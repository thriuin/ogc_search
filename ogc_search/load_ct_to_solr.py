from babel.numbers import parse_decimal, format_currency
import csv
from datetime import datetime
from django.conf import settings
import os
import pysolr
from search_util import get_bilingual_field, get_choices, get_choices_json, get_field, get_lookup_field, \
    get_choice_field
import sys
from yaml import load
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

BULK_SIZE = 500
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ogc_search.settings')

gc_schema = {}
with open(settings.CONTRACTS_YAML_FILE, mode='r', encoding='utf8', errors="ignore") as ckan_schema_file:
    gc_schema = load(ckan_schema_file, Loader=Loader)

controlled_lists = {'commodity_type_code': get_choices('commodity_type_code', gc_schema),
                    'solicitation_procedure_code': get_choices('solicitation_procedure_code', gc_schema),
                    'limited_tendering_reason_code': get_choices('limited_tendering_reason_code', gc_schema),
                    'exemption_code': get_choices('exemption_code', gc_schema),
                    'aboriginal_business': get_choices('aboriginal_business', gc_schema),
                    'intellectual_property_code': get_choices('intellectual_property_code', gc_schema),
                    'standing_offer': get_choices('standing_offer', gc_schema),
                    'document_type_code': get_choices('document_type_code', gc_schema),
                    'country_of_origin': get_choices_json(settings.COUNTRY_JSON_FILE),
                    'agreement_type_code': get_choices('agreement_type_code', gc_schema, is_lookup=True),
                    'potential_commercial_exploitation': get_choices('potential_commercial_exploitation', gc_schema),
                    'former_public_servant': get_choices('former_public_servant', gc_schema),
                    'ministers_office': get_choices('ministers_office', gc_schema)
                    }

solr = pysolr.Solr(settings.SOLR_CT)
solr.delete(q='*:*')
solr.commit()

