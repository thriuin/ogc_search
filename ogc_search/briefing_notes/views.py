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

logger = logging.getLogger('ogc_search')


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
class BNSearchView(View):

    def __init__(self):
        super().__init__()
        # French search fields
        self.solr_fields_fr = ("id,tracking_number_s,title_txt_fr,org_sector_fr_s,addressee_fr_s,action_required_fr_s,"
                               "date_received_tdt,month_i,year_i,owner_org_fr_s,additional_information_fr_s")
        self.solr_query_fields_fr = ['owner_org_fr_s^2', 'additional_information_fr_s^3', 'org_sector_fr_s^4',
                                     'title_txt_fr^5', '_text_fr_^0.5', 'action_required_fr_s^0.5']
        self.solr_facet_fields_fr = ['{!ex=tag_owner_org_fr_s}owner_org_fr_s',
                                     '{!ex=tag_month_i}month_i',
                                     '{!ex=tag_year_i}year_i',
                                     '{!ex=tag_action_required_fr_s}action_required_fr_s',
                                     '{!ex=tag_addressee_fr_s}addressee_fr_s']
        self.solr_hl_fields_fr = ['additional_information_fr_s', 'title_txt_fr', 'org_sector_fr_s']

        # English search fields
        self.solr_fields_en = ("id,tracking_number_s,title_txt_en,org_sector_en_s,addressee_en_s,action_required_en_s,"
                               "date_received_tdt,month_i,year_i,owner_org_en_s,additional_information_en_s")
        self.solr_query_fields_en = ['owner_org_en_s^2', 'additional_information_en_s^3', 'org_sector_en_s^4',
                                     'title_txt_en^5', '_text_en_^0.5', 'action_required_en_s^0.5']
        self.solr_facet_fields_en = ['{!ex=tag_owner_org_en_s}owner_org_en_s',
                                     '{!ex=tag_month_i}month_i',
                                     '{!ex=tag_year_i}year_i',
                                     '{!ex=tag_action_required_en_s}action_required_en_s',
                                     '{!ex=tag_addressee_en_s}addressee_en_s']
        self.solr_hl_fields_en = ['additional_information_en_s', 'title_txt_en', 'org_sector_en_s']

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
            'bq': 'date_received_tdt:[NOW/DAY-2YEAR TO NOW/DAY]',
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
            'bq': 'date_received_tdt:[NOW/DAY-2YEAR TO NOW/DAY]',
        }

    @staticmethod
    def split_with_quotes(csv_string):
        # As per https://stackoverflow.com/a/23155180
        return re.findall(r'[^"\s]\S*|".+?"', csv_string)

    def solr_query(self, q, startrow='0', pagesize='10', facets={}, language='en',
                   sort_order='score asc', ids=''):
        solr = pysolr.Solr(settings.SOLR_BN)
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
        context["bn_ds_id"] = settings.BRIEFING_NOTE_DATASET_ID
        context["bn_ds_title_en"] = settings.BRIEFING_NOTE_DATASET_TITLE_EN
        context["bn_ds_title_fr"] = settings.BRIEFING_NOTE_DATASET_TITLE_FR

        solr_search_ids = request.GET.get('ids', '')

        # Get any search terms

        search_text = str(request.GET.get('search_text', ''))
        # Respect quoted strings
        context['search_text'] = search_text
        search_terms = self.split_with_quotes(search_text)
        if len(search_terms) == 0:
            solr_search_terms = "*"
        elif len(search_terms) == 1:
            solr_search_terms = '"{0}"'.format(search_terms)
        else:
            solr_search_terms = ' '.join(search_terms)

        # Retrieve search results and transform facets results to python dict

        solr_search_orgs: str = request.GET.get('bn-search-orgs', '')
        solr_search_year: str = request.GET.get('bn-search-year', '')
        solr_search_month: str = request.GET.get('bn-search-month', '')
        solr_search_ar: str = request.GET.get('bn-search-action', '')
        solr_search_addrs: str = request.GET.get('bn-search-addressee', '')

        context["organizations_selected"] = solr_search_orgs
        context["organizations_selected_list"] = solr_search_orgs.split(',')
        context["year_selected"] = solr_search_year
        context["year_selected_list"] = solr_search_year.split(',')
        context["month_selected"] = solr_search_month
        context["month_selected_list"] = solr_search_month.split(',')
        context["actions_selected"] = solr_search_ar
        context["actions_selected_list"] = solr_search_ar.split(',')
        context["addressee_selected"] = solr_search_addrs
        context["addressee_selected_list"] = solr_search_addrs.split(',')

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
        if solr_search_sort not in ['score desc', 'date_received_tdt desc', 'title_txt_en asc']:
            solr_search_sort = 'score desc'
        context['sortby'] = solr_search_sort

        if request.LANGUAGE_CODE == 'fr':
            facets_dict = dict(owner_org_fr_s=context['organizations_selected'],
                               year_i=context['year_selected'],
                               month_i=context['month_selected'],
                               action_required_fr_s=context['actions_selected'],
                               addressee_fr_s=context['addressee_selected'])
        else:
            facets_dict = dict(owner_org_en_s=context['organizations_selected'],
                               year_i=context['year_selected'],
                               month_i=context['month_selected'],
                               action_required_en_s=context['actions_selected'],
                               addressee_en_s=context['addressee_selected'])

        search_results = self.solr_query(solr_search_terms, startrow=str(start_row), pagesize='10', facets=facets_dict,
                                         language=request.LANGUAGE_CODE,
                                         sort_order=solr_search_sort, ids=solr_search_ids)

        context['results'] = search_results
        export_url = "/{0}/bn/export/?{1}".format(request.LANGUAGE_CODE, request.GET.urlencode())
        context['export_url'] = export_url

        if request.LANGUAGE_CODE == 'fr':
            context['org_facets_fr'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_fr_s'])
            context['action_required_fr_s'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['action_required_fr_s'])
            context['addressee_fr_s'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['addressee_fr_s'])
        else:
            context['org_facets_en'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_en_s'])
            context['action_required_en_s'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['action_required_en_s'])
            context['addressee_en_s'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['addressee_en_s'])

        context['month_i'] = _convert_facet_list_to_dict(
            search_results.facets['facet_fields']['month_i'])
        context['year_i'] = _convert_facet_list_to_dict(
            search_results.facets['facet_fields']['year_i'])

        return render(request, "bn_search.html", context)

class BNExportView(View):

    def __init__(self):
        super().__init__()
        self.solr_fields = ['tracking_id_s, owner_org_en_s, owner_org_fr_s, org_sector_en_s, org_sector_fr_s,'
                            'additional_information_en_s, additional_information_fr_s, date_received_tdt,'
                            'addressee_en_s, addressee_fr_s, action_required_en_s, action_required_fr_s']

        self.solr_query_fields_fr = ['owner_org_fr_s^2', 'additional_information_fr_s^3', 'org_sector_fr_s^4',
                                     'title_txt_fr^5', '_text_fr_^0.5', 'action_required_fr_s^0.5']
        self.solr_query_fields_en = ['owner_org_en_s^2', 'additional_information_en_s^3', 'org_sector_en_s^4',
                                     'title_txt_en^5', '_text_en_^0.5', 'action_required_en_s^0.5']

        self.cache_dir = settings.EXPORT_FILE_CACHE_DIR
        if not os.path.exists(self.cache_dir):
            os.mkdir(self.cache_dir)

    def cache_search_results_file(self, cached_filename: str, sr: pysolr.Results):

        if not os.path.exists(cached_filename):
            with open(cached_filename, 'w', newline='', encoding='utf8') as csvfile:
                cache_writer = csv.writer(csvfile, dialect='excel')
                headers = self.solr_fields[0].split(',')
                headers[0] = u'\N{BOM}' + headers[0]
                cache_writer.writerow(headers)
                for i in sr.docs:
                    try:
                        cache_writer.writerow(i.values())
                    except UnicodeEncodeError:
                        pass
        return True

    @staticmethod
    def split_with_quotes(csv_string):
        return re.findall(r'[^"\s]\S*|".+?"', csv_string)

    def solr_query(self, q, facets={}, language='en', sort_order='date_received_tdt desc', ids=''):

        solr = pysolr.Solr(settings.SOLR_BN, search_handler='/export')
        solr_facets = []
        for facet in facets.keys():
            if facets[facet] != '':
                facet_terms = facets[facet].split(',')
                quoted_terms = ['"{0}"'.format(item) for item in facet_terms]
                facet_text = '{{!tag=tag_{0}}}{0}:({1})'.format(facet, ' OR '.join(quoted_terms))
                solr_facets.append(facet_text)

        if language == 'fr':
            extras = {
                'fq': solr_facets,
                'fl': self.solr_fields,
                'defType': 'edismax',
                'qf': self.solr_query_fields_fr,
                'sort': sort_order,
            }
        else:
            extras = {
                'fq': solr_facets,
                'fl': self.solr_fields,
                'defType': 'edismax',
                'qf': self.solr_query_fields_en,
                'sort': sort_order,
            }
        sr = solr.search(q, **extras)
        return sr

    def get(self, request: HttpRequest):

        # Check to see if a recent cached results exists and return that instead if it exists

        hashed_query = hashlib.sha1(request.GET.urlencode().encode('utf8')).hexdigest()
        cached_filename = os.path.join(self.cache_dir, "{}.csv".format(hashed_query))
        if os.path.exists(cached_filename):
            if time.time() - os.path.getmtime(cached_filename) > 600:
                os.remove(cached_filename)
            else:
                if settings.EXPORT_FILE_CACHE_URL == "":
                    return FileResponse(open(cached_filename, 'rb'), as_attachment=True)
                else:
                    return HttpResponseRedirect(settings.EXPORT_FILE_CACHE_URL + "{}.csv".format(hashed_query))

        # Get any search terms

        search_text = str(request.GET.get('search_text', ''))
        # Respect quoted strings
        search_terms = self.split_with_quotes(search_text)
        if len(search_terms) == 0:
            solr_search_terms = "*"
        elif len(search_terms) == 1:
            solr_search_terms = '"{0}"'.format(search_terms)
        else:
            solr_search_terms = ' '.join(search_terms)

        # Retrieve search results and transform facets results to python dict

        solr_search_orgs: str = request.GET.get('bn-search-orgs', '')
        solr_search_year: str = request.GET.get('bn-search-year', '')
        solr_search_month: str = request.GET.get('bn-search-month', '')
        solr_search_ar: str = request.GET.get('bn-search-action', '')
        solr_search_addrs : str = request.GET.get('bn-search-addressee', '')

        if request.LANGUAGE_CODE == 'fr':
            facets_dict = dict(owner_org_fr_s=solr_search_orgs,
                               year_i=solr_search_year,
                               month_i=solr_search_month,
                               action_required_fr_s=solr_search_ar,
                               addressee_fr_s=solr_search_addrs)
        else:
            facets_dict = dict(owner_org_en_s=solr_search_orgs,
                               year_i=solr_search_year,
                               month_i=solr_search_month,
                               action_required_en_s=solr_search_ar,
                               addressee_en_s=solr_search_addrs)

        search_results = self.solr_query(solr_search_terms, facets=facets_dict,
                                         language=request.LANGUAGE_CODE)

        self.cache_search_results_file(cached_filename, search_results)
        if settings.EXPORT_FILE_CACHE_URL == "":
            return FileResponse(open(cached_filename, 'rb'), as_attachment=True)
        else:
            return HttpResponseRedirect(settings.EXPORT_FILE_CACHE_URL + "{}.csv".format(hashed_query))

