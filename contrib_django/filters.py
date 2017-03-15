from flask_admin.babel import lazy_gettext
from flask_admin.model import filters
from django.db.models import Q


class BaseDjangoFilter(filters.BaseFilter):
    """
        Base Django filter.
    """

    def __init__(self, column, name, options=None, data_type=None):
        """
            Constructor.

            :param column:
                Model field
            :param name:
                Display name
            :param options:
                Fixed set of options
            :param data_type:
                Client data type
        """
        super(BaseDjangoFilter, self).__init__(name, options, data_type)

        self.column = column


# Common filters
class FilterEqual(BaseDjangoFilter):
    def apply(self, query, value):
        return query.filter(**{"{}__iexact".format(self.column): value})

    def operation(self):
        return lazy_gettext('equals')


class FilterNotEqual(BaseDjangoFilter):
    def apply(self, query, value):
        return query.filter(~Q(**{"{}__iexact".format(self.column): value}))

    def operation(self):
        return lazy_gettext('not equal')


class FilterLike(BaseDjangoFilter):
    def apply(self, query, value):
        return query.filter(**{"{}__icontains".format(self.column): value})

    def operation(self):
        return lazy_gettext('contains')


class FilterNotLike(BaseDjangoFilter):
    def apply(self, query, value):
        return query.filter(Q(**{"{}__icontains".format(self.column): value}))
        
    def operation(self):
        return lazy_gettext('not contains')


class FilterGreater(BaseDjangoFilter):
    def apply(self, query, value):
        return query.filter(**{"{}__gt".format(self.column): value})

    def operation(self):
        return lazy_gettext('greater than')


class FilterSmaller(BaseDjangoFilter):
    def apply(self, query, value):
        return query.filter(**{"{}__lt".format(self.column): value})

    def operation(self):
        return lazy_gettext('smaller than')


class FilterEmpty(BaseDjangoFilter, filters.BaseBooleanFilter):
    def apply(self, query, value):
        if value == '1':
            return query.filter(**{"{}__isnull".format(self.column):True})
        else:
            return query.filter(~Q(**{"{}__isnull".format(self.column):True}))

    def operation(self):
        return lazy_gettext('empty')


class FilterInList(BaseDjangoFilter):
    def __init__(self, column, name, options=None, data_type=None):
        super(FilterInList, self).__init__(
            column, name, options, data_type='select2-tags')

    def clean(self, value):
        return [v.strip() for v in value.split(',') if v.strip()]

    def apply(self, query, value):
        return query.filter(**{"{}__in".format(self.column): (value or [None])})

    def operation(self):
        return lazy_gettext('in list')


class FilterNotInList(FilterInList):
    def apply(self, query, value):
        # NOT IN can exclude NULL values, so "or_ == None" needed to be added
        first = ~Q(**{"{}__in".format(self.column): (value or [None])})
        second = Q(**{"{}__in".format(self.column): (value or [None])})
        return query.filter(first | second)

    def operation(self):
        return lazy_gettext('not in list')


# Customized type filters
class BooleanEqualFilter(FilterEqual, filters.BaseBooleanFilter):
    def clean(self, value):
        return int(value)


class BooleanNotEqualFilter(FilterNotEqual, filters.BaseBooleanFilter):
    def clean(self, value):
        return int(value)


class IntEqualFilter(FilterEqual, filters.BaseIntFilter):
    pass


class IntNotEqualFilter(FilterNotEqual, filters.BaseIntFilter):
    pass


class IntGreaterFilter(FilterGreater, filters.BaseIntFilter):
    pass


class IntSmallerFilter(FilterSmaller, filters.BaseIntFilter):
    pass


class IntInListFilter(filters.BaseIntListFilter, FilterInList):
    pass


class IntNotInListFilter(filters.BaseIntListFilter, FilterNotInList):
    pass


class FloatEqualFilter(FilterEqual, filters.BaseFloatFilter):
    pass


class FloatNotEqualFilter(FilterNotEqual, filters.BaseFloatFilter):
    pass


class FloatGreaterFilter(FilterGreater, filters.BaseFloatFilter):
    pass


class FloatSmallerFilter(FilterSmaller, filters.BaseFloatFilter):
    pass


class FloatInListFilter(filters.BaseFloatListFilter, FilterInList):
    pass


class FloatNotInListFilter(filters.BaseFloatListFilter, FilterNotInList):
    pass


class DateEqualFilter(FilterEqual, filters.BaseDateFilter):
    pass


class DateNotEqualFilter(FilterNotEqual, filters.BaseDateFilter):
    pass


class DateGreaterFilter(FilterGreater, filters.BaseDateFilter):
    pass


class DateSmallerFilter(FilterSmaller, filters.BaseDateFilter):
    pass


class DateBetweenFilter(BaseDjangoFilter, filters.BaseDateBetweenFilter):
    def __init__(self, column, name, options=None, data_type=None):
        super(DateBetweenFilter, self).__init__(
            column, name, options, data_type='daterangepicker')

    def apply(self, query, value):
        start, end = value
        return query.filter(**{"{}__range".format(self.column):(start, end)})


