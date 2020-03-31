from django.conf import settings
from django.http import HttpRequest, HttpResponseRedirect, FileResponse
from django.shortcuts import render
from django.views.generic import View
import hashlib
import logging
import os
import search_util
import time
from urlsafe import url_part_escape

logger = logging.getLogger('ogc_search')


def get_user_facet_parameters(request: HttpRequest):
    """
    Retrieve any selected search facets from the HTTP GET request
    :param request:
    :return: dictionary of strings of the accumulated search parameters
    """
    return {
        'solr_search_orgs': request.GET.get('sd-search-orgs', ''),
        'solr_search_status': request.GET.get('sd-status', ''),
        'solr_search_reason': request.GET.get('sd-reaason', ''),
    }


class SDSearchView(View):
    # Suggested Datesets Search Page
    def __init__(self):
        super().__init__()
        # French search fields
        self.solr_fields_fr = ("id,title_fr_txt,owner_org_fr_s,owner_org_title_txt_fr,desc_fr_txt,"
                               "votes,keywords_txt_fr,date_received_dt,date_create_fr_s,status_fr_s,"
                               "subjects_fr_s,reason_fr_s,status_updates_fr_s,date_released_fr_s")
        self.solr_query_fields_fr = ['id', 'owner_org_title_txt_fr', 'desc_fr_txt^3', 'keywords_txt_fr^4',
                                     'status_fr_s', 'subjects_fr_s', 'reason_fr_s', 'title_fr_txt']
        self.solr_facet_fields_fr = ['{!ex=tag_owner_org_fr_s}owner_org_fr_s',
                                     '{!ex=tag_status_fr_s}status_fr_s',
                                     '{!ex=tag_reason_fr_s}reason_fr_s']
        self.solr_hl_fields_fr = ['title_fr_txt', 'owner_org_title_txt_fr', 'desc_fr_txt',
                                  'desc_fr_txt', 'keywords_txt_fr']
        
        # E English earch fields
        self.solr_fields_en = ("id,title_en_txt,owner_org_en_s,owner_org_title_txt_en,desc_en_txt,"
                               "votes,keywords_txt_en,date_received_dt,date_create_en_s,status_en_s,"
                               "subjects_en_s,reason_en_s,status_updates_en_s,date_released_en_s")
        self.solr_query_fields_en = ['id', 'owner_org_title_txt_en', 'desc_en_txt^3', 'keywords_txt_en^4',
                                     'status_en_s', 'subjects_en_s', 'reason_en_s', 'title_en_txt']
        self.solr_facet_fields_en = ['{!ex=tag_owner_org_en_s}owner_org_en_s',
                                     '{!ex=tag_status_en_s}status_en_s',
                                     '{!ex=tag_reason_en_s}reason_en_s']
        self.solr_hl_fields_en = ['title_en_txt', 'owner_org_title_txt_en', 'desc_en_txt',
                                  'desc_en_txt', 'keywords_txt_en']

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
        context["adobe_analytics_url"] = settings.ADOBE_ANALYTICS_URL
        items_per_page = int(settings.OPEN_DATA_ITEMS_PER_PAGE)

        # Allow for, but do not require, a custom alert message
        if hasattr(settings, 'OPEN_DATA_PORTAL_ALERT_BASE'):
            context['od_portal_alert_base'] = settings.OPEN_DATA_PORTAL_ALERT_BASE
        else:
            context['od_portal_alert_base'] = "/data/static/_site_messaging/header_od_ckan."

        # Get any search terms

        solr_search_terms = search_util.get_search_terms(request)
        context['search_text'] = str(request.GET.get('search_text', ''))

        # Retrieve search results and transform facets results to python dict

        solr_search_orgs: str = request.GET.get('sd-search-orgs', '')
        solr_search_status: str = request.GET.get('sd-status', '')
        solr_search_reason: str = request.GET.get('sd-reason', '')
        context["organizations_selected"] = solr_search_orgs
        context["organizations_selected_list"] = solr_search_orgs.split('|')
        context["status_selected"] = solr_search_status
        context["status_selected_list"] = solr_search_status.split('|')
        context["reason_selected"] = solr_search_reason
        context["reason_selected_list"] = solr_search_reason.split('|')
        context["suggest_a_dataset_en"] = settings.SD_SUGGEST_A_DATASET_EN
        context["suggest_a_dataset_fr"] = settings.SD_SUGGEST_A_DATASET_FR

        start_row, page = search_util.calc_starting_row(request.GET.get('page', 1))

        # Retrieve search sort order
        solr_search_sort = request.GET.get('sort', 'score desc')
        if solr_search_sort not in ['score desc', 'date_received_dt desc', 'date_recieved_dt asc']:
            solr_search_sort = 'score desc'
        context['sortby'] = solr_search_sort

        if request.LANGUAGE_CODE == 'fr':
            facets_dict = dict(owner_org_fr_s=context['organizations_selected'],
                               status_fr_s=context['status_selected'],
                               reason_fr_s=context['reason_selected'])
        else:
            facets_dict = dict(owner_org_en_s=context['organizations_selected'],
                               status_en_s=context['status_selected'],
                               reason_en_s=context['reason_selected'])

        if request.LANGUAGE_CODE == 'fr':
            search_results = search_util.solr_query(solr_search_terms,
                                                    settings.SOLR_SD,
                                                    self.solr_fields_fr,
                                                    self.solr_query_fields_fr,
                                                    self.solr_facet_fields_fr,
                                                    self.phrase_xtras_fr,
                                                    start_row=str(start_row), pagesize=str(items_per_page),
                                                    facets=facets_dict,
                                                    sort_order=solr_search_sort)
        else:
            search_results = search_util.solr_query(solr_search_terms,
                                                    settings.SOLR_SD,
                                                    self.solr_fields_en,
                                                    self.solr_query_fields_en,
                                                    self.solr_facet_fields_en,
                                                    self.phrase_xtras_en,
                                                    start_row=str(start_row), pagesize=str(items_per_page),
                                                    facets=facets_dict,
                                                    sort_order=solr_search_sort)

        context['results'] = search_results
        export_url = "/{0}/sd/export/?{1}".format(request.LANGUAGE_CODE, request.GET.urlencode())
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
        
        if request.LANGUAGE_CODE == 'fr':
            context['org_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_fr_s'])
            context['status_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['status_fr_s'])
            context['reason_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['reason_fr_s'])
        else:
            context['org_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_en_s'])
            context['status_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['status_en_s'])
            context['reason_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['reason_en_s'])
            
        return render(request, "sd_search.html", context)


class SDDatasetView(SDSearchView):

    def __init__(self):
        super().__init__()
        self.phrase_xtras_en = {}
        self.phrase_xtras_fr = {}

    def get(self, request, slug=''):
        context = dict(LANGUAGE_CODE=request.LANGUAGE_CODE, )
        context["cdts_version"] = settings.CDTS_VERSION
        context["adobe_analytics_url"] = settings.ADOBE_ANALYTICS_URL
        context["slug"] = slug
        context["comments_base_en"] = settings.SD_COMMENTS_BASE_EN
        context["comments_base_fr"] = settings.SD_COMMENTS_BASE_FR

        # Allow for, but do not require, a custom alert message
        if hasattr(settings, 'OPEN_DATA_PORTAL_ALERT_BASE'):
            context['od_portal_alert_base'] = settings.OPEN_DATA_PORTAL_ALERT_BASE
        else:
            context['od_portal_alert_base'] = "/data/static/_site_messaging/header_od_ckan."
        solr_search_terms = 'id:"{0}"'.format(context["slug"])
        if request.LANGUAGE_CODE == 'fr':
            search_results = search_util.solr_query(solr_search_terms,
                                                    settings.SOLR_SD,
                                                    self.solr_fields_fr,
                                                    self.solr_query_fields_fr,
                                                    self.solr_facet_fields_fr,
                                                    self.phrase_xtras_fr)
        else:
            search_results = search_util.solr_query(solr_search_terms,
                                                    settings.SOLR_SD,
                                                    self.solr_fields_en,
                                                    self.solr_query_fields_en,
                                                    self.solr_facet_fields_en,
                                                    self.phrase_xtras_en)
        context['results'] = search_results
        if len(search_results.docs) >= 0:
            context['id'] = slug
            return render(request, "sd_dataset.html", context)
        else:
            return render(request, 'no_record_found.html', context, status=404)


class SDExportView(SDSearchView):

    def __init__(self):
        super().__init__()
        self.solr_fields_fr = ("id,title_fr_s,owner_org_fr_s,desc_fr_s,"
                               "votes,keywords_fr_s,date_received_dt,date_create_fr_s,status_fr_s,"
                               "subjects_fr_s,reason_fr_s,status_updates_export_fr_s,date_released_fr_s")
        self.solr_fields_en = ("id,title_en_s,owner_org_en_s,desc_en_s,"
                               "votes,keywords_en_s,date_received_dt,date_create_en_s,status_en_s,"
                               "subjects_en_s,reason_en_s,status_updates_export_en_s,date_released_en_s")

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
                               status_fr_s=params['solr_search_status'],
                               reason_fr_s=params['solr_search_reason'])
            solr_fields = self.solr_fields_fr
            solr_search_facets = self.solr_facet_fields_fr
            solr_query_fields = self.solr_query_fields_fr
        else:
            facets_dict = dict(owner_org_en_s=params['solr_search_orgs'],
                               status_en_s=params['solr_search_status'],
                               reason_en_s=params['solr_search_reason'])
            solr_fields = self.solr_fields_en
            solr_search_facets = self.solr_facet_fields_en
            solr_query_fields = self.solr_query_fields_en

        search_results = search_util.solr_query_for_export(solr_search_terms,
                                                           settings.SOLR_SD,
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
