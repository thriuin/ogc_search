from django.conf import settings
from django.http import HttpRequest, HttpResponseRedirect, FileResponse
from django.shortcuts import render
from django.views.generic import View
import hashlib
import logging
import os
import search_util
import time

logger = logging.getLogger('ogc_search')


# Create your views here.
class BNSearchView(View):

    def __init__(self):
        super().__init__()
        # French search fields
        self.solr_fields_fr = ("id,tracking_number_s,title_txt_fr,org_sector_fr_s,addressee_fr_s,action_required_fr_s,"
                               "date_received_tdt,month_i,year_i,owner_org_fr_s,additional_information_fr_s")
        self.solr_query_fields_fr = ['owner_org_fr_s^2', 'additional_information_fr_s^3', 'org_sector_fr_s^4',
                                     'title_txt_fr^5', '_text_fr_^0.5', 'action_required_fr_s^0.5',
                                     'tracking_number_s^5']
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
                                     'title_txt_en^5', '_text_en_^0.5', 'action_required_en_s^0.5',
                                     'tracking_number_s^5']
        self.solr_facet_fields_en = ['{!ex=tag_owner_org_en_s}owner_org_en_s',
                                     '{!ex=tag_month_i}month_i',
                                     '{!ex=tag_year_i}year_i',
                                     '{!ex=tag_action_required_en_s}action_required_en_s',
                                     '{!ex=tag_addressee_en_s}addressee_en_s']
        self.solr_hl_fields_en = ['additional_information_en_s', 'title_txt_en', 'org_sector_en_s']

        self.phrase_xtras_fr = {
            'hl': 'on',
            'hl.simple.pre': '<mark>',
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
            'hl.simple.pre': '<mark>',
            'hl.simple.post': '</mark>',
            'hl.method': 'unified',
            'hl.snippets': 10,
            'hl.fl': self.solr_hl_fields_en,
            'hl.preserveMulti': 'true',
            'ps': 10,
            'mm': '3<70%',
            'bq': 'date_received_tdt:[NOW/DAY-2YEAR TO NOW/DAY]',
        }

    def get(self, request):

        context = dict(LANGUAGE_CODE=request.LANGUAGE_CODE, )
        context["cdts_version"] = settings.CDTS_VERSION
        context["od_en_url"] = settings.OPEN_DATA_EN_URL_BASE
        context["od_fr_url"] = settings.OPEN_DATA_FR_URL_BASE
        context["bn_ds_id"] = settings.BRIEFING_NOTE_DATASET_ID
        context["bn_ds_title_en"] = settings.BRIEFING_NOTE_DATASET_TITLE_EN
        context["bn_ds_title_fr"] = settings.BRIEFING_NOTE_DATASET_TITLE_FR
        items_per_page = int(settings.SI_ITEMS_PER_PAGE)

        # Get any search terms

        search_text = str(request.GET.get('search_text', ''))
        # Respect quoted strings
        context['search_text'] = search_text
        search_terms = search_util.split_with_quotes(search_text)
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
        context["organizations_selected_list"] = solr_search_orgs.split('|')
        context["year_selected"] = solr_search_year
        context["year_selected_list"] = solr_search_year.split('|')
        context["month_selected"] = solr_search_month
        context["month_selected_list"] = solr_search_month.split('|')
        context["actions_selected"] = solr_search_ar
        context["actions_selected_list"] = solr_search_ar.split('|')
        context["addressee_selected"] = solr_search_addrs
        context["addressee_selected_list"] = solr_search_addrs.split('|')

        start_row, page = search_util.calc_starting_row(request.GET.get('page', 1))

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

        if request.LANGUAGE_CODE == 'fr':
            search_results = search_util.solr_query(solr_search_terms,
                                                    settings.SOLR_BN,
                                                    self.solr_fields_fr,
                                                    self.solr_query_fields_fr,
                                                    self.solr_facet_fields_fr,
                                                    self.phrase_xtras_fr,
                                                    start_row=str(start_row), pagesize=str(items_per_page),
                                                    facets=facets_dict,
                                                    sort_order=solr_search_sort)
        else:
            search_results = search_util.solr_query(solr_search_terms,
                                                    settings.SOLR_BN,
                                                    self.solr_fields_en,
                                                    self.solr_query_fields_en,
                                                    self.solr_facet_fields_en,
                                                    self.phrase_xtras_en,
                                                    start_row=str(start_row), pagesize=str(items_per_page),
                                                    facets=facets_dict,
                                                    sort_order=solr_search_sort)

        context['results'] = search_results
        export_url = "/{0}/bn/export/?{1}".format(request.LANGUAGE_CODE, request.GET.urlencode())
        context['export_url'] = export_url

        # Set pagination values for the page

        pagination = search_util.calc_pagination_range(context['results'], 10, page)
        context['pagination'] = pagination
        context['previous_page'] = (1 if page == 1 else page - 1)
        last_page = (pagination[len(pagination) - 1] if len(pagination) > 0 else 1)
        last_page = (1 if last_page < 1 else last_page)
        context['last_page'] = last_page
        next_page = page + 1
        next_page = (last_page if next_page > last_page else next_page)
        context['next_page'] = next_page
        context['currentpage'] = page

        if request.LANGUAGE_CODE == 'fr':
            context['org_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_fr_s'])
            context['action_required_fr_s'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['action_required_fr_s'])
            context['addressee_fr_s'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['addressee_fr_s'])
            context['info_msg'] = settings.BRIEF_NOTE_INFO_FR

        else:
            context['org_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_en_s'])
            context['action_required_en_s'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['action_required_en_s'])
            context['addressee_en_s'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['addressee_en_s'])
            context['info_msg'] = settings.BRIEF_NOTE_INFO_EN

        context['month_i'] = search_util.convert_facet_list_to_dict(
            search_results.facets['facet_fields']['month_i'])
        context['year_i'] = search_util.convert_facet_list_to_dict(
            search_results.facets['facet_fields']['year_i'])

        return render(request, "bn_search.html", context)


