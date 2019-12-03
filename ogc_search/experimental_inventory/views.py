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


def get_user_facet_parameters(request: HttpRequest):
    """
    Retrieve any selected search facets from the HTTP GET request
    :param request:
    :return: dictionary of strings of the accumulated search parameters
    """
    return {
        'solr_search_orgs': request.GET.get('ei-search-orgs', ''),
        'solr_search_area': request.GET.get('ei-area', ''),
        'solr_search_method': request.GET.get('ei-method', ''),
        'solr_search_status': request.GET.get('ei-status', ''),
    }


class EISearchView(View):
    # Example Search Page
    def __init__(self):
        super().__init__()

        # Fields to be returned by the Solr query, English and French Versions
        self.solr_fields_en = ("id,ref_number_s,"
                               "titre_du_projet_txt_en,"
                               "question_de_recherche_txt_en,"
                               "project_summary_txt_en,"
                               "last_updated_dt,last_updated_en_s,"
                               "experimental_area_en_s,"
                               "research_method_en_s,"
                               "status_en_s,"
                               "report_to_txt_en,"
                               "info_supplementaire_txt_en,"
                               "owner_org_en_s")
        self.solr_fields_fr = ("id,ref_number_s,"
                               "titre_du_projet_txt_fr,"
                               "question_de_recherche_txt_fr,"
                               "project_summary_txt_fr,"
                               "last_updated_dt,last_updated_fr_s,"
                               "experimental_area_fr_s,"
                               "research_method_fr_s,"
                               "status_fr_s,"
                               "report_to_txt_fr,"
                               "info_supplementaire_txt_fr,"
                               "owner_org_fr_s")
        
        # Fields to be searched in the Solr query. Fields can be weighted to indicate which are more relevant for
        # searching. 
        self.solr_query_fields_en = ['ref_number_s^5',
                                     'titre_du_projet_txt_en^4',
                                     'question_de_recherche_txt_en^3',
                                     'project_summary_txt_en^3',
                                     'last_updated_dt,last_updated_en_s',
                                     'experimental_area_en_s',
                                     'research_method_en_s',
                                     'status_en_s',
                                     'report_to_txt_en^2',
                                     'info_supplementaire_txt_en^3',
                                     'owner_org_en_s'
                                     ]
        self.solr_query_fields_fr = ['ref_number_s^5',
                                     'titre_du_projet_txt_fr^4',
                                     'question_de_recherche_txt_fr^3',
                                     'project_summary_txt_fr^3',
                                     'last_updated_dt,last_updated_fr_s',
                                     'experimental_area_fr_s',
                                     'research_method_fr_s',
                                     'status_fr_s',
                                     'report_to_txt_fr^2',
                                     'info_supplementaire_txt_fr^3',
                                     'owner_org_fr_s'
                                     ]
        
        # These fields are search facets
        self.solr_facet_fields_en = ['{!ex=tag_owner_org_en_s}owner_org_en_s',
                                     '{!ex=tag_experimental_area_en_s}experimental_area_en_s',
                                     '{!ex=tag_research_method_en_s}research_method_en_s',
                                     '{!ex=tag_status_en_s}status_en_s']
        self.solr_facet_fields_fr = ['{!ex=tag_owner_org_fr_s}owner_org_fr_s',
                                     '{!ex=tag_experimental_area_fr_s}experimental_area_fr_s',
                                     '{!ex=tag_research_method_fr_s}research_method_fr_s',
                                     '{!ex=tag_status_fr_s}status_fr_s']
        
        # These fields will have search hit high-lighting applied
        self.solr_hl_fields_en = ['titre_du_projet_txt_en', 'question_de_recherche_txt_en', 
                                  'project_summary_txt_en', 'report_to_txt_en', 'info_supplementaire_txt_en']
        self.solr_hl_fields_fr = ['titre_du_projet_txt_fr', 'question_de_recherche_txt_fr', 
                                  'project_summary_txt_fr', 'report_to_txt_fr', 'info_supplementaire_txt_fr']
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
        }


    def get(self, request):

        context = dict(LANGUAGE_CODE=request.LANGUAGE_CODE, )
        context["cdts_version"] = settings.CDTS_VERSION
        context["od_en_url"] = settings.OPEN_DATA_EN_URL_BASE
        context["od_fr_url"] = settings.OPEN_DATA_FR_URL_BASE
        context["ei_ds_id"] = settings.EI_DATASET_ID
        context["ei_ds_title_en"] = settings.EI_DATASET_TITLE_EN
        context["ei_ds_title_fr"] = settings.EI_DATASET_TITLE_FR
        context["adobe_analytics_url"] = settings.ADOBE_ANALYTICS_URL
        if request.LANGUAGE_CODE == 'fr':
            context['about_msg'] = settings.EI_ABOUT_FR
        else:
            context['about_msg'] = settings.EI_ABOUT_EN
        # Get any search terms
        solr_search_terms = search_util.get_search_terms(request)
        context['search_text'] = str(request.GET.get('search_text', ''))
        items_per_page = 15

        # Retrieve search sort order
        solr_search_sort = request.GET.get('sort', 'score desc')
        if solr_search_sort not in ['score desc', 'contract_delivery_s desc', 'contract_value_f desc']:
            solr_search_sort = 'score desc'
        context['sortby'] = solr_search_sort

        # Get current page
        start_row, page = search_util.calc_starting_row(request.GET.get('page', 1))

        # Retrieve any selected search facets and convert to lists, and create a facets dictionary
        solr_area: str = request.GET.get('ei-area', '')
        solr_method: str = request.GET.get('ei-method', '')
        solr_status: str = request.GET.get('ei-status', '')
        solr_search_orgs: str = request.GET.get('ei-search-orgs', '')
        context['area_selected'] = solr_area
        context['area_selected_list'] = solr_area.split('|')
        context['method_selected'] = solr_method
        context['method_selected_list'] = solr_method.split('|')
        context['status_selected'] = solr_status
        context['status_selected_list'] = solr_status.split('|')
        context["organizations_selected"] = solr_search_orgs
        context["organizations_selected_list"] = solr_search_orgs.split('|')

        if request.LANGUAGE_CODE == 'fr':
            facets_dict = dict(owner_org_fr_s=solr_search_orgs,
                               experimental_area_fr_s=solr_area,
                               research_method_fr_s=solr_method,
                               status_fr_s=solr_status)
        else:
            facets_dict = dict(owner_org_en_s=solr_search_orgs,
                               experimental_area_en_s=solr_area,
                               research_method_en_s=solr_method,
                               status_en_s=solr_status)

        # Query Solr
        if request.LANGUAGE_CODE == 'fr':
            search_results = search_util.solr_query(solr_search_terms,
                                                    settings.SOLR_EI,
                                                    self.solr_fields_fr,
                                                    self.solr_query_fields_fr,
                                                    self.solr_facet_fields_fr,
                                                    self.phrase_xtras_fr,
                                                    start_row=str(start_row), pagesize=str(items_per_page),
                                                    facets=facets_dict,
                                                    sort_order=solr_search_sort,
                                                    facet_limit=200)
        else:
            search_results = search_util.solr_query(solr_search_terms,
                                                    settings.SOLR_EI,
                                                    self.solr_fields_en,
                                                    self.solr_query_fields_en,
                                                    self.solr_facet_fields_en,
                                                    self.phrase_xtras_en,
                                                    start_row=str(start_row), pagesize=str(items_per_page),
                                                    facets=facets_dict,
                                                    sort_order=solr_search_sort,
                                                    facet_limit=200)

        context['results'] = search_results
        export_url = "/{0}/ei/export/?{1}".format(request.LANGUAGE_CODE, request.GET.urlencode())
        context['export_url'] = export_url

        # Set pagination values for the page
        pagination = search_util.calc_pagination_range(context['results'], items_per_page, page)
        context['pagination'] = pagination
        context['previous_page'] = (1 if page == 1 else page - 1)
        last_page = (pagination[len(pagination) - 1] if len(pagination) > 0 else 1)
        last_page = (1 if last_page < 1 else last_page)
        context['last_page'] = last_page
        next_page = page + 1
        next_page = (last_page if next_page > last_page else next_page)
        context['next_page'] = next_page
        context['currentpage'] = page

        # Set search result facets results
        if request.LANGUAGE_CODE == 'fr':
            context['experimental_area_fr_s'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['experimental_area_fr_s'])
            context['research_method_fr_s'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['research_method_fr_s'])
            context['status_fr_s'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['status_fr_s'])
            context['owner_org_fr_s'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_fr_s'])
        else:
            context['experimental_area_en_s'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['experimental_area_en_s'])
            context['research_method_en_s'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['research_method_en_s'])
            context['status_en_s'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['status_en_s'])
            context['owner_org_en_s'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_en_s'])

        return render(request, "ei_search.html", context)


class EIExperimentView(EISearchView):

    def __init__(self):
        super().__init__()
        self.phrase_xtras_en = {}
        self.phrase_xtras_fr = {}

    def get(self, request, slug=''):
        context = dict(LANGUAGE_CODE=request.LANGUAGE_CODE, )
        context["cdts_version"] = settings.CDTS_VERSION
        context["adobe_analytics_url"] = settings.ADOBE_ANALYTICS_URL
        context["slug"] = slug
        solr_search_terms = 'id:"{0}"'.format(slug)
        if request.LANGUAGE_CODE == 'fr':
            search_results = search_util.solr_query(solr_search_terms,
                                                    settings.SOLR_EI,
                                                    self.solr_fields_fr,
                                                    self.solr_query_fields_fr,
                                                    self.solr_facet_fields_fr,
                                                    self.phrase_xtras_fr)
        else:
            search_results = search_util.solr_query(solr_search_terms,
                                                    settings.SOLR_EI,
                                                    self.solr_fields_en,
                                                    self.solr_query_fields_en,
                                                    self.solr_facet_fields_en,
                                                    self.phrase_xtras_en)
        context['results'] = search_results
        if len(search_results.docs) > 0:
            context['ref_number_s'] = slug
            return render(request, "experiment.html", context)
        else:
            return render(request, 'no_record_found.html', context, status=404)


class EIExportView(EISearchView):
    """
    A view for downloading a simple CSV containing a subset of the fields from the Search View.
    """

    def __init__(self):
        super().__init__()
        self.solr_fields_en = ("ref_number_s,"
                               "titre_du_projet_en_s,"
                               "question_de_recherche_en_s,"
                               "project_summary_en_s,"
                               "last_updated_en_s,"
                               "experimental_area_en_s,"
                               "research_method_en_s,"
                               "status_en_s,"
                               "report_to_en_s,"
                               "info_supplementaire_en_s,"
                               "owner_org_en_s")
        self.solr_fields_fr = ("ref_number_s,"
                               "titre_du_projet_fr_s,"
                               "question_de_recherche_fr_s,"
                               "project_summary_fr_s,"
                               "last_updated_fr_s,"
                               "experimental_area_fr_s,"
                               "research_method_fr_s,"
                               "status_fr_s,"
                               "report_to_fr_s,"
                               "info_supplementaire_fr_s,"
                               "owner_org_fr_s")
        self.phrase_xtras = {
            'mm': '3<70%',
        }
        self.cache_dir = settings.EXPORT_FILE_CACHE_DIR
        if not os.path.exists(self.cache_dir):
            os.mkdir(self.cache_dir)
            
    def get(self, request: HttpRequest):

        # Check to see if a recent cached results exists and return that instead if it exists
        hashed_query = hashlib.sha1(request.GET.urlencode().encode('utf8')).hexdigest()
        cached_filename = os.path.join(self.cache_dir, "{}_{}.csv".format(hashed_query, request.LANGUAGE_CODE))
        if os.path.exists(cached_filename):
            if time.time() - os.path.getmtime(cached_filename) > 600:
                os.remove(cached_filename)
            else:
                if settings.EXPORT_FILE_CACHE_URL == "":
                    return FileResponse(open(cached_filename, 'rb'), as_attachment=True)
                else:
                    return HttpResponseRedirect(settings.EXPORT_FILE_CACHE_URL + "{}.csv".format(hashed_query))

        # Retrieve any selected search facets
        params = get_user_facet_parameters(request)

        solr_search_terms = search_util.get_search_terms(request)

        if request.LANGUAGE_CODE == 'fr':
            facets_dict = dict(owner_org_fr_s=params['solr_search_orgs'],
                               experimental_area_fr_s=params['solr_search_area'],
                               research_method_fr_s=params['solr_search_method'],
                               status_fr_s=params['solr_search_status'])
            solr_fields = self.solr_fields_fr
            solr_search_facets = self.solr_facet_fields_fr
            solr_query_fields = self.solr_query_fields_fr
        else:
            facets_dict = dict(owner_org_en_s=params['solr_search_orgs'],
                               experimental_area_en_s=params['solr_search_area'],
                               research_method_en_s=params['solr_search_method'],
                               status_en_s=params['solr_search_status'])

            solr_fields = self.solr_fields_en
            solr_search_facets = self.solr_facet_fields_en
            solr_query_fields = self.solr_query_fields_en

        search_results = search_util.solr_query_for_export(solr_search_terms,
                                                           settings.SOLR_EI,
                                                           solr_fields,
                                                           solr_query_fields,
                                                           solr_search_facets,
                                                           "id asc",
                                                           facets_dict,
                                                           self.phrase_xtras)

        if search_util.cache_search_results_file(cached_filename=cached_filename, sr=search_results,
                                                 solr_fields=solr_fields):
            if settings.EXPORT_FILE_CACHE_URL == "":
                return FileResponse(open(cached_filename, 'rb'), as_attachment=True)
            else:
                return HttpResponseRedirect(settings.EXPORT_FILE_CACHE_URL + "{}.csv".format(hashed_query))