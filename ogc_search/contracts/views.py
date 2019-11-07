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
        'solr_report_type': request.GET.get('ct-search-report-type', ''),
        'solr_search_orgs': request.GET.get('ct-search-orgs', ''),
        'solr_search_year': request.GET.get('ct-search-year', ''),
        'solr_search_commodity_type': request.GET.get('ct-search-commodity-type', ''),
        'solr_search_country': request.GET.get('ct-search-country', ''),
        'solr_search_range': request.GET.get('ct-search-dollar-range', ''),
        'solr_search_agreements': request.GET.get('ct-search-agreement', ''),
        'solr_search_solicitation': request.GET.get('ct-solicitation', ''),
        'solr_search_doc_type': request.GET.get('ct-search-doc', ''),
    }


class CTSearchView(View):
    # Contracts Search Page
    def __init__(self):
        super().__init__()

        # Fields to be returned by the Solr query, English and French Versions
        self.solr_fields_en = ("id,ref_number_s,procurement_id_s,"
                               "vendor_name_s,vendor_name_txt_en,"
                               "contract_date_dt,contract_year_s,contract_month_s,"
                               "economic_object_code_s,"
                               "description_en_s,description_txt_en,"
                               "contract_start_dt,contract_start_s,"
                               "contract_delivery_dt,contract_delivery_s,"
                               "contract_value_f,contract_value_en_s,"
                               "original_value_f,original_value_en_s,"
                               "amendment_value_f,amendment_value_en_s,"
                               "comments_en_s,comments_txt_en,"
                               "additional_comments_en_s,additional_comments_txt_en,"
                               "agreement_type_code_en_s,agreement_type_code_txt_en,"
                               "commodity_type_code_en_s,"
                               "commodity_code_s,"
                               "country_of_origin_en_s,"
                               "solicitation_procedure_code_en_s,"
                               "limited_tendering_reason_code_en_s,"
                               "exemption_code_en_s,"
                               "aboriginal_business_en_s,"
                               "intellectual_property_code_en_s,"
                               "potential_commercial_exploitation_en_s,"
                               "former_public_servant_en_s,"
                               "standing_offer_en_s,"
                               "standing_offer_number_s,"
                               "document_type_code_en_s,"
                               "ministers_office_en_s,"
                               "reporting_period_s,"
                               "owner_org_s,owner_org_en_s,"
                               "report_type_en_s,"
                               "nil_report_b"
                               )
        self.solr_fields_fr = ("id,ref_number_s,procurement_id_s,"
                               "vendor_name_s,vendor_name_txt_fr,"
                               "contract_date_dt,contract_year_s,contract_month_s,"
                               "economic_object_code_s,"
                               "description_fr_s,description_txt_fr,"
                               "contract_start_dt,contract_start_s,"
                               "contract_delivery_dt,contract_delivery_s,"
                               "contract_value_f,contract_value_fr_s,"
                               "original_value_f,original_value_fr_s,"
                               "amendment_value_f,amendment_value_fr_s,"
                               "comments_fr_s,comments_txt_fr,"
                               "additional_comments_fr_s,additional_comments_txt_fr,"
                               "agreement_type_code_fr_s,agreement_type_code_txt_fr,"
                               "commodity_type_code_fr_s,"
                               "commodity_code_s,"
                               "country_of_origin_fr_s,"
                               "solicitation_procedure_code_fr_s,"
                               "limited_tendering_reason_code_fr_s,"
                               "exemption_code_fr_s,"
                               "aboriginal_business_fr_s,"
                               "intellectual_property_code_fr_s,"
                               "potential_commercial_exploitation_fr_s,"
                               "former_public_servant_fr_s,"
                               "standing_offer_fr_s,"
                               "standing_offer_number_s,"
                               "document_type_code_fr_s,"
                               "ministers_office_fr_s,"
                               "reporting_period_s,"
                               "owner_org_s,owner_org_fr_s,"
                               "report_type_fr_s,"
                               "nil_report_b"
                               )

        # Fields to be searched in the Solr query. Fields can be weighted to indicate which are more relevant for
        # searching. 
        self.solr_query_fields_en = ['ref_number_s^5', 'procurement_id_s^5',
                                     'vendor_name_txt_en', 'contract_year_s', 'contract_month_s',
                                     'economic_object_code_s^4',
                                     'description_txt_en^3',
                                     'contract_start_s^4', 'contract_delivery_s^4',
                                     'contract_value_en_s^5', 'original_value_en_s^4', 'amendment_value_en_s^4',
                                     'comments_txt_en', 'additional_comments_txt_en',
                                     'agreement_type_code_txt_en',
                                     'commodity_type_code_en_s',
                                     'commodity_code_s',
                                     'country_of_origin_en_s^2',
                                     'solicitation_procedure_code_en_s',
                                     'limited_tendering_reason_code_en_s',
                                     'exemption_code_en_s',
                                     'aboriginal_business_en_s',
                                     'intellectual_property_code_en_s',
                                     'former_public_servant_en_s',
                                     'standing_offer_en_s', 'standing_offer_number_s',
                                     'ministers_office_en_s',
                                     'reporting_period_s',
                                     'owner_org_en_s',
                                     'report_type_en_s'
                                     ]
        self.solr_query_fields_fr = ['ref_number_s^5', 'procurement_id_s^5',
                                     'vendor_name_txt_fr', 'contract_year_s', 'contract_month_s',
                                     'economic_object_code_s^4',
                                     'description_txt_fr^3',
                                     'contract_start_s^4', 'contract_delivery_s^4',
                                     'contract_value_fr_s^5', 'original_value_fr_s^4', 'amendment_value_fr_s^4',
                                     'comments_txt_fr', 'additional_comments_txt_fr',
                                     'agreement_type_code_txt_fr',
                                     'commodity_type_code_fr_s',
                                     'commodity_code_s',
                                     'country_of_origin_fr_s^2',
                                     'solicitation_procedure_code_fr_s',
                                     'limited_tendering_reason_code_fr_s',
                                     'exemption_code_fr_s',
                                     'aboriginal_business_fr_s',
                                     'intellectual_property_code_fr_s',
                                     'former_public_servant_fr_s',
                                     'standing_offer_fr_s', 'standing_offer_number_s',
                                     'ministers_office_fr_s',
                                     'reporting_period_s',
                                     'owner_org_fr_s',
                                     'report_type_fr_s'
                                     ]

        # These fields are search facets
        self.solr_facet_fields_en = ['{!ex=tag_owner_org_en_s}owner_org_en_s',
                                     '{!ex=tag_report_type_en_s}report_type_en_s',
                                     '{!ex=tag_contract_year_s}contract_year_s',
                                     '{!ex=tag_contract_value_range_en_s}contract_value_range_en_s',
                                     '{!ex=tag_commodity_type_code_en_s}commodity_type_code_en_s',
                                     '{!ex=tag_country_of_origin_en_s}country_of_origin_en_s',
                                     '{!ex=tag_solicitation_procedure_code_en_s}solicitation_procedure_code_en_s',
                                     '{!ex=tag_exemption_code_en_s}exemption_code_en_s',
                                     '{!ex=tag_aboriginal_business_en_s}aboriginal_business_en_s',
                                     '{!ex=tag_document_type_code_en_s}document_type_code_en_s',
                                     '{!ex=tag_agreement_type_code_en_s}agreement_type_code_en_s']
        self.solr_facet_fields_fr = ['{!ex=tag_owner_org_fr_s}owner_org_fr_s',
                                     '{!ex=tag_report_type_en_s}report_type_fr_s',
                                     '{!ex=tag_contract_year_s}contract_year_s',
                                     '{!ex=tag_contract_value_range_fr_s}contract_value_range_fr_s',
                                     '{!ex=tag_commodity_type_code_fr_s}commodity_type_code_fr_s',
                                     '{!ex=tag_country_of_origin_fr_s}country_of_origin_fr_s',
                                     '{!ex=tag_solicitation_procedure_code_fr_s}solicitation_procedure_code_fr_s',
                                     '{!ex=tag_exemption_code_fr_s}exemption_code_fr_s',
                                     '{!ex=tag_aboriginal_business_fr_s}aboriginal_business_fr_s',
                                     '{!ex=tag_document_type_code_fr_s}document_type_code_fr_s',
                                     '{!ex=tag_agreement_type_code_fr_s}agreement_type_code_fr_s']

        # These fields will have search hit high-lighting applied
        self.solr_hl_fields_en = ['description_txt_en', 'vendor_name_txt_en', 'comments_txt_en',
                                  'additional_comments_txt_en', 'agreement_type_code_txt_en',
                                  'country_of_origin_en_s', ]
        self.solr_hl_fields_fr = ['description_txt_fr', 'vendor_name_txt_fr', 'comments_txt_fr',
                                  'additional_comments_txt_fr', 'agreement_type_code_txt_fr',
                                  'country_of_origin_fr_s', ]

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
        context["ct_ds_id"] = settings.CT_DATASET_ID
        context["ct_ds_title_en"] = settings.CT_DATASET_TITLE_EN
        context["ct_ds_title_fr"] = settings.CT_DATASET_TITLE_FR
        items_per_page = int(settings.GC_ITEMS_PER_PAGE)
        if request.LANGUAGE_CODE == 'fr':
            context['info_msg'] = settings.CT_INFO_FR
            context['about_msg'] = settings.CT_ABOUT_FR
        else:
            context['info_msg'] = settings.CT_INFO_EN
            context['about_msg'] = settings.CT_ABOUT_EN

        # Get any search terms
        solr_search_terms = search_util.get_search_terms(request)
        context['search_text'] = str(request.GET.get('search_text', ''))
        # Retrieve search results and transform facets results to python dict

        # Retrieve any selected search facets
        solr_report_type: str = request.GET.get('ct-search-report-type', '')
        solr_search_orgs: str = request.GET.get('ct-search-orgs', '')
        solr_search_year: str = request.GET.get('ct-search-year', '')
        solr_search_commodity_type: str = request.GET.get('ct-search-commodity-type', '')
        solr_search_country: str = request.GET.get('ct-search-country', '')
        solr_search_range: str = request.GET.get('ct-search-dollar-range', '')
        solr_search_agreements: str = request.GET.get('ct-search-agreement', '')
        solr_search_solicitation: str = request.GET.get('ct-solicitation', '')
        solr_search_doc_type: str = request.GET.get('ct-search-doc', '')
        context['type_selected'] = solr_report_type
        context['type_selected_list'] = solr_report_type.split('|')
        context["organizations_selected"] = solr_search_orgs
        context["organizations_selected_list"] = solr_search_orgs.split('|')
        context["year_selected"] = solr_search_year
        context["year_selected_list"] = solr_search_year.split('|')
        context["commodity_type_selected"] = solr_search_commodity_type
        context["commodity_type_selected_list"] = solr_search_commodity_type.split('|')
        context["country_selected"] = solr_search_country
        context["country_selected_list"] = solr_search_country.split('|')
        context["range_selected"] = solr_search_range
        context["range_selected_list"] = solr_search_range.split('|')
        context["agreement_selected"] = solr_search_agreements
        context["agreement_selected_list"] = solr_search_agreements.split('|')
        context["solicitation_selected"] = solr_search_solicitation
        context["solicitation_selected_list"] = solr_search_solicitation.split('|')
        context["doc_type_selected"] = solr_search_doc_type
        context["doc_type_selected_list"] = solr_search_doc_type.split('|')

        if request.LANGUAGE_CODE == 'fr':
            facets_dict = dict(owner_org_fr_s=context['organizations_selected'],
                               report_type_en_s=context['type_selected'],
                               contract_year_s=context['year_selected'],
                               commodity_type_code_fr_s=context['commodity_type_selected'],
                               country_of_origin_fr_s=context['country_selected'],
                               contract_value_range_fr_s=context['range_selected'],
                               agreement_type_code_fr_s=context['agreement_selected'],
                               solicitation_procedure_code_fr_s=context['solicitation_selected'],
                               document_type_code_fr_s=context['doc_type_selected']
                               )
        else:
            facets_dict = dict(owner_org_en_s=context['organizations_selected'],
                               report_type_en_s=context['type_selected'],
                               contract_year_s=context['year_selected'],
                               commodity_type_code_en_s=context['commodity_type_selected'],
                               country_of_origin_en_s=context['country_selected'],
                               contract_value_range_en_s=context['range_selected'],
                               agreement_type_code_en_s=context['agreement_selected'],
                               solicitation_procedure_code_en_s=context['solicitation_selected'],
                               document_type_code_en_s=context['doc_type_selected']
                               )

        # Retrieve search sort order
        solr_search_sort = request.GET.get('sort', 'score desc')
        if solr_search_sort not in ['score desc', 'contract_delivery_s desc', 'contract_value_f desc']:
            solr_search_sort = 'score desc'
        context['sortby'] = solr_search_sort

        # Get current page
        start_row, page = search_util.calc_starting_row(request.GET.get('page', 1))

        if request.LANGUAGE_CODE == 'fr':
            search_results = search_util.solr_query(solr_search_terms,
                                                    settings.SOLR_CT,
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
                                                    settings.SOLR_CT,
                                                    self.solr_fields_en,
                                                    self.solr_query_fields_en,
                                                    self.solr_facet_fields_en,
                                                    self.phrase_xtras_en,
                                                    start_row=str(start_row), pagesize=str(items_per_page),
                                                    facets=facets_dict,
                                                    sort_order=solr_search_sort,
                                                    facet_limit=200)


        context['results'] = search_results
        export_url = "/{0}/ct/export/?{1}".format(request.LANGUAGE_CODE, request.GET.urlencode())
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
            context['report_type_fr_s'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['report_type_fr_s'])
            context['org_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_fr_s'])
            context['commodity_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['commodity_type_code_fr_s'])
            context['country_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['country_of_origin_fr_s'])
            context['agreement_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['agreement_type_code_fr_s'])
            context['value_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['contract_value_range_fr_s'])
            context['solicitation_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['solicitation_procedure_code_fr_s'])
            context['doc_type_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['document_type_code_fr_s'])
        else:
            context['report_type_en_s'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['report_type_en_s'])
            context['org_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_en_s'])
            context['commodity_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['commodity_type_code_en_s'])
            context['country_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['country_of_origin_en_s'])
            context['agreement_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['agreement_type_code_en_s'])
            context['value_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['contract_value_range_en_s'])
            context['solicitation_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['solicitation_procedure_code_en_s'])
            context['doc_type_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['document_type_code_en_s'])
        context['year_facets'] = search_util.convert_facet_list_to_dict(
            search_results.facets['facet_fields']['contract_year_s'])
        return render(request, "contracts_search.html", context)


class CTContractView(CTSearchView):

    def __init__(self):
        super().__init__()
        self.phrase_xtras_en = {}
        self.phrase_xtras_fr = {}

    def get(self, request, slug=''):
        context = dict(LANGUAGE_CODE=request.LANGUAGE_CODE, )
        context["cdts_version"] = settings.CDTS_VERSION
        context["slug"] = slug
        solr_search_terms = 'id:"{0}"'.format(slug)
        if request.LANGUAGE_CODE == 'fr':
            search_results = search_util.solr_query(solr_search_terms,
                                                    settings.SOLR_CT,
                                                    self.solr_fields_fr,
                                                    self.solr_query_fields_fr,
                                                    self.solr_facet_fields_fr,
                                                    self.phrase_xtras_fr)
        else:
            search_results = search_util.solr_query(solr_search_terms,
                                                    settings.SOLR_CT,
                                                    self.solr_fields_en,
                                                    self.solr_query_fields_en,
                                                    self.solr_facet_fields_en,
                                                    self.phrase_xtras_en)
        context['results'] = search_results
        if len(search_results.docs) > 0:
            context['ref_number_s'] = slug
            return render(request, "contract.html", context)
        else:
            return render(request, 'no_record_found.html', context, status=404)


class CTExportView(View):

    def __init__(self):
        super().__init__()

        # Fields to be returned by the Solr query, English and French Versions
        self.solr_fields_en = ("ref_number_s,"
                               "procurement_id_s,"
                               "vendor_name_s,"
                               "contract_date_dt,"
                               "economic_object_code_s,"
                               "description_en_s,"
                               "contract_start_s,"
                               "contract_delivery_s,"
                               "contract_value_en_s,"
                               "original_value_en_s,"
                               "amendment_value_en_s,"
                               "comments_en_s,"
                               "additional_comments_en_s,"
                               "agreement_type_code_export_en_s,"
                               "commodity_type_code_en_s,"
                               "commodity_code_s,"
                               "country_of_origin_en_s,"
                               "solicitation_procedure_code_en_s,"
                               "limited_tendering_reason_code_en_s,"
                               "exemption_code_en_s,"
                               "aboriginal_business_en_s,"
                               "intellectual_property_code_en_s,"
                               "potential_commercial_exploitation_en_s,"
                               "former_public_servant_en_s,"
                               "standing_offer_en_s,"
                               "standing_offer_number_s,"
                               "document_type_code_en_s,"
                               "ministers_office_en_s,"
                               "reporting_period_s,"
                               "owner_org_en_s,"
                               "report_type_en_s"
                               )
        self.solr_fields_fr = ("ref_number_s,"
                               "procurement_id_s,"
                               "vendor_name_s,"
                               "contract_date_dt,"
                               "economic_object_code_s,"
                               "description_fr_s,"
                               "contract_start_s,"
                               "contract_delivery_s,"
                               "contract_value_fr_s,"
                               "original_value_fr_s,"
                               "amendment_value_fr_s,"
                               "comments_fr_s,"
                               "additional_comments_fr_s,"
                               "agreement_type_code_export_fr_s,"
                               "commodity_type_code_fr_s,"
                               "commodity_code_s,"
                               "country_of_origin_fr_s,"
                               "solicitation_procedure_code_fr_s,"
                               "limited_tendering_reason_code_fr_s,"
                               "exemption_code_fr_s,"
                               "aboriginal_business_fr_s,"
                               "intellectual_property_code_fr_s,"
                               "potential_commercial_exploitation_fr_s,"
                               "former_public_servant_fr_s,"
                               "standing_offer_fr_s,"
                               "standing_offer_number_s,"
                               "document_type_code_fr_s,"
                               "ministers_office_fr_s,"
                               "reporting_period_s,"
                               "owner_org_fr_s,"
                               "report_type_fr_s"
                               )

        # Fields to be searched in the Solr query. Fields can be weighted to indicate which are more relevant for
        # searching.
        self.solr_query_fields_en = ['ref_number_s^5', 'procurement_id_s^5',
                                     'vendor_name_txt_en', 'contract_year_s', 'contract_month_s',
                                     'economic_object_code_s^4',
                                     'description_txt_en^3',
                                     'contract_start_s^4', 'contract_delivery_s^4',
                                     'contract_value_en_s^5', 'original_value_en_s^4', 'amendment_value_en_s^4',
                                     'comments_txt_en', 'additional_comments_txt_en',
                                     'agreement_type_code_txt_en',
                                     'commodity_type_code_en_s',
                                     'commodity_code_s',
                                     'country_of_origin_en_s^2',
                                     'solicitation_procedure_code_en_s',
                                     'limited_tendering_reason_code_en_s',
                                     'exemption_code_en_s',
                                     'aboriginal_business_en_s',
                                     'intellectual_property_code_en_s',
                                     'former_public_servant_en_s',
                                     'standing_offer_en_s', 'standing_offer_number_s',
                                     'ministers_office_en_s',
                                     'reporting_period_s',
                                     'owner_org_en_s',
                                     'report_type_en_s'
                                     ]
        self.solr_query_fields_fr = ['ref_number_s^5', 'procurement_id_s^5',
                                     'vendor_name_txt_fr', 'contract_year_s', 'contract_month_s',
                                     'economic_object_code_s^4',
                                     'description_txt_fr^3',
                                     'contract_start_s^4', 'contract_delivery_s^4',
                                     'contract_value_fr_s^5', 'original_value_fr_s^4', 'amendment_value_fr_s^4',
                                     'comments_txt_fr', 'additional_comments_txt_fr',
                                     'agreement_type_code_txt_fr',
                                     'commodity_type_code_fr_s',
                                     'commodity_code_s',
                                     'country_of_origin_fr_s^2',
                                     'solicitation_procedure_code_fr_s',
                                     'limited_tendering_reason_code_fr_s',
                                     'exemption_code_fr_s',
                                     'aboriginal_business_fr_s',
                                     'intellectual_property_code_fr_s',
                                     'former_public_servant_fr_s',
                                     'standing_offer_fr_s', 'standing_offer_number_s',
                                     'ministers_office_fr_s',
                                     'reporting_period_s',
                                     'owner_org_fr_s',
                                     'report_type_fr_s'
                                     ]

        # These fields are search facets
        self.solr_facet_fields_en = ['{!ex=tag_owner_org_en_s}owner_org_en_s',
                                     '{!ex=tag_report_type_en_s}report_type_en_s',
                                     '{!ex=tag_contract_year_s}contract_year_s',
                                     '{!ex=tag_contract_value_range_en_s}contract_value_range_en_s',
                                     '{!ex=tag_commodity_type_code_en_s}commodity_type_code_en_s',
                                     '{!ex=tag_country_of_origin_en_s}country_of_origin_en_s',
                                     '{!ex=tag_solicitation_procedure_code_en_s}solicitation_procedure_code_en_s',
                                     '{!ex=tag_exemption_code_en_s}exemption_code_en_s',
                                     '{!ex=tag_aboriginal_business_en_s}aboriginal_business_en_s',
                                     '{!ex=tag_document_type_code_en_s}document_type_code_en_s',
                                     '{!ex=tag_agreement_type_code_en_s}agreement_type_code_en_s']
        self.solr_facet_fields_fr = ['{!ex=tag_owner_org_fr_s}owner_org_fr_s',
                                     '{!ex=tag_report_type_en_s}report_type_fr_s',
                                     '{!ex=tag_contract_year_s}contract_year_s',
                                     '{!ex=tag_contract_value_range_fr_s}contract_value_range_fr_s',
                                     '{!ex=tag_commodity_type_code_fr_s}commodity_type_code_fr_s',
                                     '{!ex=tag_country_of_origin_fr_s}country_of_origin_fr_s',
                                     '{!ex=tag_solicitation_procedure_code_fr_s}solicitation_procedure_code_fr_s',
                                     '{!ex=tag_exemption_code_fr_s}exemption_code_fr_s',
                                     '{!ex=tag_aboriginal_business_fr_s}aboriginal_business_fr_s',
                                     '{!ex=tag_document_type_code_fr_s}document_type_code_fr_s',
                                     '{!ex=tag_agreement_type_code_fr_s}agreement_type_code_fr_s']
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

        # Retrieve any selected search facets
        params = get_user_facet_parameters(request)

        solr_search_terms = search_util.get_search_terms(request)
        solr_fields = self.solr_fields_en
        solr_search_facets = self.solr_facet_fields_en
        solr_query_fields = self.solr_query_fields_en

        if request.LANGUAGE_CODE == 'fr':
            facets_dict = dict(owner_org_fr_s=params['solr_search_orgs'],
                               report_type_fr_s=params['solr_report_type'],
                               contract_year_s=params['solr_search_year'],
                               commodity_type_code_fr_s=params['solr_search_commodity_type'],
                               country_of_origin_fr_s=params['solr_search_country'],
                               contract_value_range_fr_s=params['solr_search_range'],
                               agreement_type_code_fr_s=params['solr_search_agreements'],
                               solicitation_procedure_code_fr_s=params['solr_search_solicitation'],
                               document_type_code_fr_s=params['solr_search_doc_type']
                               )
            solr_fields = self.solr_fields_fr
            solr_search_facets = self.solr_facet_fields_fr
            solr_query_fields = self.solr_query_fields_fr
        else:
            facets_dict = dict(owner_orgen_s=params['solr_search_orgs'],
                               report_type_en_s=params['solr_report_type'],
                               contract_year_s=params['solr_search_year'],
                               commodity_type_code_en_s=params['solr_search_commodity_type'],
                               country_of_origin_en_s=params['solr_search_country'],
                               contract_value_range_en_s=params['solr_search_range'],
                               agreement_type_code_en_s=params['solr_search_agreements'],
                               solicitation_procedure_code_en_s=params['solr_search_solicitation'],
                               document_type_code_en_s=params['solr_search_doc_type']
                               )

        search_results = search_util.solr_query_for_export(solr_search_terms,
                                                           settings.SOLR_CT,
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