from flask import request, flash, abort, Response
from flask_admin.babel import gettext, ngettext, lazy_gettext
from wtforms.validators import ValidationError as wtfValidationError
from flask_admin.model import BaseModelView
from django.db.models import fields as django_fields
from . import filters
from .tools import get_primary_key, parse_like_term
from flask_admin.actions import action
from .ajax import create_ajax_loader
from .form import get_form, CustomModelConverter, InlineModelConverter, save_inline
from flask_admin.model.form import create_editable_list_form
from django.db.models import Q
from django.core.paginator import Paginator
import logging
from flask_admin._compat import itervalues, as_unicode
from django.core.exceptions import ValidationError

log = logging.getLogger("flask-admin.django")


def format_error(error):
    if isinstance(error, ValidationError):
        return as_unicode(error)

    if isinstance(error, wtfValidationError):
        return '. '.join(itervalues(error.to_dict()))

    return as_unicode(error)


class DjangoModelView(BaseModelView):
    filter_converter = filters.FilterConverter()
    model_form_converter = CustomModelConverter
    inline_model_form_converter = InlineModelConverter
    inline_models = []
    fast_mass_delete = False

    def __init__(self,
                 model,
                 name=None,
                 category=None,
                 endpoint=None,
                 url=None,
                 static_folder=None,
                 menu_class_name=None,
                 menu_icon_type=None,
                 menu_icon_value=None):
        self._search_fields = []

        super(DjangoModelView, self).__init__(
            model,
            name,
            category,
            endpoint,
            url,
            static_folder,
            menu_class_name=menu_class_name,
            menu_icon_type=menu_icon_type,
            menu_icon_value=menu_icon_value)

        self._primary_key = self.scaffold_pk()

    def scaffold_pk(self):
        return get_primary_key(self.model)

    def _get_model_fields(self, model=None):
        if model is None:
            model = self.model
        return model._meta.fields

    def get_pk_value(self, model):
        return model.pk

    def scaffold_list_columns(self):
        columns = []

        for field in self._get_model_fields():
            # Verify type
            field_class = type(field)

            if field_class == django_fields.related.ForeignKey:
                columns.append(field.name)
            elif self.column_display_pk or field_class != django_fields.AutoField:
                columns.append(field.name)

        return columns

    def scaffold_sortable_columns(self):
        columns = dict()

        for field in self._get_model_fields():
            if self.column_display_pk or type(
                    field) != django_fields.AutoField:
                columns[field.name] = field

        return columns

    def init_search(self):
        if self.column_searchable_list:
            for ppp in self.column_searchable_list:
                field_type = ppp
                if isinstance(ppp, str):
                    field_type = type(self.model._meta.get_field(ppp))

                # Check type
                if (field_type != django_fields.CharField and
                        field_type != django_fields.TextField):
                    raise Exception('Can only search on text columns. ' +
                                    'Failed to setup search for "%s"' % ppp)

                self._search_fields.append(ppp)

        return bool(self._search_fields)

    def scaffold_filters(self, name):
        if isinstance(name, str):
            attr = getattr(self.model, name, None)
        else:
            attr = name

        if attr is None:
            raise Exception('Failed to find field for filter: %s' % name)

        # Check if field is in different model
        if attr.model_class != self.model:
            visible_name = '%s / %s' % (
                self.get_column_name(attr.model_class.__name__),
                self.get_column_name(attr.name))
        else:
            if not isinstance(name, str):
                visible_name = self.get_column_name(attr.name)
            else:
                visible_name = self.get_column_name(name)

        type_name = type(attr).__name__
        flt = self.filter_converter.convert(type_name, attr, visible_name)

        return flt

    def is_valid_filter(self, _filter):
        return isinstance(_filter, filters.BaseDjangoFilter)

    def scaffold_form(self):
        form_class = get_form(
            self.model,
            self.model_form_converter(self),
            base_class=self.form_base_class,
            only=self.form_columns,
            exclude=self.form_excluded_columns,
            field_args=self.form_args,
            extra_fields=self.form_extra_fields)

        if self.inline_models:
            form_class = self.scaffold_inline_form_models(form_class)

        return form_class

    def scaffold_list_form(self, widget=None, validators=None):
        """
            Create form for the `index_view` using only the columns from
            `self.column_editable_list`.

            :param widget:
                WTForms widget class. Defaults to `XEditableWidget`.
            :param validators:
                `form_args` dict with only validators
                {'name': {'validators': [required()]}}
        """
        form_class = get_form(
            self.model,
            self.model_form_converter(self),
            base_class=self.form_base_class,
            only=self.column_editable_list,
            field_args=validators)

        return create_editable_list_form(self.form_base_class, form_class,
                                         widget)

    def scaffold_inline_form_models(self, form_class):
        converter = self.model_form_converter(self)
        inline_converter = self.inline_model_form_converter(self)

        for m_v in self.inline_models:
            form_class = inline_converter.contribute(converter, self.model,
                                                     form_class, m_v)

        return form_class

    # AJAX foreignkey support
    def _create_ajax_loader(self, name, options):
        return create_ajax_loader(self.model, name, name, options)

    def get_query(self):
        """
        Returns the QuerySet for this view.  By default, it returns all the
        objects for the current model.
        """
        return self.model.objects

    def _search(self, query, search_term):
        # TODO: Unfortunately, MongoEngine contains bug which
        # prevents running complex Q queries and, as a result,
        # Flask-Admin does not support per-word searching like
        # in other backends
        values = search_term.split(' ')
        stmt = None
        for value in values:
            if not value:
                continue

            search_type, term = parse_like_term(value)
            for field in self._search_fields:
                q = Q(**{"{}__{}".format(field, search_type): term})

                if stmt is None:
                    stmt = q
                else:
                    stmt |= q
        return query.filter(stmt)

    def get_list(self,
                 page,
                 sort_column,
                 sort_desc,
                 search,
                 filters,
                 execute=True,
                 page_size=None):
        """
            Get list of objects from MongoEngine

            :param page:
                Page number
            :param sort_column:
                Sort column
            :param sort_desc:
                Sort descending
            :param search:
                Search criteria
            :param filters:
                List of applied filters
            :param execute:
                Run query immediately or not
            :param page_size:
                Number of results. Defaults to ModelView's page_size. Can be
                overriden to change the page_size limit. Removing the page_size
                limit requires setting page_size to 0 or False.
        """
        query = self.get_query()

        # Filters
        if self._filters:
            for flt, flt_name, value in filters:
                sample_filter = self._filters[flt]
                query = sample_filter.apply(query, sample_filter.clean(value))

        # Search
        if self._search_supported and search:
            query = self._search(query, search)

        # Get count
        count = query.count() if not self.simple_list_pager else None

        # Sorting
        if sort_column:
            query = query.order_by('%s%s' %
                                   ('-' if sort_desc else '', sort_column))
        else:
            order = self._get_default_order()

            if order:
                query = query.order_by('%s%s' %
                                       ('-' if order[1] else '', order[0]))
        # Pagination
        page_size = self.page_size
        paginator = Paginator(query, page_size)

        if page_size:
            query = paginator.object_list
            
        if page and page_size:
            query = paginator.page(page).object_list

        if execute:
            query = query.all()

        return count, query

    def get_one(self, _id):
        """
            Return a single model instance by its ID

            :param id:
                Model ID
        """
        return self.get_query().filter(pk=_id).first()

    def create_model(self, form):
        """
            Create model helper

            :param form:
                Form instance
        """
        try:
            model = self.model()
            form.populate_obj(model)
            self._on_model_change(form, model, True)
            model.save()
        except Exception as ex:
            if not self.handle_view_exception(ex):
                flash(
                    gettext(
                        'Failed to create record. %(error)s',
                        error=format_error(ex)),
                    'error')
                log.exception('Failed to create record.')

            return False
        else:
            self.after_model_change(form, model, True)

        return model

    def update_model(self, form, model):
        """
            Update model helper

            :param form:
                Form instance
            :param model:
                Model instance to update
        """
        try:
            form.populate_obj(model)
            self._on_model_change(form, model, False)
            model.save()
        except Exception as ex:
            if not self.handle_view_exception(ex):
                flash(
                    gettext(
                        'Failed to update record. %(error)s',
                        error=format_error(ex)),
                    'error')
                log.exception('Failed to update record.')

            return False
        else:
            self.after_model_change(form, model, False)

        return True

    def delete_model(self, model):
        """
            Delete model helper

            :param model:
                Model instance
        """
        try:
            self.on_model_delete(model)
            model.delete()
        except Exception as ex:
            if not self.handle_view_exception(ex):
                flash(
                    gettext(
                        'Failed to delete record. %(error)s',
                        error=format_error(ex)),
                    'error')
                log.exception('Failed to delete record.')

            return False
        else:
            self.after_model_delete(model)

        return True

    # Default model actions
    def is_action_allowed(self, name):
        # Check delete action permission
        if name == 'delete' and not self.can_delete:
            return False

        return super(DjangoModelView, self).is_action_allowed(name)

    @action('delete',
            lazy_gettext('Delete'),
            lazy_gettext('Are you sure you want to delete selected records?'))
    def action_delete(self, ids):
        try:
            if self.fast_mass_delete:
                count, _ = self.get_query().filter(pk__in=ids).delete()
            else:
                count = 0
                for obj in self.get_query().filter(pk__in=ids).all():
                    count += self.delete_model(obj)

            flash(
                ngettext(
                    'Record was successfully deleted.',
                    '%(count)s records were successfully deleted.',
                    count,
                    count=count),
                'success')
        except Exception as ex:
            if not self.handle_view_exception(ex):
                flash(
                    gettext(
                        'Failed to delete records. %(error)s', error=str(ex)),
                    'error')
