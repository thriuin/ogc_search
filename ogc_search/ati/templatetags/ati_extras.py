from django import template
#from django.conf.urls.i18n import i18n_patterns
from django.urls import reverse
from django.utils.translation import gettext
from ati.views import AtiSearchView


register = template.Library()


#@todo Is this needed anymore - GET RID OF!!

@register.simple_tag(takes_context=True)
def facet_url(context, facet_type='', add_item=''):
    months = list(context['months_selected'])
    if '*' in months:
        months.remove('*')
    if facet_type == 'month' and add_item in months:
        months.remove(add_item)
    else:
        months.append(add_item)

    years = list(context['years_selected'])
    if '*' in years:
        years.remove('*')
    if facet_type == 'year' and add_item in years:
        years.remove(add_item)
    else:
        years.append(add_item)

    orgs = list(context['organizations_selected'])
    if '*' in orgs:
        orgs.remove('*')
    if facet_type == 'org' and add_item in orgs:
        orgs.remove(add_item)
    else:
        orgs.append(add_item)

    base_path = "{0}?".format(reverse('AtiQuery'))
    if context['search_text'] != '*':
        base_path = "{0}search_text={1}&".format(base_path, context['search_text'])
    months_args = ''
    if type(months) is list:
        months_args = "month={0}&".format("&month=".join(months))
    years_args = ''
    if type(years) is list:
        years_args = "year={0}&".format("&year=".join(years))
    orgs_args = ''
    if type(orgs) is list:
        orgs_args = "organization_en={0}&".format("&organization_en=".join(orgs))

    return "{0}{1}{2}{3}page={4}".format(base_path, months_args, years_args, orgs_args, context['currentpage'])