class DateNotBetweenFilter(DateBetweenFilter):
    def apply(self, query, value):
        start, end = value
        return query.filter(~Q(**{"{}__range".format(self.column):(start, end)}))

    def operation(self):
        return lazy_gettext('not between')


class DateTimeEqualFilter(FilterEqual, filters.BaseDateTimeFilter):
    pass


class DateTimeNotEqualFilter(FilterNotEqual, filters.BaseDateTimeFilter):
    pass


class DateTimeGreaterFilter(FilterGreater, filters.BaseDateTimeFilter):
    pass


class DateTimeSmallerFilter(FilterSmaller, filters.BaseDateTimeFilter):
    pass


class DateTimeBetweenFilter(BaseDjangoFilter,
                            filters.BaseDateTimeBetweenFilter):
    def __init__(self, column, name, options=None, data_type=None):
        super(DateTimeBetweenFilter, self).__init__(
            column, name, options, data_type='datetimerangepicker')

    def apply(self, query, value):
        start, end = value
        return query.filter(Q(**{"{}__range".format(self.column):(start, end)}))


class DateTimeNotBetweenFilter(DateTimeBetweenFilter):
    def apply(self, query, value):
        start, end = value
        return query.filter(~Q(**{"{}__range".format(self.column):(start, end)}))

    def operation(self):
        return lazy_gettext('not between')


class TimeEqualFilter(FilterEqual, filters.BaseTimeFilter):
    pass


class TimeNotEqualFilter(FilterNotEqual, filters.BaseTimeFilter):
    pass


class TimeGreaterFilter(FilterGreater, filters.BaseTimeFilter):
    pass


class TimeSmallerFilter(FilterSmaller, filters.BaseTimeFilter):
    pass


class TimeBetweenFilter(BaseDjangoFilter, filters.BaseTimeBetweenFilter):
    def __init__(self, column, name, options=None, data_type=None):
        super(TimeBetweenFilter, self).__init__(
            column, name, options, data_type='timerangepicker')

    def apply(self, query, value):
        start, end = value
        return query.filter(Q(**{"{}__range".format(self.column):(start, end)}))


class TimeNotBetweenFilter(TimeBetweenFilter):
    def apply(self, query, value):
        start, end = value
        return query.filter(~Q(**{"{}__range".format(self.column):(start, end)}))

    def operation(self):
        return lazy_gettext('not between')


# Base peewee filter field converter
class FilterConverter(filters.BaseFilterConverter):
    strings = (FilterLike, FilterNotLike, FilterEqual, FilterNotEqual,
               FilterEmpty, FilterInList, FilterNotInList)
    int_filters = (IntEqualFilter, IntNotEqualFilter, IntGreaterFilter,
                   IntSmallerFilter, FilterEmpty, IntInListFilter,
                   IntNotInListFilter)
    float_filters = (FloatEqualFilter, FloatNotEqualFilter, FloatGreaterFilter,
                     FloatSmallerFilter, FilterEmpty, FloatInListFilter,
                     FloatNotInListFilter)
    bool_filters = (BooleanEqualFilter, BooleanNotEqualFilter)
    date_filters = (DateEqualFilter, DateNotEqualFilter, DateGreaterFilter,
                    DateSmallerFilter, DateBetweenFilter, DateNotBetweenFilter,
                    FilterEmpty)
    datetime_filters = (DateTimeEqualFilter, DateTimeNotEqualFilter,
                        DateTimeGreaterFilter, DateTimeSmallerFilter,
                        DateTimeBetweenFilter, DateTimeNotBetweenFilter,
                        FilterEmpty)
    time_filters = (TimeEqualFilter, TimeNotEqualFilter, TimeGreaterFilter,
                    TimeSmallerFilter, TimeBetweenFilter, TimeNotBetweenFilter,
                    FilterEmpty)

    def convert(self, type_name, column, name):
        filter_name = type_name.lower()

        if filter_name in self.converters:
            return self.converters[filter_name](column, name)

        return None

    @filters.convert('CharField', 'TextField')
    def conv_string(self, column, name):
        return [f(column, name) for f in self.strings]

    @filters.convert('BooleanField')
    def conv_bool(self, column, name):
        return [f(column, name) for f in self.bool_filters]

    @filters.convert('IntegerField', 'BigIntegerField', 'AutoField')
    def conv_int(self, column, name):
        return [f(column, name) for f in self.int_filters]

    @filters.convert('DecimalField', 'FloatField', 'DoubleField')
    def conv_float(self, column, name):
        return [f(column, name) for f in self.float_filters]

    @filters.convert('DateField')
    def conv_date(self, column, name):
        return [f(column, name) for f in self.date_filters]

    @filters.convert('DateTimeField')
    def conv_datetime(self, column, name):
        return [f(column, name) for f in self.datetime_filters]

    @filters.convert('TimeField')
    def conv_time(self, column, name):
        return [f(column, name) for f in self.time_filters]
