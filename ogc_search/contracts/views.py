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
                               "vendor_name_s,vendor_name_txt,"
                               "vendor_postal_code_s,"
                               "buyer_name_s,buyer_name_txt_en,"
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
                               "trade_agreement_en_s,trade_agreement_txt_en,"
                               "land_claims_en_s,land_claims_txt_en,"
                               "commodity_type_en_s,"
                               "commodity_code_s,"
                               "country_of_origin_en_s,"
                               "solicitation_procedure_en_s,"
                               "limited_tendering_reason_en_s,limited_tendering_reason_txt_en,"
                               "trade_agreement_exceptions_en_s,trade_agreement_exceptions_txt_en,"
                               "aboriginal_business_en_s,"
                               "aboriginal_business_incidental_en_s,"
                               "intellectual_property_en_s,"
                               "potential_commercial_exploitation_en_s,"
                               "former_public_servant_en_s,"
                               "contracting_entity_en_s,"
                               "standing_offer_number_s,"
                               "instrument_type_en_s,"
                               "ministers_office_en_s,"
                               "number_of_bids_s,"
                               "article_6_exceptions_en_s,"
                               "award_criteria_en_s,"
                               "socioeconomic_indicator_en_s,"
                               "reporting_period_s,"
                               "owner_org_s,owner_org_en_s,"
                               "report_type_en_s,"
                               "nil_report_b"
                               )
        self.solr_fields_fr = ("id,ref_number_s,procurement_id_s,"
                               "vendor_name_s,vendor_name_txt,"
                               "vendor_postal_code_s,"
                               "buyer_name_s,buyer_name_txt_fr,"
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
                               "trade_agreement_fr_s,trade_agreement_txt_fr,"
                               "land_claims_fr_s,land_claims_txt_fr,"
                               "commodity_type_fr_s,"
                               "commodity_code_s,"
                               "country_of_origin_fr_s,"
                               "solicitation_procedure_fr_s,"
                               "limited_tendering_reason_fr_s,limited_tendering_reason_txt_fr,"
                               "trade_agreement_exceptions_fr_s,trade_agreement_exceptions_txt_fr,"
                               "aboriginal_business_fr_s,"
                               "aboriginal_business_incidental_fr_s,"
                               "intellectual_property_fr_s,"
                               "potential_commercial_exploitation_fr_s,"
                               "former_public_servant_fr_s,"
                               "contracting_entity_fr_s,"
                               "standing_offer_number_s,"
                               "instrument_type_fr_s,"
                               "ministers_office_fr_s,"
                               "number_of_bids_s,"
                               "article_6_exceptions_fr_s,"
                               "award_criteria_fr_s,"
                               "socioeconomic_indicator_fr_s,"
                               "reporting_period_s,"
                               "owner_org_s,owner_org_fr_s,"
                               "report_type_fr_s,"
                               "nil_report_b"
                               )

        # Fields to be searched in the Solr query. Fields can be weighted to indicate which are more relevant for
        # searching. 
        self.solr_query_fields_en = ['ref_number_s^5', 'procurement_id_s^5',
                                     'vendor_name_txt', 'vendor_postal_code_s',
                                     'buyer_name_s',
                                     'contract_year_s', 'contract_month_s',
                                     'economic_object_code_s^4',
                                     'description_txt_en^3',
                                     'contract_start_s^4', 'contract_delivery_s^4',
                                     'contract_value_en_s^5', 'original_value_en_s^4', 'amendment_value_en_s^4',
                                     'comments_txt_en', 'additional_comments_txt_en',
                                     'trade_agreement_exception_en_s',
                                     'commodity_type_en_s',
                                     'commodity_code_s',
                                     'country_of_origin_en_s^2',
                                     'solicitation_procedure_code_en_s',
                                     'limited_tendering_reason_code_en_s',
                                     'trade_agreement_exceptions_en_s',
                                     "land_claims_en_s",
                                     'aboriginal_business_en_s',
                                     'intellectual_property_en_s',
                                     'former_public_servant_en_s',
                                     'contracting_entity_en_s', 'standing_offer_number_s',
                                     'instrument_type_en_s',
                                     'ministers_office_en_s',
                                     'reporting_period_s',
                                     'owner_org_en_s',
                                     'report_type_en_s'
                                     ]
        self.solr_query_fields_fr = ['ref_number_s^5', 'procurement_id_s^5',
                                     'vendor_name_txt', 'vendor_postal_code_s',
                                     'buyer_name_s',
                                     'contract_year_s', 'contract_month_s',
                                     'economic_object_code_s^4',
                                     'description_txt_fr^3',
                                     'contract_start_s^4', 'contract_delivery_s^4',
                                     'contract_value_fr_s^5', 'original_value_fr_s^4', 'amendment_value_fr_s^4',
                                     'comments_txt_fr', 'additional_comments_txt_fr',
                                     'trade_agreement_exception_fr_s',
                                     'commodity_type_fr_s',
                                     'commodity_code_s',
                                     'country_of_origin_fr_s^2',
                                     'solicitation_procedure_code_fr_s',
                                     'limited_tendering_reason_code_fr_s',
                                     'trade_agreement_exceptions_fr_s',
                                     "land_claims_fr_s",
                                     'aboriginal_business_fr_s',
                                     'intellectual_property_fr_s',
                                     'former_public_servant_fr_s',
                                     'contracting_entity_fr_s', 'standing_offer_number_s',
                                     'instrument_type_fr_s',
                                     'ministers_office_fr_s',
                                     'reporting_period_s',
                                     'owner_org_fr_s',
                                     'report_type_fr_s'
                                     ]

        # These fields are search facets
        self.solr_facet_fields_en = ['{!ex=tag_contract_year_s}contract_year_s',
                                     '{!ex=tag_owner_org_en_s}owner_org_en_s',
                                     '{!ex=tag_contract_value_range_en_s}contract_value_range_en_s',
                                     '{!ex=tag_trade_agreement_en_s}trade_agreement_en_s',
                                     '{!ex=tag_land_claims_en_s}land_claims_en_s',
                                     '{!ex=tag_intellectual_property_en_s}intellectual_property_en_s',
                                     '{!ex=tag_solicitation_procedure_en_s}solicitation_procedure_en_s',
                                     '{!ex=tag_instrument_type_en_s}instrument_type_en_s',
                                     '{!ex=tag_commodity_type_en_s}commodity_type_en_s',
                                     '{!ex=tag_limited_tendering_reason_en_s}limited_tendering_reason_en_s',
                                     '{!ex=tag_trade_agreement_exceptions_en_s}trade_agreement_exceptions_en_s',
                                     '{!ex=tag_former_public_servant_en_s}former_public_servant_en_s',
                                     '{!ex=tag_contracting_entity_en_s}contracting_entity_en_s',
                                     '{!ex=tag_ministers_office_en_s}ministers_office_en_s',
                                     '{!ex=tag_report_type_en_s}report_type_en_s',
                                     ]

        self.solr_facet_fields_fr = ['{!ex=tag_contract_year_s}contract_year_s',
                                     '{!ex=tag_owner_org_fr_s}owner_org_fr_s',
                                     '{!ex=tag_contract_value_range_fr_s}contract_value_range_fr_s',
                                     '{!ex=tag_trade_agreement_fr_s}trade_agreement_fr_s',
                                     '{!ex=tag_land_claims_fr_s}land_claims_fr_s',
                                     '{!ex=tag_intellectual_property_fr_s}intellectual_property_fr_s',
                                     '{!ex=tag_solicitation_procedure_fr_s}solicitation_procedure_fr_s',
                                     '{!ex=tag_instrument_type_fr_s}instrument_type_fr_s',
                                     '{!ex=tag_commodity_type_fr_s}commodity_type_fr_s',
                                     '{!ex=tag_limited_tendering_reason_fr_s}limited_tendering_reason_fr_s',
                                     '{!ex=tag_trade_agreement_exceptions_fr_s}trade_agreement_exceptions_fr_s',
                                     '{!ex=tag_former_public_servant_fr_s}former_public_servant_fr_s',
                                     '{!ex=tag_contracting_entity_fr_s}contracting_entity_fr_s',
                                     '{!ex=tag_ministers_office_fr_s}ministers_office_fr_s',
                                     '{!ex=tag_report_type_fr_s}report_type_fr_s',
                                     ]

        # These fields will have search hit high-lighting applied
        self.solr_hl_fields_en = ['description_txt_en', 'vendor_name_txt', 'comments_txt_en',
                                  'additional_comments_txt_en', 'agreement_type_code_txt_en',
                                  'country_of_origin_en_s', 'trade_agreement_txt_en',
                                  'land_claims_txt_en', 'limited_tendering_reason_txt_en',
                                  'trade_agreement_exceptions_txt_en']
        self.solr_hl_fields_fr = ['description_txt_fr', 'vendor_name_txt', 'comments_txt_fr',
                                  'additional_comments_txt_fr', 'agreement_type_code_txt_fr',
                                  'country_of_origin_fr_s', 'trade_agreement_txt_fr',
                                  'land_claims_txt_fr', 'limited_tendering_reason_txt_fr',
                                  'trade_agreement_exceptions_txt_fr']

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
        context["ct_show_new_fields"] = settings.CT_SHOW_LATEST_FIELDS
        context["adobe_analytics_url"] = settings.ADOBE_ANALYTICS_URL
        context["survey_url"] = settings.SURVEY_URL if settings.SURVEY_ENABLED else None
        items_per_page = int(settings.GC_ITEMS_PER_PAGE)
        if request.LANGUAGE_CODE == 'fr':
            context['info_msg'] = settings.CT_INFO_FR
            context['about_msg'] = settings.CT_ABOUT_FR
        else:
            context['info_msg'] = settings.CT_INFO_EN
            context['about_msg'] = settings.CT_ABOUT_EN

        # Allow for, but do not require, a custom alert message
        if hasattr(settings, 'OPEN_DATA_PORTAL_ALERT_BASE'):
            context['od_portal_alert_base'] = settings.OPEN_DATA_PORTAL_ALERT_BASE
        else:
            context['od_portal_alert_base'] = "/data/static/_site_messaging/header_od_ckan."

        # Get any search terms
        solr_search_terms = search_util.get_search_terms(request)
        context['search_text'] = str(request.GET.get('search_text', ''))
        # Retrieve search results and transform facets results to python dict

        # Retrieve any selected search facets
        solr_search_year: str = request.GET.get('ct-search-year', '')  # contract_year_s
        solr_search_orgs: str = request.GET.get('ct-search-orgs', '')  # owner_org_en_s
        solr_search_range: str = request.GET.get('ct-search-dollar-range', '')  # contract_value_range_en_s
        solr_search_agreements: str = request.GET.get('ct-search-agreement', '')  # trade_agreement_en_s
        solr_land_claims: str = request.GET.get('ct-land-claims', '') # land_claims_en_s
        solr_search_ip: str = request.GET.get('ct-search-ip', '')  # intellectual_property_en_s
        solr_search_solicitation: str = request.GET.get('ct-solicitation', '')  # solicitation_procedure_en_s
        solr_search_doc_type: str = request.GET.get('ct-search-doc', '')  # instrument_type_en_s
        solr_search_commodity_type: str = request.GET.get('ct-search-commodity-type', '')  # commodity_type_en_s
        solr_search_tendering: str = request.GET.get('ct-search-tender', '')  # limited_tendering_reason_en_s
        solr_search_exempt: str = request.GET.get('ct-search-exempt', '')  # trade_agreement_exceptions_en_s
        solr_search_fps: str = request.GET.get('ct-search-fps', '')  # former_public_servant_en_s
        solr_search_so: str = request.GET.get('ct-search-so', '')  # contracting_entity_en_s
        solr_search_mo: str = request.GET.get('ct-search-mo', '')  # ministers_office_en_s
        solr_report_type: str = request.GET.get('ct-search-report-type', '')  # report_type_en_s

        context["year_selected"] = solr_search_year
        context["year_selected_list"] = solr_search_year.split('|')
        context["organizations_selected"] = solr_search_orgs
        context["organizations_selected_list"] = solr_search_orgs.split('|')
        context["range_selected"] = solr_search_range
        context["range_selected_list"] = solr_search_range.split('|')
        context["agreement_selected"] = solr_search_agreements
        context["agreement_selected_list"] = solr_search_agreements.split('|')
        context["land_claims_selected"] = solr_land_claims
        context["land_claims_selected_list"] = solr_land_claims.split('|')
        context['ip_selected'] = solr_search_ip
        context['ip_selected_list'] = solr_search_ip.split('|')
        context["solicitation_selected"] = solr_search_solicitation
        context["solicitation_selected_list"] = solr_search_solicitation.split('|')
        context["doc_type_selected"] = solr_search_doc_type
        context["doc_type_selected_list"] = solr_search_doc_type.split('|')
        context["commodity_type_selected"] = solr_search_commodity_type
        context["commodity_type_selected_list"] = solr_search_commodity_type.split('|')
        context['tendering_selected'] = solr_search_tendering
        context['tendering_selected_list'] = solr_search_tendering.split('|')
        context['exempt_selected'] = solr_search_exempt
        context['exempt_selected_list'] = solr_search_exempt.split('|')
        context['fps_selected'] = solr_search_fps
        context['fps_selected_list'] = solr_search_fps.split('|')
        context['so_selected'] = solr_search_so
        context['so_selected_list'] = solr_search_so.split('|')
        context['mo_selected'] = solr_search_mo
        context['mo_selected_list'] = solr_search_mo.split('|')
        context['type_selected'] = solr_report_type
        context['type_selected_list'] = solr_report_type.split('|')

        if request.LANGUAGE_CODE == 'fr':
            facets_dict = dict(contract_year_s=solr_search_year,
                               owner_org_fr_s=solr_search_orgs,
                               contract_value_range_fr_s=solr_search_range,
                               trade_agreement_fr_s=solr_search_agreements,
                               land_claims_fr_s=solr_land_claims,
                               intellectual_property_fr_s=solr_search_ip,
                               solicitation_procedure_fr_s=solr_search_solicitation,
                               instrument_type_fr_s=solr_search_doc_type,
                               commodity_type_fr_s=solr_search_commodity_type,
                               limited_tendering_reason_fr_s=solr_search_tendering,
                               trade_agreement_exceptions_fr_s=solr_search_exempt,
                               former_public_servant_fr_s=solr_search_fps,
                               contracting_entity_fr_s=solr_search_so,
                               ministers_office_fr_s=solr_search_mo,
                               report_type_fr_s=solr_report_type,
                               )
        else:
            facets_dict = dict(contract_year_s=solr_search_year,
                               owner_org_en_s=solr_search_orgs,
                               contract_value_range_en_s=solr_search_range,
                               trade_agreement_en_s=solr_search_agreements,
                               land_claims_en_s=solr_land_claims,
                               intellectual_property_en_s=solr_search_ip,
                               solicitation_procedure_en_s=solr_search_solicitation,
                               instrument_type_en_s=solr_search_doc_type,
                               commodity_type_en_s=solr_search_commodity_type,
                               limited_tendering_reason_en_s=solr_search_tendering,
                               trade_agreement_exceptions_en_s=solr_search_exempt,
                               former_public_servant_en_s=solr_search_fps,
                               contracting_entity_en_s=solr_search_so,
                               ministers_office_en_s=solr_search_mo,
                               report_type_en_s=solr_report_type,
                               )

        # Retrieve search sort order
        solr_search_sort = request.GET.get('sort', 'score desc')
        if solr_search_sort not in ['score desc', 'contract_start_s desc', 'original_value_f desc']:
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
                                                    facet_limit={'facet.limit': 200})
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
                                                    facet_limit={'facet.limit': 200})

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

        context['year_facets'] = search_util.convert_facet_list_to_dict(
            search_results.facets['facet_fields']['contract_year_s'])
        if request.LANGUAGE_CODE == 'fr':
            context['org_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_fr_s'])
            context['value_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['contract_value_range_fr_s'])
            context['agreement_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['trade_agreement_fr_s'])
            context['land_claims_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['land_claims_fr_s'])
            context['ip_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['intellectual_property_fr_s'])
            context['solicitation_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['solicitation_procedure_fr_s'])
            context['doc_type_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['instrument_type_fr_s'])
            context['commodity_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['commodity_type_fr_s'])
            context['tender_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['limited_tendering_reason_fr_s'])
            context['exempt_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['trade_agreement_exceptions_fr_s'])
            context['fps_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['former_public_servant_fr_s'])
            context['so_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['contracting_entity_fr_s'])
            context['mo_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['ministers_office_fr_s'])
            context['report_type_fr_s'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['report_type_fr_s'])
        else:
            context['org_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_en_s'])
            context['value_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['contract_value_range_en_s'])
            context['agreement_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['trade_agreement_en_s'])
            context['land_claims_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['land_claims_en_s'])
            context['ip_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['intellectual_property_en_s'])
            context['solicitation_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['solicitation_procedure_en_s'])
            context['doc_type_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['instrument_type_en_s'])
            context['commodity_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['commodity_type_en_s'])
            context['tender_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['limited_tendering_reason_en_s'])
            context['exempt_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['trade_agreement_exceptions_en_s'])
            context['fps_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['former_public_servant_en_s'])
            context['so_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['contracting_entity_en_s'])
            context['mo_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['ministers_office_en_s'])
            context['report_type_en_s'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['report_type_en_s'])

        return render(request, "contracts_search.html", context)


class CTContractView(CTSearchView):

    def __init__(self):
        super().__init__()
        self.phrase_xtras_en = {}
        self.phrase_xtras_fr = {}

    def get(self, request, slug=''):        # lgtm [py/similar-function]
        context = dict(LANGUAGE_CODE=request.LANGUAGE_CODE, )
        context["cdts_version"] = settings.CDTS_VERSION
        context["adobe_analytics_url"] = settings.ADOBE_ANALYTICS_URL
        context["survey_url"] = settings.SURVEY_URL if settings.SURVEY_ENABLED else None
        context["slug"] = url_part_escape(slug)
        solr_search_terms = 'id:"{0}"'.format(context["slug"])
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
                               "vendor_postal_code_s,"
                               "buyer_name_s,"
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
                               "trade_agreement_en_s,"
                               "land_claims_en_s,"
                               "commodity_type_en_s,"
                               "commodity_code_s,"
                               "country_of_origin_en_s,"
                               "solicitation_procedure_en_s,"
                               "limited_tendering_reason_en_s,"
                               "trade_agreement_exceptions_en_s,"
                               "aboriginal_business_en_s,"
                               "aboriginal_business_incidental_en_s,"
                               "intellectual_property_en_s,"
                               "potential_commercial_exploitation_en_s,"
                               "former_public_servant_en_s,"
                               "contracting_entity_en_s,"
                               "standing_offer_number_s,"
                               "instrument_type_en_s,"
                               "ministers_office_en_s,"
                               "number_of_bids_s,"
                               "article_6_exceptions_en_s,"
                               "award_criteria_en_s,"
                               "socioeconomic_indicator_en_s,"
                               "reporting_period_s,"
                               "owner_org_en_s,"
                               "report_type_en_s"
                               )
        self.solr_fields_fr = ("ref_number_s,"
                               "procurement_id_s,"
                               "vendor_name_s,"
                               "vendor_postal_code_s,"
                               "buyer_name_s,"
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
                               "trade_agreement_fr_s,"
                               "land_claims_fr_s,"
                               "commodity_type_fr_s,"
                               "commodity_code_s,"
                               "country_of_origin_fr_s,"
                               "solicitation_procedure_fr_s,"
                               "limited_tendering_reason_fr_s,"
                               "trade_agreement_exceptions_fr_s,"
                               "aboriginal_business_fr_s,"
                               "aboriginal_business_incidental_fr_s,"
                               "intellectual_property_fr_s,"
                               "potential_commercial_exploitation_fr_s,"
                               "former_public_servant_fr_s,"
                               "contracting_entity_fr_s,"
                               "standing_offer_number_s,"
                               "instrument_type_fr_s,"
                               "ministers_office_fr_s,"
                               "number_of_bids_s,"
                               "article_6_exceptions_fr_s,"
                               "award_criteria_fr_s,"
                               "socioeconomic_indicator_fr_s,"
                               "reporting_period_s,"
                               "owner_org_fr_s,"
                               "report_type_fr_s"
                               )

        # Fields to be searched in the Solr query. Fields can be weighted to indicate which are more relevant for
        # searching.
        self.solr_query_fields_en = ['ref_number_s^5', 'procurement_id_s^5',
                                     'vendor_name_txt', 'vendor_postal_code_s',
                                     'buyer_name_s',
                                     'contract_year_s', 'contract_month_s',
                                     'economic_object_code_s^4',
                                     'description_txt_en^3',
                                     'contract_start_s^4', 'contract_delivery_s^4',
                                     'contract_value_en_s^5', 'original_value_en_s^4', 'amendment_value_en_s^4',
                                     'comments_txt_en', 'additional_comments_txt_en',
                                     'trade_agreement_exception_en_s',
                                     'commodity_type_en_s',
                                     'commodity_code_s',
                                     'country_of_origin_en_s^2',
                                     'solicitation_procedure_code_en_s',
                                     'limited_tendering_reason_code_en_s',
                                     'trade_agreement_exceptions_en_s',
                                     'aboriginal_business_en_s',
                                     'intellectual_property_en_s',
                                     'former_public_servant_en_s',
                                     'contracting_entity_en_s', 'standing_offer_number_s',
                                     'instrument_type_en_s',
                                     'ministers_office_en_s',
                                     'reporting_period_s',
                                     'owner_org_en_s',
                                     'report_type_en_s'
                                     ]
        self.solr_query_fields_fr = ['ref_number_s^5', 'procurement_id_s^5',
                                     'vendor_name_txt', 'vendor_postal_code_s',
                                     'buyer_name_s',
                                     'contract_year_s', 'contract_month_s',
                                     'economic_object_code_s^4',
                                     'description_txt_fr^3',
                                     'contract_start_s^4', 'contract_delivery_s^4',
                                     'contract_value_fr_s^5', 'original_value_fr_s^4', 'amendment_value_fr_s^4',
                                     'comments_txt_fr', 'additional_comments_txt_fr',
                                     'trade_agreement_exception_fr_s',
                                     'commodity_type_fr_s',
                                     'commodity_code_s',
                                     'country_of_origin_fr_s^2',
                                     'solicitation_procedure_code_fr_s',
                                     'limited_tendering_reason_code_fr_s',
                                     'trade_agreement_exceptions_fr_s',
                                     'aboriginal_business_fr_s',
                                     'intellectual_property_fr_s',
                                     'former_public_servant_fr_s',
                                     'contracting_entity_fr_s', 'standing_offer_number_s',
                                     'instrument_type_fr_s',
                                     'ministers_office_fr_s',
                                     'reporting_period_s',
                                     'owner_org_fr_s',
                                     'report_type_fr_s'
                                     ]


        # These fields are search facets
        self.solr_facet_fields_en = ['{!ex=tag_contract_year_s}contract_year_s',
                                     '{!ex=tag_owner_org_en_s}owner_org_en_s',
                                     '{!ex=tag_contract_value_range_en_s}contract_value_range_en_s',
                                     '{!ex=tag_trade_agreement_en_s}trade_agreement_en_s',
                                     '{!ex=tag_land_claims_en_s}land_claims_en_s',
                                     '{!ex=tag_intellectual_property_en_s}intellectual_property_en_s',
                                     '{!ex=tag_solicitation_procedure_en_s}solicitation_procedure_en_s',
                                     '{!ex=tag_instrument_type_en_s}instrument_type_en_s',
                                     '{!ex=tag_commodity_type_en_s}commodity_type_en_s',
                                     '{!ex=tag_limited_tendering_reason_en_s}limited_tendering_reason_en_s',
                                     '{!ex=tag_trade_agreement_exceptions_en_s}trade_agreement_exceptions_en_s',
                                     '{!ex=tag_former_public_servant_en_s}former_public_servant_en_s',
                                     '{!ex=tag_contracting_entity_en_s}contracting_entity_en_s',
                                     '{!ex=tag_ministers_office_en_s}ministers_office_en_s',
                                     '{!ex=tag_report_type_en_s}report_type_en_s',
                                     ]

        self.solr_facet_fields_fr = ['{!ex=tag_contract_year_s}contract_year_s',
                                     '{!ex=tag_owner_org_fr_s}owner_org_fr_s',
                                     '{!ex=tag_contract_value_range_fr_s}contract_value_range_fr_s',
                                     '{!ex=tag_trade_agreement_fr_s}trade_agreement_fr_s',
                                     '{!ex=tag_land_claims_fr_s}land_claims_fr_s',
                                     '{!ex=tag_intellectual_property_fr_s}intellectual_property_fr_s',
                                     '{!ex=tag_solicitation_procedure_fr_s}solicitation_procedure_fr_s',
                                     '{!ex=tag_instrument_type_fr_s}instrument_type_fr_s',
                                     '{!ex=tag_commodity_type_fr_s}commodity_type_fr_s',
                                     '{!ex=tag_limited_tendering_reason_fr_s}limited_tendering_reason_fr_s',
                                     '{!ex=tag_trade_agreement_exceptions_fr_s}trade_agreement_exceptions_fr_s',
                                     '{!ex=tag_former_public_servant_fr_s}former_public_servant_fr_s',
                                     '{!ex=tag_contracting_entity_fr_s}contracting_entity_fr_s',
                                     '{!ex=tag_ministers_office_fr_s}ministers_office_fr_s',
                                     '{!ex=tag_report_type_fr_s}report_type_fr_s',
                                     ]
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
        solr_search_terms = search_util.get_search_terms(request)
        solr_search_year: str = request.GET.get('ct-search-year', '')  # contract_year_s
        solr_search_orgs: str = request.GET.get('ct-search-orgs', '')  # owner_org_en_s
        solr_search_range: str = request.GET.get('ct-search-dollar-range', '')  # contract_value_range_en_s
        solr_search_agreements: str = request.GET.get('ct-search-agreement', '')  # trade_agreement_en_s
        solr_land_claims: str = request.GET.get('ct-land-claims', '')
        solr_search_ip: str = request.GET.get('ct-search-ip', '')  # intellectual_property_en_s
        solr_search_solicitation: str = request.GET.get('ct-solicitation', '')  # solicitation_procedure_en_s
        solr_search_doc_type: str = request.GET.get('ct-search-doc', '')  # instrument_type_en_s
        solr_search_commodity_type: str = request.GET.get('ct-search-commodity-type', '')  # commodity_type_en_s
        solr_search_tendering: str = request.GET.get('ct-search-tender', '')  # limited_tendering_reason_en_s
        solr_search_exempt: str = request.GET.get('ct-search-exempt', '')  # trade_agreement_exceptions_en_s
        solr_search_fps: str = request.GET.get('ct-search-fps', '')  # former_public_servant_en_s
        solr_search_so: str = request.GET.get('ct-search-so', '')  # contracting_entity_en_s
        solr_search_mo: str = request.GET.get('ct-search-mo', '')  # ministers_office_en_s
        solr_report_type: str = request.GET.get('ct-search-report-type', '')  # report_type_en_s

        if request.LANGUAGE_CODE == 'fr':
            facets_dict = dict(contract_year_s=solr_search_year,
                               owner_org_fr_s=solr_search_orgs,
                               contract_value_range_fr_s=solr_search_range,
                               trade_agreement_fr_s=solr_search_agreements,
                               land_clains_fr_s=solr_land_claims,
                               intellectual_property_fr_s=solr_search_ip,
                               solicitation_procedure_fr_s=solr_search_solicitation,
                               instrument_type_fr_s=solr_search_doc_type,
                               commodity_type_fr_s=solr_search_commodity_type,
                               limited_tendering_reason_fr_s=solr_search_tendering,
                               trade_agreement_exceptions_fr_s=solr_search_exempt,
                               former_public_servant_fr_s=solr_search_fps,
                               contracting_entity_fr_s=solr_search_so,
                               ministers_office_fr_s=solr_search_mo,
                               report_type_fr_s=solr_report_type,
                               )
            solr_fields = self.solr_fields_fr
            solr_search_facets = self.solr_facet_fields_fr
            solr_query_fields = self.solr_query_fields_fr
        else:
            facets_dict = dict(contract_year_s=solr_search_year,
                               owner_org_en_s=solr_search_orgs,
                               contract_value_range_en_s=solr_search_range,
                               trade_agreement_en_s=solr_search_agreements,
                               land_claims_en_s=solr_land_claims,
                               intellectual_property_en_s=solr_search_ip,
                               solicitation_procedure_en_s=solr_search_solicitation,
                               instrument_type_en_s=solr_search_doc_type,
                               commodity_type_en_s=solr_search_commodity_type,
                               limited_tendering_reason_en_s=solr_search_tendering,
                               trade_agreement_exceptions_en_s=solr_search_exempt,
                               former_public_servant_en_s=solr_search_fps,
                               contracting_entity_en_s=solr_search_so,
                               ministers_office_en_s=solr_search_mo,
                               report_type_en_s=solr_report_type,
                               )
            solr_fields = self.solr_fields_en
            solr_search_facets = self.solr_facet_fields_en
            solr_query_fields = self.solr_query_fields_en

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