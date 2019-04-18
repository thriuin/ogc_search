from django.conf import settings
from django.http import HttpRequest, HttpResponseRedirect, FileResponse
from django.shortcuts import render
from django.views.generic import View
import csv
import hashlib
import logging
from math import ceil
import os
import pysolr
import re
import time


def _convert_facet_list_to_dict(facet_list: list, reverse: bool = False) -> dict:
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


def _calc_pagination_range(results, pagesize, current_page):
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

# Create your views here.

class ATISearchView(View):

    @staticmethod
    def split_with_quotes(csv_string):
        # As per https://stackoverflow.com/a/23155180
        return re.findall(r'[^"\s]\S*|".+?"', csv_string)

    def __init__(self):
        super().__init__()
        # French search fields
        self.solr_fields_fr = ("id,request_no_txt_ws,request_no_txt_ws,summary_text_fr,summary_fr_s,owner_org_fr_s,disposition_fr_s,"
                               "month_i,year_i, pages_i,umd_i,nil_report_b,owner_org_title_txt_fr")
        self.solr_query_fields_fr = ['owner_org_fr_s^2', 'request_no_txt_ws', 'summary_fr_s^3', '_text_fr_^0.5']
        self.solr_facet_fields_fr = ['{!ex=tag_owner_org_fr_s}owner_org_fr_s',
                                     '{!ex=tag_month_i}month_i',
                                     '{!ex=tag_year_i}year_i']
        self.solr_hl_fields_fr = ['summary_text_fr', 'request_no_txt_ws', 'owner_org_title_txt_fr']

        # English search fields
        self.solr_fields_en = ("id,request_no_s,request_no_txt_ws,summary_text_en,summary_en_s,owner_org_en_s,disposition_en_s,"
                               "month_i,year_i, pages_i,umd_i,nil_report_b,owner_org_title_txt_en")
        self.solr_query_fields_en = ['owner_org_en_s^2', 'request_no_txt_ws', 'summary_en_s^3', '_text_en_^0.5']
        self.solr_facet_fields_en = ['{!ex=tag_owner_org_en_s}owner_org_en_s',
                                     '{!ex=tag_month_i}month_i',
                                     '{!ex=tag_year_i}year_i']
        self.solr_hl_fields_en = ['summary_text_en', 'request_no_txt_ws', 'owner_org_title_txt_en']

        self.phrase_xtras_fr = {
            'hl': 'on',
            'hl.simple.pre': '<mark class="highlight">',
            'hl.simple.post': '</mark>',
            'hl.method': 'unified',
            'hl.snippets': 10,
            'hl.fl': self.solr_hl_fields_fr,
            'hl.preserveMulti': 'true',
            'ps': 10,
            'mm': '3<70%',
        }
        self.phrase_xtras_en = {
            'hl': 'on',
            'hl.simple.pre': '<mark class="highlight">',
            'hl.simple.post': '</mark>',
            'hl.method': 'unified',
            'hl.snippets': 10,
            'hl.fl': self.solr_hl_fields_en,
            'hl.preserveMulti': 'true',
            'ps': 10,
            'mm': '3<70%',
        }

    def solr_query(self, q, startrow='0', pagesize='10', facets={}, language='en',
                   sort_order='score asc'):
        solr = pysolr.Solr(settings.SOLR_ATI)
        solr_facets = []
        if language == 'fr':
            extras = {
                'start': startrow,
                'rows': pagesize,
                'facet': 'on',
                'facet.sort': 'index',
                'facet.field': self.solr_facet_fields_fr,
                'fq': solr_facets,
                'fl': self.solr_fields_fr,
                'defType': 'edismax',
                'qf': self.solr_query_fields_fr,
                'sort': sort_order,
            }

        else:
            extras = {
                'start': startrow,
                'rows': pagesize,
                'facet': 'on',
                'facet.sort': 'index',
                'facet.field': self.solr_facet_fields_en,
                'fq': solr_facets,
                'fl': self.solr_fields_en,
                'defType': 'edismax',
                'qf': self.solr_query_fields_en,
                'sort': sort_order,
            }

        for facet in facets.keys():
            if facets[facet] != '':
                facet_terms = facets[facet].split(',')
                quoted_terms = ['"{0}"'.format(item) for item in facet_terms]
                facet_text = '{{!tag=tag_{0}}}{0}:({1})'.format(facet, ' OR '.join(quoted_terms))
                solr_facets.append(facet_text)

        if q != '*':
            if language == 'fr':
                extras.update(self.phrase_xtras_fr)
            elif language == 'en':
                extras.update(self.phrase_xtras_en)

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

    def get(self, request):

        context = dict(LANGUAGE_CODE=request.LANGUAGE_CODE, )
        context["cdts_version"] = settings.CDTS_VERSION
        context["od_en_url"] = settings.OPEN_DATA_EN_URL_BASE
        context["od_fr_url"] = settings.OPEN_DATA_FR_URL_BASE
        context["ati_ds_id"] = settings.BRIEFING_NOTE_DATASET_ID
        context["ati_ds_title_en"] = settings.BRIEFING_NOTE_DATASET_TITLE_EN
        context["ati_ds_title_fr"] = settings.BRIEFING_NOTE_DATASET_TITLE_FR

        # Get any search terms

        search_text = str(request.GET.get('search_text', '')).strip().replace('"', "'")
        # Respect quoted strings
        context['search_text'] = search_text
        search_terms = self.split_with_quotes(search_text)
        if len(search_terms) == 0:
            solr_search_terms = "*"
        elif len(search_terms) == 1:
            solr_search_terms = search_terms
        else:
            solr_search_terms = ' '.join(search_terms)

        # Retrieve search results and transform facets results to python dict

        solr_search_orgs: str = request.GET.get('ati-search-orgs', '')
        solr_search_year: str = request.GET.get('ati-search-year', '')
        solr_search_month: str = request.GET.get('ati-search-month', '')

        context["organizations_selected"] = solr_search_orgs
        context["organizations_selected_list"] = solr_search_orgs.split(',')
        context["year_selected"] = solr_search_year
        context["year_selected_list"] = solr_search_year.split(',')
        context["month_selected"] = solr_search_month
        context["month_selected_list"] = solr_search_month.split(',')

        # Calculate a starting row for the Solr search results. We only retrieve one page at a time

        try:
            page = int(request.GET.get('page', 1))
        except ValueError:
            page = 1
        if page < 1:
            page = 1
        elif page > 10000:  # @magic_number: arbitrary upper range
            page = 10000
        start_row = 10 * (page - 1)

        # Retrieve search sort order

        solr_search_sort = request.GET.get('sort', 'score desc')
        if solr_search_sort not in ['score desc', 'year_i desc', 'year_i asc']:
            solr_search_sort = 'score desc'
        context['sortby'] = solr_search_sort

        if request.LANGUAGE_CODE == 'fr':
            facets_dict = dict(owner_org_fr_s=context['organizations_selected'],
                               year_i=context['year_selected'],
                               month_i=context['month_selected'])
        else:
            facets_dict = dict(owner_org_en_s=context['organizations_selected'],
                               year_i=context['year_selected'],
                               month_i=context['month_selected'])

        search_results = self.solr_query(solr_search_terms, startrow=str(start_row), pagesize='10', facets=facets_dict,
                                         language=request.LANGUAGE_CODE,
                                         sort_order=solr_search_sort)

        context['results'] = search_results        # Set up previous and next page numbers

        pagination = _calc_pagination_range(context['results'], 10, page)
        context['pagination'] = pagination
        context['previous_page'] = (1 if page == 1 else page - 1)
        last_page = (pagination[len(pagination) - 1] if len(pagination) > 0 else 1)
        last_page = (1 if last_page < 1 else last_page)
        context['last_page'] = last_page
        next_page = page + 1
        next_page = (last_page if next_page > last_page else next_page)
        context['next_page'] = next_page
        context['currentpage'] = page

        export_url = "/{0}/ati/export/?{1}".format(request.LANGUAGE_CODE, request.GET.urlencode())
        context['export_url'] = export_url

        if request.LANGUAGE_CODE == 'fr':
            context['org_facets_fr'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_fr_s'])
        else:
            context['org_facets_en'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_en_s'])

        context['month_i'] = _convert_facet_list_to_dict(
            search_results.facets['facet_fields']['month_i'])
        context['year_i'] = _convert_facet_list_to_dict(
            search_results.facets['facet_fields']['year_i'])

        return render(request, "ati_search.html", context)

