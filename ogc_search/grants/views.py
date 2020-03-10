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


class GCSearchView(View):
    # Grants and Contributions Search Page
    def __init__(self):
        super().__init__()
        # French search fields
        self.solr_fields_fr = ("id,ref_number_s,ref_number_txt_ws,"
                               "agreement_type_fr_s,"
                               "recipient_country_fr_s,"
                               "agreement_value_range_fr_s,"
                               "year_i,"
                               "owner_org_fr_s,"
                               "amendment_number_s,agreement_number_ws," 
                               "amendment_date_s,amendment_date_txt,"
                               "recipient_business_number_s,recipient_business_number_txt,"
                               "recipient_legal_name_txt_fr,recipient_type_fr_s,"
                               "recipient_operating_name_txt_fr,research_organization_name_txt_fr,"
                               "recipient_province_fr_s,recipient_province_txt_fr,"
                               "recipient_city_fr_s,recipient_city_txt_fr,"
                               "recipient_postal_code_txt,"
                               "federal_riding_name_txt_fr,"
                               "federal_riding_number_s,federal_riding_number_txt,"
                               "program_name_txt_fr,program_purpose_txt_fr,agreement_number_s,"
                               "agreement_title_txt_fr,agreement_value_fr_txt_ws,agreement_value_fs,agreement_value_fr_s,"
                               "foreign_currency_type_fr_s,foreign_currency_value_s,"
                               "agreement_start_date_s,agreement_end_date_s,agreement_type_fr_s,"
                               "coverage_txt_fr,description_txt_fr,"
                               "naics_identifier_s,naics_identifier_txt,"
                               "expected_results_txt_fr,additional_information_txt_fr,"
                               "report_type_fr_s,nil_report_b,quarter_s,fiscal_year_s"
                               )
        self.solr_query_fields_fr = ['id', 'owner_org_fr_s^2',  'ref_number_txt_ws', 'recipient_country_fr_s',
                                     'amendment_date_s', 'recipient_business_number_s', 'recipient_legal_name_txt_fr',
                                     'recipient_operating_name_txt_fr', 'recipient_province_fr_s',
                                     'recipient_city_fr_s', 'recipient_postal_code_txt',
                                     'federal_riding_name_txt_fr',
                                     'program_name_txt_fr', 'program_purpose_txt_fr',
                                     'agreement_title_txt_fr',
                                     'agreement_value_fr_txt_ws', 'agreement_value_fr_s',
                                     'agreement_number_s', 'agreement_number_ws',
                                     'foreign_currency_type_fr_s', 'foreign_currency_value_s',
                                     'coverage_txt_fr', 'description_txt_fr',
                                     'naics_identifier_s',
                                     'expected_results_txt_fr', 'additional_information_txt_fr']
        self.solr_facet_fields_fr = ['{!ex=tag_owner_org_fr_s}owner_org_fr_s',
                                     '{!ex=tag_agreement_type_fr_s}agreement_type_fr_s',
                                     '{!ex=tag_year_i}year_i',
                                     '{!ex=tag_report_type_fr_s}report_type_fr_s',
                                     '{!ex=tag_agreement_value_range_fr_s}agreement_value_range_fr_s']
        self.solr_hl_fields_fr = ['amendment_date_txt', 'recipient_business_number_txt', 'ref_number_txt_ws',
                                  'recipient_business_number_txt', 'recipient_legal_name_txt_fr',
                                  'recipient_operating_name_txt_fr', 'research_organization_name_txt_fr',
                                  'recipient_province_txt_fr', 'recipient_city_txt_fr', 'recipient_postal_code_txt',
                                  'federal_riding_name_txt_fr', 'federal_riding_number_txt', 
                                  'program_name_txt_fr', 'program_purpose_txt_fr',
                                  'agreement_title_txt_fr', 'coverage_txt_fr', 'description_txt_fr',
                                  'naics_identifier_txt', 'expected_results_txt_fr', 'additional_information_txt_fr',
                                  'owner_org_title_txt_fr', 'agreement_value_fr_txt_ws']

        # English search fields
        self.solr_fields_en = ("id,ref_number_s,ref_number_txt_ws,"
                               "agreement_type_en_s,"
                               "recipient_country_en_s,"
                               "agreement_value_range_en_s,"
                               "year_i,"
                               "owner_org_en_s,"
                               "amendment_number_s,"
                               "amendment_date_s,amendment_date_txt,"
                               "recipient_business_number_s,recipient_business_number_txt,"
                               "recipient_legal_name_txt_en,recipient_type_en_s,"
                               "recipient_operating_name_txt_en,research_organization_name_txt_en,"
                               "recipient_province_en_s,recipient_province_txt_en,"
                               "recipient_city_en_s,recipient_city_txt_en,"
                               "recipient_postal_code_txt,"
                               "federal_riding_name_txt_en,"
                               "federal_riding_number_s,federal_riding_number_txt,"
                               "program_name_txt_en,program_purpose_txt_en,agreement_number_s,"
                               "agreement_title_txt_en,agreement_value_en_txt_ws,agreement_value_fs,"
                               "foreign_currency_type_en_s,foreign_currency_value_s,"
                               "agreement_start_date_s,agreement_end_date_s,agreement_type_en_s,"
                               "coverage_txt_en,description_txt_en,"
                               "naics_identifier_s,naics_identifier_txt,"
                               "expected_results_txt_en,additional_information_txt_en,"
                               "report_type_en_s,nil_report_b,quarter_s,fiscal_year_s"
                               )
        self.solr_query_fields_en = ['id', 'owner_org_en_s^2', 'ref_number_txt_ws', 'ref_number_s', 'recipient_country_en_s',
                                     'amendment_date_s', 'recipient_business_number_s', 'recipient_legal_name_txt_en',
                                     'recipient_operating_name_txt_en', 'recipient_province_en_s',
                                     'recipient_city_en_s', 'recipient_postal_code_txt',
                                     'federal_riding_name_txt_en',
                                     'program_name_txt_en', 'program_purpose_txt_en',
                                     'agreement_title_txt_en',
                                     'agreement_value_en_txt_ws',
                                     'agreement_number_s', 'agreement_number_ws',
                                     'foreign_currency_type_en_s', 'foreign_currency_value_s',
                                     'coverage_txt_en', 'description_txt_en',
                                     'naics_identifier_s',
                                     'expected_results_txt_en', 'additional_information_txt_en']
        self.solr_facet_fields_en = ['{!ex=tag_owner_org_en_s}owner_org_en_s',
                                     '{!ex=tag_agreement_type_en_s}agreement_type_en_s',
                                     '{!ex=tag_year_i}year_i',
                                     '{!ex=tag_report_type_en_s}report_type_en_s',
                                     '{!ex=tag_agreement_value_range_en_s}agreement_value_range_en_s']
        self.solr_hl_fields_en = ['amendment_date_txt', 'recipient_business_number_txt', 'ref_number_txt_ws',
                                  'recipient_business_number_txt', 'recipient_legal_name_txt_en',
                                  'recipient_operating_name_txt_en', 'research_organization_name_txt_en',
                                  'recipient_province_txt_en', 'recipient_city_txt_en', 'recipient_postal_code_txt',
                                  'federal_riding_name_txt_en', 'federal_riding_number_txt', 
                                  'program_name_txt_en', 'program_purpose_txt_en',
                                  'agreement_title_txt_en', 'coverage_txt_en', 'description_txt_en',
                                  'naics_identifier_txt', 'expected_results_txt_en', 'additional_information_txt_en',
                                  'owner_org_title_txt_en', 'agreement_value_en_txt_ws']

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
        context["gc_ds_id"] = settings.GC_DATASET_ID
        context["gc_ds_title_en"] = settings.GC_DATASET_TITLE_EN
        context["gc_ds_title_fr"] = settings.GC_DATASET_TITLE_FR
        context["adobe_analytics_url"] = settings.ADOBE_ANALYTICS_URL
        items_per_page = int(settings.GC_ITEMS_PER_PAGE)

        # Get any search terms
        solr_search_terms = search_util.get_search_terms(request)
        context['search_text'] = str(request.GET.get('search_text', ''))

        # Retrieve search results and transform facets results to python dict

        solr_search_orgs: str = request.GET.get('gc-search-orgs', '')
        solr_search_year: str = request.GET.get('gc-search-year', '')
        solr_search_agreement: str = request.GET.get('gc-search-agreement-type', '')
        solr_search_type: str = request.GET.get('gc-search-report-type', '')
        solr_search_range: str = request.GET.get('gc-search-agreement-range', '')

        context["organizations_selected"] = solr_search_orgs
        context["organizations_selected_list"] = solr_search_orgs.split('|')
        context["year_selected"] = solr_search_year
        context["year_selected_list"] = solr_search_year.split('|')
        context["agreement_selected"] = solr_search_agreement
        context["agreement_selected_list"] = solr_search_agreement.split('|')
        context["type_selected"] = solr_search_type
        context["type_selected_list"] = solr_search_type.split('|')
        context["range_selected"] = solr_search_range
        context["range_selected_list"] = solr_search_range.split('|')

        start_row, page = search_util.calc_starting_row(request.GET.get('page', 1))

        # Retrieve search sort order
        solr_search_sort = request.GET.get('sort', 'score desc')
        if solr_search_sort not in ['score desc', 'agreement_start_date_s desc', 'agreement_value_fs desc']:
            solr_search_sort = 'score desc'
        context['sortby'] = solr_search_sort

        if request.LANGUAGE_CODE == 'fr':
            facets_dict = dict(owner_org_fr_s=context['organizations_selected'],
                               year_i=context['year_selected'],
                               agreement_type_fr_s=context['agreement_selected'],
                               report_type_fr_s=context['type_selected'],
                               agreement_value_range_fr_s=context['range_selected'],
                               amendment_number_s='current')
        else:
            facets_dict = dict(owner_org_en_s=context['organizations_selected'],
                               year_i=context['year_selected'],
                               agreement_type_en_s=context['agreement_selected'],
                               report_type_en_s=context['type_selected'],
                               agreement_value_range_en_s=context['range_selected'],
                               amendment_number_s='current')

        if request.LANGUAGE_CODE == 'fr':
            search_results = search_util.solr_query(solr_search_terms,
                                                    settings.SOLR_GC,
                                                    self.solr_fields_fr,
                                                    self.solr_query_fields_fr,
                                                    self.solr_facet_fields_fr,
                                                    self.phrase_xtras_fr,
                                                    start_row=str(start_row), pagesize=str(items_per_page),
                                                    facets=facets_dict,
                                                    sort_order=solr_search_sort)
        else:
            search_results = search_util.solr_query(solr_search_terms,
                                                    settings.SOLR_GC,
                                                    self.solr_fields_en,
                                                    self.solr_query_fields_en,
                                                    self.solr_facet_fields_en,
                                                    self.phrase_xtras_en,
                                                    start_row=str(start_row), pagesize=str(items_per_page),
                                                    facets=facets_dict,
                                                    sort_order=solr_search_sort)

        context['results'] = search_results
        export_url = "/{0}/gc/export/?{1}".format(request.LANGUAGE_CODE, request.GET.urlencode())
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
            context['agreement_type_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['agreement_type_fr_s'])
            context['report_type_fr_s'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['report_type_fr_s'])
            context['agreement_value_range_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['agreement_value_range_fr_s'])
            context['info_msg'] = settings.GC_INFO_FR
            context['about_msg'] = settings.GC_ABOUT_FR

        else:
            context['org_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_en_s'])
            context['agreement_type_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['agreement_type_en_s'])
            context['report_type_en_s'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['report_type_en_s'])
            context['agreement_value_range_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['agreement_value_range_en_s'])
            context['info_msg'] = settings.GC_INFO_EN
            context['about_msg'] = settings.GC_ABOUT_EN

        context['year_i'] = search_util.convert_facet_list_to_dict(
            search_results.facets['facet_fields']['year_i'])

        return render(request, "gc_search.html", context)


class GCAmendmentView(GCSearchView):

    def __init__(self):
        super().__init__()
        self.phrase_xtras_en = {}
        self.phrase_xtras_fr = {}

    def get(self, request, slug=''):
        context = dict(LANGUAGE_CODE=request.LANGUAGE_CODE, )
        context["cdts_version"] = settings.CDTS_VERSION
        context["adobe_analytics_url"] = settings.ADOBE_ANALYTICS_URL
        context["slug"] = slug
        solr_search_terms = 'ref_number_s:"{0}"'.format(slug)
        if request.LANGUAGE_CODE == 'fr':
            search_results = search_util.solr_query(solr_search_terms,
                                                    settings.SOLR_GC,
                                                    self.solr_fields_fr,
                                                    self.solr_query_fields_fr,
                                                    self.solr_facet_fields_fr,
                                                    self.phrase_xtras_fr,
                                                    sort_order='amendment_number_s desc')
        else:
            search_results = search_util.solr_query(solr_search_terms,
                                                    settings.SOLR_GC,
                                                    self.solr_fields_en,
                                                    self.solr_query_fields_en,
                                                    self.solr_facet_fields_en,
                                                    self.phrase_xtras_en,
                                                    sort_order='amendment_number_s desc')
        context['results'] = search_results
        if len(search_results.docs) > 0:
            context['ref_number_s'] = slug
            return render(request, "gc_amendment.html", context)
        else:
            return render(request, 'no_record_found.html', context, status=404)


class GCRecordView(GCSearchView):

    def __init__(self):
        super().__init__()
        self.phrase_xtras_en = {}
        self.phrase_xtras_fr = {}

    def get(self, request, slug=''):
        context = dict(LANGUAGE_CODE=request.LANGUAGE_CODE, )
        context["cdts_version"] = settings.CDTS_VERSION
        context["adobe_analytics_url"] = settings.ADOBE_ANALYTICS_URL
        context["slug"] = url_part_escape(slug)
        solr_search_terms = 'id:"{0}"'.format(context["slug"])
        if request.LANGUAGE_CODE == 'fr':
            search_results = search_util.solr_query(solr_search_terms,
                                                    settings.SOLR_GC,
                                                    self.solr_fields_fr,
                                                    self.solr_query_fields_fr,
                                                    self.solr_facet_fields_fr,
                                                    self.phrase_xtras_fr)
        else:
            search_results = search_util.solr_query(solr_search_terms,
                                                    settings.SOLR_GC,
                                                    self.solr_fields_en,
                                                    self.solr_query_fields_en,
                                                    self.solr_facet_fields_en,
                                                    self.phrase_xtras_en)
        context['results'] = search_results
        if len(search_results.docs) > 0:
            context['id'] = slug
            return render(request, "gc_record.html", context)
        else:
            return render(request, 'no_record_found.html', context, status=404)


class GCExportView(View):

    def __init__(self):
        super().__init__()
        self.solr_fields_fr = ("ref_number_s,"
                               "amendment_number_s,"
                               "amendment_date_s,"
                               "agreement_type_fr_s,"
                               "recipient_type_fr_s,"
                               "recipient_business_number_s,"
                               "recipient_legal_name_fr_s,"
                               "recipient_operating_name_fr_s,research_organization_name_fr_s,"
                               "recipient_country_fr_s,"
                               "recipient_province_fr_s,"
                               "recipient_city_fr_s,"
                               "recipient_postal_code_s,"
                               "federal_riding_name_fr_s,"
                               "federal_riding_number_s,"
                               "program_name_fr_s,program_purpose_fr_s,"
                               "agreement_title_fr_s,"
                               "agreement_number_s,"
                               "agreement_value_fr_s,"
                               "foreign_currency_type_fr_s,foreign_currency_value_s,"
                               "agreement_start_date_s,agreement_end_date_s,"
                               "coverage_fr_s,description_fr_s,"
                               "naics_identifier_s,"
                               "expected_results_fr_s,additional_information_fr_s,"
                               "owner_org_fr_s,"
                               )
        self.solr_query_fields_fr = ['owner_org_fr_s^2',  'ref_number_txt_ws', 'recipient_country_fr_s',
                                     'amendment_date_s', 'recipient_business_number_s', 'recipient_legal_name_txt_fr',
                                     'recipient_operating_name_txt_fr', 'recipient_province_fr_s',
                                     'recipient_city_fr_s', 'recipient_postal_code_txt',
                                     'federal_riding_name_txt_fr',
                                     'program_name_txt_fr', 'program_purpose_txt_fr',
                                     'agreement_value_fr_txt_ws', 'agreement_value_fr_s',
                                     'foreign_currency_type_fr_s', 'foreign_currency_value_s',
                                     'coverage_txt_fr', 'description_txt_fr',
                                     'naics_identifier_s',
                                     'expected_results_txt_fr', 'additional_information_txt_fr']
        self.solr_facet_fields_fr = ['{!ex=tag_owner_org_fr_s}owner_org_fr_s',
                                     '{!ex=tag_agreement_type_fr_s}agreement_type_fr_s',
                                     '{!ex=tag_year_i}year_i',
                                     '{!ex=tag_report_type_fr_s}report_type_fr_s',
                                     '{!ex=tag_agreement_value_range_fr_s}agreement_value_range_fr_s']

        # English search fields
        self.solr_fields_en = ("ref_number_s,"
                               "amendment_number_s,"
                               "amendment_date_s,"
                               "agreement_type_en_s,"
                               "recipient_type_en_s,"
                               "recipient_business_number_s,"
                               "recipient_legal_name_en_s,"
                               "recipient_operating_name_en_s,research_organization_name_en_s,"
                               "recipient_country_en_s,"
                               "recipient_province_en_s,"
                               "recipient_city_en_s,"
                               "recipient_postal_code_s,"
                               "federal_riding_name_en_s,"
                               "federal_riding_number_s,"
                               "program_name_en_s,program_purpose_en_s,"
                               "agreement_title_en_s,"
                               "agreement_number_s,"
                               "agreement_value_en_s,"
                               "foreign_currency_type_en_s,foreign_currency_value_s,"
                               "agreement_start_date_s,agreement_end_date_s,"
                               "coverage_en_s,description_en_s,"
                               "naics_identifier_s,"
                               "expected_results_en_s,additional_information_en_s,"
                               "owner_org_en_s,"
                               )
        self.solr_query_fields_en = ['owner_org_en_s^2', 'ref_number_txt_ws', 'recipient_country_en_s',
                                     'amendment_date_s', 'recipient_business_number_s', 'recipient_legal_name_txt_en',
                                     'recipient_operating_name_txt_en', 'recipient_province_en_s',
                                     'recipient_city_en_s', 'recipient_postal_code_txt',
                                     'federal_riding_name_txt_en',
                                     'program_name_txt_en', 'program_purpose_txt_en',
                                     'agreement_value_en_txt_ws',
                                     'foreign_currency_type_en_s', 'foreign_currency_value_s',
                                     'coverage_txt_en', 'description_txt_en',
                                     'naics_identifier_s',
                                     'expected_results_txt_en', 'additional_information_txt_en']
        self.solr_facet_fields_en = ['{!ex=tag_owner_org_en_s}owner_org_en_s',
                                     '{!ex=tag_agreement_type_en_s}agreement_type_en_s',
                                     '{!ex=tag_year_i}year_i',
                                     '{!ex=tag_report_type_en_s}report_type_en_s',
                                     '{!ex=tag_agreement_value_range_en_s}agreement_value_range_en_s']

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

        # Retrieve search results and transform facets results to python dict
        solr_search_orgs: str = request.GET.get('gc-search-orgs', '')
        solr_search_year: str = request.GET.get('gc-search-year', '')
        solr_search_agreement: str = request.GET.get('gc-search-agreement-type', '')
        solr_search_type: str = request.GET.get('gc-search-report-type', '')
        solr_search_range: str = request.GET.get('gc-search-agreement-range', '')

        solr_search_terms = search_util.get_search_terms(request)
        solr_fields = self.solr_fields_en
        solr_search_facets = self.solr_facet_fields_en
        solr_query_fields = self.solr_query_fields_en
        if request.LANGUAGE_CODE == 'fr':
            facets_dict = dict(owner_org_fr_s=solr_search_orgs,
                               year_i=solr_search_year,
                               agreement_type_fr_s=solr_search_agreement,
                               report_type_fr_s=solr_search_type,
                               agreement_value_range_fr_s=solr_search_range)
            solr_search_facets = self.solr_facet_fields_fr
            solr_query_fields = self.solr_query_fields_fr
            solr_fields = self.solr_fields_fr
        else:
            facets_dict = dict(owner_org_en_s=solr_search_orgs,
                               year_i=solr_search_year,
                               agreement_type_en_s=solr_search_agreement,
                               report_type_en_s=solr_search_type,
                               agreement_value_range_en_s=solr_search_range)

        search_results = search_util.solr_query_for_export(solr_search_terms,
                                                           settings.SOLR_GC,
                                                           solr_fields,
                                                           solr_query_fields,
                                                           solr_search_facets,
                                                           "report_type_en_s asc, agreement_start_date_s desc",
                                                           facets_dict,
                                                           self.phrase_xtras)

        if search_util.cache_search_results_file(cached_filename=cached_filename, sr=search_results,
                                                 solr_fields=solr_fields):
            if settings.EXPORT_FILE_CACHE_URL == "":
                return FileResponse(open(cached_filename, 'rb'), as_attachment=True)
            else:
                return HttpResponseRedirect(settings.EXPORT_FILE_CACHE_URL + "{}.csv".format(hashed_query))
