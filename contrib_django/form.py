from wtforms import fields

from django.db.models import Model as BaseModel
from django.db.models.fields import AutoField
from wtforms.ext.django.orm import ModelConverter, model_form

from flask_admin import form
from flask_admin._compat import iteritems, itervalues
from flask_admin.model.form import InlineFormAdmin, InlineModelConverterBase
from flask_admin.model.fields import InlineModelFormField, InlineFieldList, AjaxSelectField
from flask_admin.model.form import (converts, ModelConverterBase,
                                    InlineModelConverterBase, FieldPlaceholder)

from .tools import get_primary_key, get_meta_fields
from .ajax import create_ajax_loader

from wtforms import fields, validators

class InlineModelFormList(InlineFieldList):
    """
        Customized inline model form list field.
    """

    form_field_type = InlineModelFormField
    """
        Form field type. Override to use custom field for each inline form
    """

    def __init__(self, form, model, prop, inline_view, **kwargs):
        self.form = form
        self.model = model
        self.prop = prop
        self.inline_view = inline_view

        self._pk = get_primary_key(model)
        super(InlineModelFormList, self).__init__(
            self.form_field_type(form, self._pk), **kwargs)

    def display_row_controls(self, field):
        return field.get_pk() is not None

    """ bryhoyt removed def process() entirely, because I believe it was buggy
        (but worked because another part of the code had a complimentary bug)
        and I'm not sure why it was necessary anyway.

        If we want it back in, we need to fix the following bogus query:
        self.model.select().where(attr == data).execute()

        `data` is not an ID, and only happened to be so because we patched it
        in in .contribute() below

        For reference, .process() introduced in:
        https://github.com/flask-admin/flask-admin/commit/2845e4b28cb40b25e2bf544b327f6202dc7e5709

        Fixed, brokenly I think, in:
        https://github.com/flask-admin/flask-admin/commit/4383eef3ce7eb01878f086928f8773adb9de79f8#diff-f87e7cd76fb9bc48c8681b24f238fb13R30
    """

    def populate_obj(self, obj, name):
        pass

    def save_related(self, obj):
        model_id = getattr(obj, self._pk)

        attr = getattr(self.model, self.prop)
        values = self.model.select().where(attr == model_id).execute()

        pk_map = dict((str(getattr(v, self._pk)), v) for v in values)

        # Handle request data
        for field in self.entries:
            field_id = field.get_pk()

            is_created = field_id not in pk_map
            if not is_created:
                model = pk_map[field_id]

                if self.should_delete(field):
                    model.delete_instance(recursive=True)
                    continue
            else:
                model = self.model()

            field.populate_obj(model, None)

            # Force relation
            setattr(model, self.prop, model_id)

            self.inline_view._on_model_change(field, model, is_created)

            model.save()

            # Recurse, to save multi-level nested inlines
            for f in itervalues(field.form._fields):
                if f.type == 'InlineModelFormList':
                    f.save_related(model)


class CustomModelConverter(ModelConverterBase):
    def __init__(self, view):
        super(CustomModelConverter, self).__init__()
        self.converter_class = ModelConverter()
        self.view = view

    def _get_field_override(self, name):
        form_overrides = getattr(self.view, 'form_overrides', None)

        if form_overrides:
            return form_overrides.get(name)

        return None

    
    def _convert_choices(self, choices):
        for c in choices:
            if isinstance(c, tuple):
                yield c
            else:
                yield (c, c)

    def convert(self, model, field, field_args):
        # Check if it is overridden field
        if isinstance(field, FieldPlaceholder):
            return form.recreate_field(field.field)

        kwargs = {
            'label': getattr(field, 'verbose_name', None),
            'description': getattr(field, 'help_text', ''),
            'validators': [],
            'filters': [],
            'default': field.default
        }

        if field_args:
            kwargs.update(field_args)

        if kwargs['validators']:
            # Create a copy of the list since we will be modifying it.
            kwargs['validators'] = list(kwargs['validators'])
        try:
            if field.required:
                kwargs['validators'].append(validators.InputRequired())
        except AttributeError:
            pass
        ftype = type(field).__name__

        if field.choices:
            kwargs['choices'] = list(self._convert_choices(field.choices))

            if ftype in self.converters:
                kwargs["coerce"] = self.coerce(ftype)
            if kwargs.pop('multiple', False):
                return fields.SelectMultipleField(**kwargs)
            return fields.SelectField(**kwargs)

        ftype = type(field).__name__

        if hasattr(field, 'to_form_field'):
            return field.to_form_field(model, kwargs)

        override = self._get_field_override(field.name)
        if override:
            return override(**kwargs)

        if ftype in self.converters:
            return self.converters[ftype](model, field, kwargs)