gc_list = []
i = 0
total = 0
with open(sys.argv[1], 'r', encoding='utf-8-sig', errors="ignore") as gc_file:
    gc_reader = csv.DictReader(gc_file, dialect='excel')
    for gc in gc_reader:
        total += 1
        try:
            od_obj = {
                'id': gc['reference_number'],
                'ref_number_s': get_field(gc, 'reference_number'),
                'procurement_id_s': get_field(gc, 'procurement_id'),
                'vendor_name_s': get_field(gc, 'vendor_name'),
                'economic_object_code_s': get_field(gc, 'economic_object_code'),
                'description_en_s': get_field(gc, 'description_en'),
                'description_fr_s': get_field(gc, 'description_fr'),
                'economic_object_code_s': get_field(gc, 'economic_object_code'),
                'description_en_s': get_field(gc, 'description_en'),
                'description_fr_s': get_field(gc, 'description_fr'),
                'comments_en_s': gc['comments_en'],
                'comments_fr_s': gc['comments_fr'],
                'additional_comments_en_s': gc['additional_comments_en'],
                'additional_comments_fr_s': gc['additional_comments_fr'],
                'commodity_type_code_en_s': get_choice_field(controlled_lists, gc, 'commodity_type_code', 'en'),
                'commodity_type_code_fr_s': get_choice_field(controlled_lists, gc, 'commodity_type_code', 'fr'),
                'commodity_code_s': gc['commodity_code'],
                'country_of_origin_s': gc['country_of_origin'],
                'country_of_origin_txt_en': get_choice_field(controlled_lists, gc, 'country_of_origin', 'en'),
                'country_of_origin_txt_fr': get_choice_field(controlled_lists, gc, 'country_of_origin', 'fr'),
                'solicitation_procedure_code_en_s': get_choice_field(controlled_lists, gc,
                                                                     'solicitation_procedure_code', 'en'),
                'solicitation_procedure_code_fr_s': get_choice_field(controlled_lists, gc,
                                                                     'solicitation_procedure_code', 'fr'),
                'limited_tendering_reason_code_fr_s': get_choice_field(controlled_lists, gc,
                                                                       'limited_tendering_reason_code', 'fr'),
                'exemption_code_en_s': get_choice_field(controlled_lists, gc, 'exemption_code', 'en'),
                'exemption_code_fr_s': get_choice_field(controlled_lists, gc, 'exemption_code', 'fr'),
                'aboriginal_business_en_s': get_choice_field(controlled_lists, gc, 'aboriginal_business', 'en'),
                'aboriginal_business_fr_s': get_choice_field(controlled_lists, gc, 'aboriginal_business', 'fr'),
                'intellectual_property_code_en_s': get_choice_field(controlled_lists, gc, 'intellectual_property_code',
                                                                    'en'),
                'intellectual_property_code_fr_s': get_choice_field(controlled_lists, gc, 'intellectual_property_code',
                                                                    'fr'),
                'potential_commercial_exploitation_en_s': get_choice_field(controlled_lists, gc,
                                                                           'potential_commercial_exploitation', 'en'),
                'potential_commercial_exploitation_fr_s': get_choice_field(controlled_lists, gc,
                                                                           'potential_commercial_exploitation', 'fr'),
                'former_public_servant_en_s': get_choice_field(controlled_lists, gc, 'former_public_servant', 'en'),
                'former_public_servant_fr_s': get_choice_field(controlled_lists, gc, 'former_public_servant', 'fr'),
                'standing_offer_en_s': get_choice_field(controlled_lists, gc, 'standing_offer', 'en'),
                'standing_offer_fr_s': get_choice_field(controlled_lists, gc, 'standing_offer', 'fr'),
                'standing_offer_number_s': gc['standing_offer_number'],
                'document_type_code_en_s': get_choice_field(controlled_lists, gc, 'document_type_code', 'en'),
                'document_type_code_fr_s': get_choice_field(controlled_lists, gc, 'document_type_code', 'fr'),
                'ministers_office_en_s': get_choice_field(controlled_lists, gc, 'ministers_office', 'en'),
                'ministers_office_fr_s': get_choice_field(controlled_lists, gc, 'ministers_office', 'fr'),
                'reporting_period_s': gc['reporting_period'],
            }
            if not gc['contract_period_start'] == "":
                contract_start_dt: datetime = datetime.strptime(gc['contract_period_start'], '%Y-%m-%d')
                od_obj['contract_start_dt'] = contract_start_dt.strftime('%Y-%m-%dT00:00:00Z')
                od_obj['contract_start_s'] = gc['contract_period_start']
            else:
                od_obj['contract_start_s'] = "-"

            if not gc['delivery_date'] == "":
                delivery_dt: datetime = datetime.strptime(gc['delivery_date'], '%Y-%m-%d')
                od_obj['contract_delivery_dt'] = delivery_dt.strftime('%Y-%m-%dT00:00:00Z')
                od_obj['contract_delivery_s'] = gc['delivery_date']
            else:
                od_obj['contract_delivery_s'] = "-"

            if not gc['contract_value'] == "":
                contract_value = parse_decimal(gc['contract_value'].replace('$', '').replace(',', ''), locale='en')
                od_obj['contract_value_f'] = contract_value
                od_obj['contract_value_en_s'] = format_currency(contract_value, 'CAD', locale='en_CA')
                od_obj['contract_value_fr_s'] = format_currency(contract_value, 'CAD', locale='fr_CA')
            else:
                od_obj['contract_value_en_s'] = "-"
                od_obj['contract_value_fr_s'] = "-"

            if not gc['original_value'] == "":
                original_value = parse_decimal(gc['original_value'].replace('$', '').replace(',', ''), locale='en')
                od_obj['original_value_f'] = original_value
                od_obj['original_value_en_s'] = format_currency(original_value, 'CAD', locale='en_CA')
                od_obj['original_value_fr_s'] = format_currency(original_value, 'CAD', locale='fr_CA')
            else:
                od_obj['original_value_en_s'] = '-'
                od_obj['original_value_fr_s'] = '-'

            if not gc['amendment_value'] == "":
                amendment_value = parse_decimal(gc['amendment_value'].replace('$', '').replace(',', ''), locale='en')
                od_obj['amendment_value_f'] = amendment_value
                od_obj['amendment_value_en_s'] = format_currency(amendment_value, 'CAD', locale='en_CA')
                od_obj['amendment_value_fr_s'] = format_currency(amendment_value, 'CAD', locale='fr_CA')
            else:
                od_obj['amendment_value_en_s'] = "-"
                od_obj['amendment_value_fr_s'] = "-"
            
            bi_org_title = str(gc['owner_org_title']).split('|')
            od_obj['owner_org_en_s'] = get_bilingual_field(gc,'owner_org_title', 'en')
            od_obj['owner_org_fr_s'] = get_bilingual_field(gc,'owner_org_title', 'fr')

            if not gc['agreement_type_code'] == "":
                # Do some data cleanup on the Agreement Type Code
                if gc['agreement_type_code'] == 'O':
                    gc['agreement_type_code'] = '0'
                if gc['agreement_type_code'][0:1] == "0":
                    gc['agreement_type_code'] = '0'
                if gc['agreement_type_code'] == 'A,R':
                    gc['agreement_type_code'] = 'AR'
                if gc['agreement_type_code'] == 'AIT':
                    gc['agreement_type_code'] = 'I'
                gc['agreement_type_code'] = str(gc['agreement_type_code']).upper()
                agreement_types = get_lookup_field(controlled_lists, gc, 'agreement_type_code', 'en')
                od_obj['agreement_type_code_en_s'] = agreement_types
                od_obj['agreement_type_code_export_en_s'] = ",".join([str(code) for code in agreement_types])
                agreement_types = get_lookup_field(controlled_lists, gc, 'agreement_type_code', 'fr')
                od_obj['agreement_type_code_fr_s'] = agreement_types
                od_obj['agreement_type_code_export_fr_s'] = ",".join([str(code) for code in agreement_types])
            else:
                od_obj['agreement_type_code_en_s'] = '-'
                od_obj['agreement_type_code_export_en_s'] = '-'
                od_obj['agreement_type_code_fr_s'] = '-'
                od_obj['agreement_type_code_export_fr_s'] = '-'

            gc_list.append(od_obj)
            i += 1
            if i == BULK_SIZE:
                solr.add(gc_list)
                solr.commit()
                gc_list = []
                print('{0} Records Processed'.format(total))
                i = 0

        except Exception as x:
            print('Error on row {0}: {1}. Row data: {2}'.format(total, x, gc))

    if len(gc_list) > 0:
        solr.add(gc_list)
        solr.commit()
        print('{0} Records Processed'.format(total))
