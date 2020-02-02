from babel.numbers import parse_decimal, format_currency, NumberFormatError
import csv
from django.http import HttpRequest
import json
import logging
from math import ceil
from nltk.tokenize.regexp import RegexpTokenizer
import os
import pysolr
import re


logger = logging.getLogger('ogc_search')


def convert_facet_list_to_dict(facet_list: list, reverse: bool = False) -> dict:
    """
    Solr returns search facet results in the form of an alternating list. Convert the list into a dictionary key
    on the facet
    :param facet_list: facet list returned by Solr
    :param reverse: boolean flag indicating if the search results should be returned in reverse order
    :return: A dictonary of the facet values and counts
    """
    facet_dict = {}
    for i in range(0, len(facet_list)):
        if i % 2 == 0:
            facet_dict[facet_list[i]] = facet_list[i + 1]
    if reverse:
        rkeys = sorted(facet_dict,  reverse=True)
        facet_dict_r = {}
        for k in rkeys:
            facet_dict_r[k] = facet_dict[k]
        return facet_dict_r
    else:
        return facet_dict


def calc_pagination_range(results, pagesize, current_page):
    pages = int(ceil(results.hits / pagesize))
    delta = 2
    if current_page > pages:
        current_page = pages
    elif current_page < 1:
        current_page = 1
    left = current_page - delta
    right = current_page + delta + 1
    pagination = []
    spaced_pagination = []

    for p in range(1, pages + 1):
        if (p == 1) or (p == pages) or (left <= p < right):
            pagination.append(p)

    last = None
    for p in pagination:
        if last:
            if p - last == 2:
                spaced_pagination.append(last + 1)
            elif p - last != 1:
                spaced_pagination.append(0)
        spaced_pagination.append(p)
        last = p

    return spaced_pagination


def split_with_quotes(csv_string):
    # As per https://stackoverflow.com/a/23155180
    return re.findall(r'[^"\s]\S*|".+?"', csv_string)


def calc_starting_row(page_num, rows_per_age=10):
    """
    Calculate a starting row for the Solr search results. We only retrieve one page at a time
    :param page_num: Current page number
    :param rows_per_age: number of rows per page
    :return: starting row
    """
    page = 1
    try:
        page = int(page_num)
    except ValueError:
        pass
    if page < 1:
        page = 1
    elif page > 100000:  # @magic_number: arbitrary upper range
        page = 100000
    return rows_per_age * (page - 1), page


def solr_query(q, solr_url, solr_fields, solr_query_fields, solr_facet_fields, phrases_extra,
               start_row='0', pagesize='10', facets={}, sort_order='score asc', facet_limit=''):
    solr = pysolr.Solr(solr_url)
    solr_facets = []
    extras = {
            'start': start_row,
            'rows': pagesize,
            'facet': 'on',
            'facet.sort': 'index',
            'facet.field': solr_facet_fields,
            'fq': solr_facets,
            'fl': solr_fields,
            'defType': 'edismax',
            'qf': solr_query_fields,
            'sort': sort_order,
        }
    if facet_limit:
        extras.update({'facet.limit': facet_limit})

    for facet in facets.keys():
        if facets[facet] != '':
            facet_terms = facets[facet].split('|')
            quoted_terms = ['"{0}"'.format(item) for item in facet_terms]
            facet_text = '{{!tag=tag_{0}}}{0}:({1})'.format(facet, ' OR '.join(quoted_terms))
            solr_facets.append(facet_text)

    if q != '*':
        extras.update(phrases_extra)

    sr = solr.search(q, **extras)

    # If there are highlighted results, substitute the highlighted field in the doc results

    for doc in sr.docs:
        if doc['id'] in sr.highlighting:
            hl_entry = sr.highlighting[doc['id']]
            for hl_fld_id in hl_entry:
                if hl_fld_id in doc and len(hl_entry[hl_fld_id]) > 0:
                    if type(doc[hl_fld_id]) is list:
                        # Scan Multi-valued Solr fields for matching highlight fields
                        for y in hl_entry[hl_fld_id]:
                            y_filtered = re.sub('</mark>', '', re.sub(r'<mark>', "", y))
                            x = 0
                            for hl_fld_txt in doc[hl_fld_id]:
                                if hl_fld_txt == y_filtered:
                                    doc[hl_fld_id][x] = y
                                x += 1
                    else:
                        # Straight-forward field replacement with highlighted text
                        doc[hl_fld_id] = hl_entry[hl_fld_id][0]

    return sr


