import csv
import logging
from math import ceil
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
    elif page > 10000:  # @magic_number: arbitrary upper range
        page = 10000
    return rows_per_age * (page - 1), page


def solr_query(q, solr_url, solr_fields, solr_query_fields, solr_facet_fields, phrases_extra,
               start_row='0', pagesize='10', facets={}, sort_order='score asc'):
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
                            y_filtered = re.sub('</mark>', '', re.sub(r'<mark class="highlight">', "", y))
                            x = 0
                            for hl_fld_txt in doc[hl_fld_id]:
                                if hl_fld_txt == y_filtered:
                                    doc[hl_fld_id][x] = y
                                x += 1
                    else:
                        # Straight-forward field replacement with highlighted text
                        doc[hl_fld_id] = hl_entry[hl_fld_id][0]

    return sr


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

    if not os.path.exists(cached_filename):
        with open(cached_filename, 'w', newline='', encoding='utf8') as csvfile:
            cache_writer = csv.writer(csvfile, dialect='excel')
            headers = solr_fields.split(',')
            headers[0] = u'\N{BOM}' + headers[0]
            cache_writer.writerow(headers)
            for i in sr.docs:
                try:
                    cache_writer.writerow(i.values())
                except UnicodeEncodeError:
                    pass
    return True