class BNExportView(View):

    def __init__(self):
        super().__init__()

        self.solr_fields = ("id,tracking_id_s,"
                            "title_en_s,title_fr_s,"
                            "org_sector_en_s,org_sector_fr_s,"
                            "date_received_tdt,"
                            "action_required_en_s,action_required_fr_s,"
                            "addressee_en_s,addressee_fr_s,"
                            "additional_information_en_s,additional_information_fr_s")
        self.solr_query_fields_fr = ['owner_org_fr_s^2', 'additional_information_fr_s^3', 'org_sector_fr_s^4',
                                     'title_txt_fr^5', '_text_fr_^0.5', 'action_required_fr_s^0.5',
                                     'tracking_number_s^5']
        self.solr_query_fields_en = ['owner_org_en_s^2', 'additional_information_en_s^3', 'org_sector_en_s^4',
                                     'title_txt_en^5', '_text_en_^0.5', 'action_required_en_s^0.5',
                                     'tracking_number_s^5']
        self.solr_facet_fields_en = ['{!ex=tag_owner_org_en_s}owner_org_en_s',
                                     '{!ex=tag_month_i}month_i',
                                     '{!ex=tag_year_i}year_i',
                                     '{!ex=tag_action_required_en_s}action_required_en_s',
                                     '{!ex=tag_addressee_en_s}addressee_en_s']
        self.solr_facet_fields_fr = ['{!ex=tag_owner_org_fr_s}owner_org_fr_s',
                                     '{!ex=tag_month_i}month_i',
                                     '{!ex=tag_year_i}year_i',
                                     '{!ex=tag_action_required_fr_s}action_required_fr_s',
                                     '{!ex=tag_addressee_fr_s}addressee_fr_s']
        self.phrase_xtras = {
            'mm': '3<70%',
        }

        self.cache_dir = settings.EXPORT_FILE_CACHE_DIR
        if not os.path.exists(self.cache_dir):
            os.mkdir(self.cache_dir)

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
        search_terms = search_util.split_with_quotes(search_text)
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

        solr_search_facets = self.solr_facet_fields_en
        solr_query_fields = self.solr_query_fields_en
        if request.LANGUAGE_CODE == 'fr':
            facets_dict = dict(owner_org_fr_s=solr_search_orgs,
                               year_i=solr_search_year,
                               month_i=solr_search_month,
                               action_required_fr_s=solr_search_ar,
                               addressee_fr_s=solr_search_addrs)
            solr_search_facets = self.solr_facet_fields_fr
            solr_query_fields = self.solr_query_fields_fr
        else:
            facets_dict = dict(owner_org_en_s=solr_search_orgs,
                               year_i=solr_search_year,
                               month_i=solr_search_month,
                               action_required_en_s=solr_search_ar,
                               addressee_en_s=solr_search_addrs)

        search_results = search_util.solr_query_for_export(solr_search_terms,
                                                           settings.SOLR_BN,
                                                           self.solr_fields,
                                                           solr_query_fields,
                                                           solr_search_facets,
                                                           "id asc",
                                                           facets_dict,
                                                           self.phrase_xtras)

        if search_util.cache_search_results_file(cached_filename=cached_filename, sr=search_results,
                                                 solr_fields=self.solr_fields):
            if settings.EXPORT_FILE_CACHE_URL == "":
                return FileResponse(open(cached_filename, 'rb'), as_attachment=True)
            else:
                return HttpResponseRedirect(settings.EXPORT_FILE_CACHE_URL + "{}.csv".format(hashed_query))