def get_search_terms(request: HttpRequest):
    # Get any search terms

    tr = RegexpTokenizer('[^"\s]\S*|".+?"', gaps=False)
    search_text = str(request.GET.get('search_text', ''))
    # Respect quoted strings
    search_terms = tr.tokenize(search_text)
    if len(search_terms) == 0:
        solr_search_terms = "*"
    else:
        solr_search_terms = ' '.join(search_terms)
    return solr_search_terms


def solr_query_for_export(q, solr_url, solr_fields, solr_query_fields, solr_facet_fields, sort_order, facets={},
                          phrase_extras={}):

    solr = pysolr.Solr(solr_url, search_handler='/export')
    solr_facets = []
    for facet in facets.keys():
        if facets[facet] != '':
            facet_terms = facets[facet].split('|')
            quoted_terms = ['"{0}"'.format(item) for item in facet_terms]
            facet_text = '{{!tag=tag_{0}}}{0}:({1})'.format(facet, ' OR '.join(quoted_terms))
            solr_facets.append(facet_text)

    extras = {
            'fq': solr_facets,
            'fl': solr_fields,
            'facet': 'on',
            'facet.sort': 'index',
            'facet.field': solr_facet_fields,
            'defType': 'edismax',
            'qf': solr_query_fields,
            'sort': sort_order,
        }

    if q != '*':
        extras.update(phrase_extras)

    sr = solr.search(q, **extras)

    return sr


def cache_search_results_file(cached_filename: str, sr: pysolr.Results, solr_fields: str):

    if len(sr.docs) == 0:
        return False
    if not os.path.exists(cached_filename):
        with open(cached_filename, 'w', newline='', encoding='utf8') as csvfile:
            cache_writer = csv.writer(csvfile, dialect='excel')
            headers = list(sr.docs[0])
            headers[0] = u'\N{BOM}' + headers[0]
            cache_writer.writerow(headers)
            for i in sr.docs:
                try:
                    cache_writer.writerow(i.values())
                except UnicodeEncodeError:
                    pass
    return True


