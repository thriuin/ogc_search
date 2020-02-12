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


class NAPSearchView(View):

    def __init__(self):
        super().__init__()

        # English search fields
        items_per_page = int(settings.SI_ITEMS_PER_PAGE)

        self.solr_fields_en = ("id,reporting_period_s,due_date_s,"
                               "owner_org_en_s,owner_org_title_txt_en,"
                               "indicators_en_s,indicator_txt_en,ind_full_text_en_s,ind_full_text_en_s,"
                               "milestone_en_s,milestone_txt_en,"
                               "progress_en_s,progress_txt_en,"
                               "evidence_en_s,evidence_txt_en,"
                               "challenges_en_s,challenges_txt_en,"
                               "commitment_nap_url_en_s,"
                               "ind_full_text_en_s,"
                               "milestone_full_text_en_s,"
                               "cmt_url_en_s,"
                               "commitments_en_s,commitment_txt_en,"
                               "status_en_s,"
                               "reporting_period_s")
        self.solr_query_fields_en = ['progress_txt_en^2', 'evidence_txt_en^2', 'indicator_txt_en^2', 'milestone_txt_en']
        self.solr_facet_fields_en = ['{!ex=tag_owner_org_en_s}owner_org_en_s',
                                     '{!ex=tag_commitments_en_s}commitments_en_s',
                                     '{!ex=tag_milestone_en_s}milestone_en_s',
                                     '{!ex=tag_status_en_s}status_en_s',
                                     '{!ex=tag_reporting_period_s}reporting_period_s',
                                     '{!ex=tag_due_date_s}due_date_s']
        self.solr_hl_fields_en = ['indicator_txt_en', 'milestone_txt_en', 'progress_txt_en', 'evidence_txt_en',
                                  'challenges_txt_en']
        self.phrase_xtras_en = {
            'hl': 'on',
            'hl.simple.pre': '<mark>',
            'hl.simple.post': '</mark>',
            'hl.method': 'unified',
            'hl.snippets': items_per_page,
            'hl.fl': self.solr_hl_fields_en,
            'hl.preserveMulti': 'true',
            'ps': items_per_page,
            'mm': '3<70%',
        }

        self.solr_fields_fr = ("id,reporting_period_s,due_date_s,"
                               "owner_org_fr_s,owner_org_title_txt_fr,"
                               "indicators_fr_s,indicator_txt_fr,ind_full_text_fr_s,ind_full_text_fr_s,"
                               "milestone_fr_s,milestone_txt_fr,"
                               "progress_fr_s,progress_txt_fr,"
                               "evidence_fr_s,evidence_txt_fr,"
                               "challenges_fr_s,challenges_txt_fr,"
                               "commitment_nap_url_fr_s,"
                               "ind_full_text_fr_s,"
                               "milestone_full_text_fr_s,"
                               "cmt_url_fr_s,"
                               "commitments_fr_s,commitment_txt_fr,"
                               "status_fr_s,"
                               "reporting_period_s")
        self.solr_query_fields_fr = ['progress_txt_fr^2', 'evidence_txt_fr^2', 'indicator_txt_fr^2', 'milestone_txt_fr']
        self.solr_facet_fields_fr = ['{!ex=tag_owner_org_fr_s}owner_org_fr_s',
                                     '{!ex=tag_commitments_fr_s}commitments_fr_s',
                                     '{!ex=tag_milestone_fr_s}milestone_fr_s',
                                     '{!ex=tag_status_fr_s}status_fr_s',
                                     '{!ex=tag_reporting_period_s}reporting_period_s',
                                     '{!ex=tag_due_date_s}due_date_s']
        self.solr_hl_fields_fr = ['indicator_txt_fr', 'milestone_txt_fr', 'progress_txt_fr', 'evidence_txt_fr',
                                  'challenges_txt_fr']
        self.phrase_xtras_fr = {
            'hl': 'on',
            'hl.simple.pre': '<mark>',
            'hl.simple.post': '</mark>',
            'hl.method': 'unified',
            'hl.snippets': items_per_page,
            'hl.fl': self.solr_hl_fields_fr,
            'hl.preserveMulti': 'true',
            'ps': items_per_page,
            'mm': '3<70%'
        }

    def get(self, request):
        context = dict(LANGUAGE_CODE=request.LANGUAGE_CODE, )
        context["cdts_version"] = settings.CDTS_VERSION
        context["od_en_url"] = settings.OPEN_DATA_EN_URL_BASE
        context["od_fr_url"] = settings.OPEN_DATA_FR_URL_BASE
        context["oc_en_url"] = settings.OPEN_CANADA_EN_URL_BASE
        context["oc_fr_url"] = settings.OPEN_CANADA_FR_URL_BASE
        context["nap_ds_id"] = settings.NAP_DATASET_ID
        context["nap_ds_title_en"] = settings.NAP_DATASET_TITLE_EN
        context["nap_ds_title_fr"] = settings.NAP_DATASET_TITLE_FR
        context["adobe_analytics_url"] = settings.ADOBE_ANALYTICS_URL

        # Get any search terms
        solr_search_terms = search_util.get_search_terms(request)
        context['search_text'] = str(request.GET.get('search_text', ''))

        items_per_page = int(settings.SI_ITEMS_PER_PAGE)

        # Retrieve search results and transform facets results to python dict

        solr_search_orgs: str = request.GET.get('ap-search-orgs', '')
        solr_search_periods: str = request.GET.get('ap-reporting-period', '')
        solr_search_commitments: str = request.GET.get('ap-commitment', '')
        solr_search_milestones: str = request.GET.get('ap-milestone', '')
        solr_search_status: str = request.GET.get('ap-status', '')
        solr_search_due_dates: str = request.GET.get('ap-due-date', '')

        context["organizations_selected"] = solr_search_orgs
        context["organizations_selected_list"] = solr_search_orgs.split('|')
        context["periods_selected"] = solr_search_periods
        context["periods_selected_list"] = solr_search_periods.split('|')
        context["commitments_selected"] = solr_search_commitments
        context["commitments_selected_list"] = solr_search_commitments.split('|')
        context["milestone_selected"] = solr_search_milestones
        context["milestone_selected_list"] = solr_search_milestones.split('|')
        context["statuses_selected"] = solr_search_status
        context["statuses_selected_list"] = solr_search_status.split('|')
        context["due_dates_selected"] = solr_search_due_dates
        context["due_dates_selected_list"] = solr_search_due_dates.split('|')

        start_row, page = search_util.calc_starting_row(request.GET.get('page', 1), items_per_page)

        solr_search_sort = request.GET.get('sort', 'score desc')
        if request.LANGUAGE_CODE == 'fr':
            if solr_search_sort not in ['score desc', 'reporting_period_s desc']:
                solr_search_sort = 'score desc'
        else:
            if solr_search_sort not in ['score desc', 'reporting_period_s desc']:
                solr_search_sort = 'score desc'
        context['sortby'] = solr_search_sort

        if request.LANGUAGE_CODE == 'fr':
            facets_dict = dict(owner_org_fr_s=context['organizations_selected'],
                               reporting_period_s=context['periods_selected'],
                               commitments_fr_s=context['commitments_selected'],
                               milestone_fr_s=context['milestone_selected'],
                               status_fr_s=context['statuses_selected'],
                               due_date_s=context['due_dates_selected'],
                               )
        else:
            facets_dict = dict(owner_org_en_s=context['organizations_selected'],
                               reporting_period_s=context['periods_selected'],
                               commitments_en_s=context['commitments_selected'],
                               milestone_en_s=context['milestone_selected'],
                               status_en_s=context['statuses_selected'],
                               due_date_s=context['due_dates_selected'],
                               )

        if request.LANGUAGE_CODE == 'fr':
            search_results = search_util.solr_query(solr_search_terms,
                                                    settings.SOLR_NAP,
                                                    self.solr_fields_fr,
                                                    self.solr_query_fields_fr,
                                                    self.solr_facet_fields_fr,
                                                    self.phrase_xtras_fr,
                                                    start_row=str(start_row), pagesize=str(items_per_page),
                                                    facets=facets_dict,
                                                    sort_order=solr_search_sort)
        else:
            search_results = search_util.solr_query(solr_search_terms,
                                                    settings.SOLR_NAP,
                                                    self.solr_fields_en,
                                                    self.solr_query_fields_en,
                                                    self.solr_facet_fields_en,
                                                    self.phrase_xtras_en,
                                                    start_row=str(start_row), pagesize=str(items_per_page),
                                                    facets=facets_dict,
                                                    sort_order=solr_search_sort)

        context['results'] = search_results
        export_url = "/{0}/nap/export/?{1}".format(request.LANGUAGE_CODE, request.GET.urlencode())
        context['export_url'] = export_url

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

        # Facet results
        context['reporting_periods_facets'] = search_util.convert_facet_list_to_dict(
            search_results.facets['facet_fields']['reporting_period_s'])
        context['due_date_facets_en'] = search_util.convert_facet_list_to_dict(
            search_results.facets['facet_fields']['due_date_s'])
        if request.LANGUAGE_CODE == 'fr':
            context['org_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_fr_s'])
            context['commitment_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['commitments_fr_s'])
            context['milestone_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['milestone_fr_s'])
            context['status_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['status_fr_s'])
        else:
            context['org_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_en_s'])
            context['commitment_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['commitments_en_s'])
            context['milestone_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['milestone_en_s'])
            context['status_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['status_en_s'])

        return render(request, "nap_search.html", context)


class NAPExportView(View):

    def __init__(self):
        super().__init__()

        self.solr_fields = ("id,"
                            "reporting_period_s,"
                            "due_date_s,"
                            "owner_org_en_s,"
                            "owner_org_fr_s,"
                            "indicators_en_s,indicators_fr_s,"
                            "ind_full_text_en_s,ind_full_text_fr_s,"
                            "milestone_en_s,milestone_fr_s,"
                            "progress_en_s,progress_fr_s,"
                            "evidence_en_s,evidence_fr_s,"
                            "challenges_en_s,challenges_fr_s,"
                            "commitment_nap_url_en_s,commitment_nap_url_fr_s,"
                            "ind_full_text_en_s,ind_full_text_fr_s,"
                            "milestone_full_text_en_s,milestone_full_text_fr_s,"
                            "cmt_url_en_s,cmt_url_fr_s,"
                            "commitments_en_s,commitments_fr_s,"
                            "status_en_s,status_fr_s,"
                            "reporting_period_s")
        self.solr_query_fields_en = ['progress_txt_en^2', 'evidence_txt_en^2', 'indicator_txt_en^2', 'milestone_txt_en',
                                                                                                     '_text_en_']
        self.solr_query_fields_fr = ['progress_txt_fr^2', 'evidence_txt_fr^2', 'indicator_txt_fr^2', 'milestone_txt_fr',
                                                                                                     '_text_fr_']
        self.solr_facet_fields_en = ['{!ex=tag_owner_org_en_s}owner_org_en_s',
                                     '{!ex=tag_commitments_en_s}commitments_en_s',
                                     '{!ex=tag_milestone_en_s}milestone_en_s',
                                     '{!ex=tag_status_en_s}status_en_s',
                                     '{!ex=tag_reporting_period_s}reporting_period_s',
                                     '{!ex=tag_due_date_s}due_date_s']
        self.solr_facet_fields_fr = ['{!ex=tag_owner_org_fr_s}owner_org_fr_s',
                                     '{!ex=tag_commitments_fr_s}commitments_fr_s',
                                     '{!ex=tag_milestone_fr_s}milestone_fr_s',
                                     '{!ex=tag_status_fr_s}status_fr_s',
                                     '{!ex=tag_reporting_period_s}reporting_period_s',
                                     '{!ex=tag_due_date_s}due_date_s']
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

        solr_search_terms = search_util.get_search_terms(request)

        # Retrieve search results and transform facets results to python dict
        solr_search_orgs: str = request.GET.get('ap-search-orgs', '')
        solr_search_periods: str = request.GET.get('ap-reporting-period', '')
        solr_search_commitments: str = request.GET.get('ap-commitment', '')
        solr_search_milestones: str = request.GET.get('ap-milestone', '')
        solr_search_status: str = request.GET.get('ap-status', '')
        solr_search_due_dates: str = request.GET.get('ap-due-date', '')

        solr_search_facets = self.solr_facet_fields_en
        if request.LANGUAGE_CODE == 'fr':
            facets_dict = dict(owner_org_fr_s=solr_search_orgs,
                               reporting_period_s=solr_search_periods,
                               commitments_fr_s=solr_search_commitments,
                               milestone_fr_s=solr_search_milestones,
                               status_fr_s=solr_search_status,
                               due_date_s=solr_search_due_dates,
                               )
        else:
            facets_dict = dict(owner_org_en_s=solr_search_orgs,
                               reporting_period_s=solr_search_periods,
                               commitments_en_s=solr_search_commitments,
                               milestone_en_s=solr_search_milestones,
                               status_en_s=solr_search_status,
                               due_date_s=solr_search_due_dates,
                               )

        search_results = search_util.solr_query_for_export(solr_search_terms,
                                                           settings.SOLR_NAP,
                                                           self.solr_fields,
                                                           self.solr_query_fields_en,
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