def get_form(model,
             converter,
             base_class=form.BaseForm,
             only=None,
             exclude=None,
             field_args=None,
             extra_fields=None):
    """
        Create form from django model and contribute extra fields, if necessary
    """
    result = model_form(
        model,
        base_class=base_class,
        only=only,
        exclude=exclude,
        field_args=field_args,
        converter=converter)

    if extra_fields:
        for name, field in iteritems(extra_fields):
            setattr(result, name, form.recreate_field(field))

    return result


class InlineModelConverter(InlineModelConverterBase):
    """
        Inline model form helper.
    """

    inline_field_list_type = InlineModelFormList
    """
        Used field list type.

        If you want to do some custom rendering of inline field lists,
        you can create your own wtforms field and use it instead
    """

    def get_info(self, p):
        info = super(InlineModelConverter, self).get_info(p)

        if info is None:
            if isinstance(p, BaseModel):
                info = InlineFormAdmin(p)
            else:
                model = getattr(p, 'model', None)
                if model is None:
                    raise Exception('Unknown inline model admin: %s' % repr(p))

                attrs = dict()

                for attr in dir(p):
                    if not attr.startswith('_') and attr != 'model':
                        attrs[attr] = getattr(p, attr)

                info = InlineFormAdmin(model, **attrs)

        # Resolve AJAX FKs
        info._form_ajax_refs = self.process_ajax_refs(info)

        return info

    def process_ajax_refs(self, info):
        refs = getattr(info, 'form_ajax_refs', None)

        result = {}

        if refs:
            for name, opts in iteritems(refs):
                new_name = '%s.%s' % (info.model.__name__.lower(), name)

                loader = None
                if isinstance(opts, (list, tuple)):
                    loader = create_ajax_loader(info.model, new_name, name,
                                                opts)
                else:
                    loader = opts

                result[name] = loader
                self.view._form_ajax_refs[new_name] = loader

        return result

    def contribute(self, converter, model, form_class, inline_model):
        # Find property from target model to current model
        reverse_field = None

        info = self.get_info(inline_model)

        for field in get_meta_fields(info.model):
            field_type = type(field)

            if field_type == AutoField:
                if field.rel_model == model:
                    reverse_field = field
                    break
        else:
            raise Exception('Cannot find reverse relation for model %s' %
                            info.model)

        # Remove reverse property from the list
        ignore = [reverse_field.name]

        if info.form_excluded_columns:
            exclude = ignore + info.form_excluded_columns
        else:
            exclude = ignore

        # Create field
        child_form = info.get_form()

        if child_form is None:
            child_form = model_form(
                info.model,
                base_class=form.BaseForm,
                only=info.form_columns,
                exclude=exclude,
                field_args=info.form_args,
                converter=converter)

        prop_name = reverse_field.related_name

        label = self.get_label(info, prop_name)

        setattr(
            form_class,
            prop_name,
            self.inline_field_list_type(
                child_form,
                info.model,
                reverse_field.name,
                info,
                label=label or info.model.__name__))

        return form_class


def save_inline(form, model):
    for f in itervalues(form._fields):
        if f.type == 'InlineModelFormList':
            f.save_related(model)