def get_choices(field_name: str, schema: dict, is_lookup=False, extra_lookup=None):
    choices_en = {}
    choices_fr = {}
    alt_choices_en = {}
    alt_choices_fr = {}
    condition_field = ''
    condition_less_than = ''
    lookup_en = {}
    lookup_fr = {}
    lookup_extras = {}

    if 'resources' in schema:
        for setting in schema['resources'][0]['fields']:
            if field_name == setting['datastore_id']:
                if 'choices' in setting:
                    if 'choices_lookup' in setting:
                        for choice in setting['choices_lookup'].keys():
                            lookup_en[choice] = setting['choices_lookup'][choice]['en']
                            lookup_fr[choice] = setting['choices_lookup'][choice]['fr']
                            if extra_lookup and extra_lookup in setting['choices_lookup'][choice]:
                                lookup_extras[lookup_en[choice]] = setting['choices_lookup'][choice][extra_lookup]
                                lookup_extras[lookup_fr[choice]] = setting['choices_lookup'][choice][extra_lookup]
                    for choice in setting['choices'].keys():
                        if not is_lookup:
                            choices_en[choice] = setting['choices'][choice]['en']
                            choices_fr[choice] = setting['choices'][choice]['fr']
                        else:
                            if 'lookup' in setting['choices'][choice]:
                                expanded_choice_en = []
                                expanded_choice_fr = []
                                for look in setting['choices'][choice]['lookup']:
                                    expanded_choice_en.append(lookup_en[look])
                                    expanded_choice_fr.append(lookup_fr[look])
                                choices_en[choice] = expanded_choice_en
                                choices_fr[choice] = expanded_choice_fr
                            elif 'conditional_lookup' in setting['choices'][choice]:
                                conditional = setting['choices'][choice]['conditional_lookup']
                                for c in conditional:
                                    if 'column' in c:
                                        expanded_choice_en = []
                                        expanded_choice_fr = []
                                        condition_field = c['column']
                                        if 'less_than' in c:
                                            condition_less_than = c['less_than']
                                        if 'lookup' in c:
                                            for look in c['lookup']:
                                                expanded_choice_fr.append(lookup_fr[look])
                                                expanded_choice_en.append(lookup_en[look])
                                            alt_choices_en[choice] = expanded_choice_en
                                            alt_choices_fr[choice] = expanded_choice_fr
                                    elif 'lookup' in c:
                                        expanded_choice_en = []
                                        expanded_choice_fr = []
                                        for look in c['lookup']:
                                            expanded_choice_fr.append(lookup_fr[look])
                                            expanded_choice_en.append(lookup_en[look])
                                        choices_en[choice] = expanded_choice_en
                                        choices_fr[choice] = expanded_choice_fr
                                # @TODO Handle the conditional lookup
                break
    return {'en': choices_en, 'fr': choices_fr, 'alt_choices_en': alt_choices_en, 'alt_choices_fr': alt_choices_fr,
            'condition_field': condition_field, 'condition_less_than': condition_less_than, 'extra_field': lookup_extras}


def get_choices_json(file_name: str):
    choices_en = {}
    choices_fr = {}
    with open (file_name, 'r', encoding='utf8') as fp:
        choices = json.load(fp)
        for choice in choices.keys():
            choices_en[choice] = choices[choice]['en']
            choices_fr[choice] = choices[choice]['fr']
    return {'en': choices_en, 'fr': choices_fr}


def get_field(fields, field_key, default_value='-'):
    if field_key not in fields:
        return default_value
    else:
        if len(fields[field_key]) == 0:
            return default_value
        else:
            return fields[field_key]


def get_lookup_field(choices, fields, field_key, lang, default_value=None):
    if default_value is None:
        default_value = {}
    if field_key not in choices:
        return default_value
    elif field_key not in fields:
        return default_value
    elif (fields[field_key] not in choices[field_key][lang]) and \
         (fields[field_key] not in choices[field_key]["alt_choices_".format(lang)]):
        return default_value
    if fields[field_key] in choices[field_key]["alt_choices_{0}".format(lang)] and \
            fields[choices[field_key]['condition_field']] < choices[field_key]['condition_less_than']:
        return choices[field_key]["alt_choices_{0}".format(lang)][fields[field_key]]
    else:
        return choices[field_key][lang][fields[field_key]]


def get_multivalue_choice(choices, lang, field_values: str):
    results = []
    for field_value in field_values.split(','):
        if field_value in choices[lang]:
            results.append(choices[lang][field_value])
        else:
            print("Unknown value {0} for {1}".format(field_value, choices))
    return results


def get_choice_field(choices, fields, field_key, lang, default_value="-"):
    if field_key not in choices:
        return default_value
    elif field_key not in fields:
        return default_value
    elif fields[field_key] not in choices[field_key][lang]:
        return default_value
    else:
        return choices[field_key][lang][fields[field_key]]


