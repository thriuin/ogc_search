# coding=utf-8


from babel.dates import format_date
from django import template
from django.utils.translation import gettext
from dateutil import parser
import json


register = template.Library()


@register.filter('SwapLangCode', autoescape=True)
def other_lang_code(value):
    if str(value).lower() == 'en':
        return 'fr'
    elif str(value).lower() == 'fr':
        return 'en'
    else:
        return ''


@register.filter('SwapLangName', autoescape=True)
def other_lang(value):
    if str(value) == 'en':
        return 'Français'
    elif str(value) == 'fr':
        return 'English'
    else:
        return ''

@register.filter('EmptyFacetMessage', autoescape=True)
def search_facet_is_empty_message(value):
    msg = ''
    if type(value) is dict:
        c = 0
        for k,v in value.items():
            c = c + v
        if c == 0:
            msg = gettext("There are no filters for this search")
    return msg


@register.filter('ToMonth', autoescape=True)
def to_month(value):
    months = [
        'January',
        'February',
        'March',
        'April',
        'May',
        'June',
        'July',
        'August',
        'September',
        'October',
        'November',
        'December'
    ]
    month_int = 0
    try:
        month_int = int(value)
    except ValueError:
        pass
    if month_int < 1 or month_int > 12:
        return ''
    else:
        return gettext(months[month_int - 1])


@register.filter('isoDateTimeToDate')
def iso_date_time_to_date(value):
    my_date = parser.parse(value)
    return my_date.strftime("%Y-%m-%d")


@register.filter('service_standards_en')
def si_std_json_to_html_en(value):
    std_obj = json.loads(value)
    return "<strong>Standard: {0}</strong><br>{1}<br>".format(
        std_obj['service_std_id'],
        std_obj['service_std_en'])


@register.filter('service_standards_fr')
def si_std_json_to_html_fr(value):
    std_obj = json.loads(value)
    return "<strong>Norme : {0}</strong><br>{1}<br>".format(
        std_obj['service_std_id'],
        std_obj['service_std_fr'])


@register.filter('nap_status')
def nap_status_alert(value):
    if value in ('Not started', 'Non commencé'):
        return '<span class="label label-default">{0}</span>'.format(value)
    elif value in ('Limited progress', 'Progrès limité'):
        return '<span class="label label-warning">{0}</span>'.format(value)
    elif value in ('Substantial progress', 'Progrès important'):
        return '<span class="label label-info">{0}</span>'.format(value)
    elif value in ('Complete', 'Réalisé'):
        return '<span class="label label-success">{0}</span>'.format(value)
    else:
        return value


@register.filter('friendly_date_en')
def human_friendly_date_en(value: str):
    if len(value) == 10:
        my_date = parser.parse(value)
        return format_date(my_date, 'medium', locale='en_CA')
    else:
        return ""


@register.filter('friendly_date_fr')
def human_friendly_date_fr(value: str):
    if len(value) == 10:
        my_date = parser.parse(value)
        return format_date(my_date, 'medium', locale='fr_CA')
    else:
        return ""


@register.filter('trim_left')
def trim_left(value: str, arg: int):
    if len(value) < arg:
        return value
    else:
        return value[arg:]