def get_choice_lookup_field(controlled_list, fields, field_key, lookup_field, lang, tertiary_choice, default_value="-"):
    """
    Written specifically for contracts, this function looks up alternative values for choices_lookup fields in]
    another controlled list. For example, in contracts.yaml, the agreement_type_code field has lookup values. So
    choice value 'Z' expands to [WTO-AGP, NAFTA]. In turn 'WTO-AGP' and 'NAFTA' are keys into the choices_lookup
    values. The choice lookup for 'WTA-AGP' is linked to the choice 'GP' in the 'trade_agreement' field. Therefore
    the following call:

    get_choice_lookup_field(controlled_lists, gc, 'agreement_type_code', 'trade_agreement', 'en', 'trade_agreement',
                                        agreement_types_en)
     will return the list:

    ['World Trade Organization – Agreement on Government Procurement',  'North American Free Trade Agreement']

    If there is no corresponding lookup field in the tertiary lookup list, then the original lookup value will be
    returned instead.
    :param controlled_list: a dictionary of dictionary containing the values from the yaml file
    :param fields: the CSV record that is being processed
    :param field_key:  the field in the CSV record that is being processed
    :param lookup_field:  the primary choice field that will be expanded
    :param lang: language: 'en' or 'fr'
    :param tertiary_choice:  the associated choice field  associated with and replacing the lookup values from the
    lookup_field
    :param default_value: A value to return if no lookup value is found
    :return: a list of looked up values
    """

    # error checking
    if field_key not in controlled_list:
        return default_value
    elif field_key not in fields:
        return default_value
    if fields[field_key] not in controlled_list[field_key][lang]:
        return default_value

    # where ta linked lookup choice from the tertiary field exists use this value otherwise use the original
    # lookup value
    mapped_lookup = list()
    for x in controlled_list[field_key][lang][fields[field_key]]:
        if x in controlled_list[field_key]['extra_field']:
            mapped_lookup.append(controlled_list[tertiary_choice][lang][controlled_list[field_key]['extra_field'][x]])
        else:
            mapped_lookup.append(x)
    return mapped_lookup


def get_bilingual_field(fields, field_key: str, lang: str, default_value="-"):
    if field_key not in fields:
        return default_value
    elif len(fields[field_key]) == 0:
        return default_value
    else:
        values = [str(x).strip() for x in fields[field_key].split('|')]
        if len(values) == 1:
            return values[0]
        else:
            if lang == 'fr':
                return values[1]
            else:
                return values[0]


def get_bilingual_dollar_range(dollars: str):
    dollar_range = {'en': {'value': '$-.--', 'range': 'No Value Declared'}, 'fr': {'value': '-,-- $', 'range': 'Sans valeur déclarée'}}
    if not dollars == '':
        try:
            dollar_amount = parse_decimal(dollars.replace('$', '').replace(',', ''), locale='en')
            # Additional formatting for the dollar value
            dollar_range['en']['value'] = format_currency(dollar_amount, 'CAD', locale='en_CA')
            dollar_range['fr']['value'] = format_currency(dollar_amount, 'CAD', locale='fr_CA')
            # Set a value range
            if dollar_amount < 0:
                dollar_range['en']['range'] = '(a) Negative'
                dollar_range['fr']['range'] = '(a) negatif'
            elif dollar_amount < 10000:
                dollar_range['en']['range'] = '(b) Less than $10,000'
                dollar_range['fr']['range'] = '(b) moins de 10 000 $'
            elif 10000 <= dollar_amount < 25000:
                dollar_range['en']['range'] = '(c) $10,000 - $25,000'
                dollar_range['fr']['range'] = '(c) de 10 000 $ à 25 000 $'
            elif 25000 <= dollar_amount < 100000:
                dollar_range['en']['range'] = '(d) $25,000 - $100,000'
                dollar_range['fr']['range'] = '(d) de 25 000 $ à 100 000 $'
            elif 100000 <= dollar_amount < 1000000:
                dollar_range['en']['range'] = '(e) $100,000 - $1,000,000'
                dollar_range['fr']['range'] = '(e) de 100 000 $ à 1 000 000 $'
            elif 1000000 <= dollar_amount < 5000000:
                dollar_range['en']['range'] = '(f) $1,000,000 - $5,000,000'
                dollar_range['fr']['range'] = '(f) de 1 000 000 $ à 5 000 000 $'
            else:
                dollar_range['en']['range'] = '(g) More than $5,000,000'
                dollar_range['fr']['range'] = '(g) plus de cinq millions $'
        except NumberFormatError:
            pass
    return dollar_range
