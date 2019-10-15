from babel.numbers import parse_decimal, format_currency
import csv
from datetime import datetime
from django.conf import settings
import os
import pysolr
from search_util import get_bilingual_field, get_choices, get_choices_json, get_field
import sys
from yaml import load
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

BULK_SIZE = 1000
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ogc_search.settings')

gc_schema = {}
with open(settings.SOLR_CT, mode='r', encoding='utf8', errors="ignore") as ckan_schema_file:
    gc_schema = load(ckan_schema_file, Loader=Loader)

controlled_lists = {'commodity_type_code': get_choices('commodity_type_code', gc_schema),
                    'solicitation_procedure_code': get_choices('solicitation_procedure_code', gc_schema),
                    'limited_tendering_reason_code': get_choices('limited_tendering_reason_code', gc_schema),
                    'exemption_code': get_choices('exemption_code', gc_schema),
                    'intellectual_property_code': get_choices('intellectual_property_code', gc_schema),
                    'standing_offer': get_choices('standing_offer', gc_schema),
                    'document_type_code': get_choices('document_type_code', gc_schema),
                    'country_of_origin': get_choices_json(settings.COUNTRY_JSON_FILE),
                    }

solr = pysolr.Solr(settings.SOLR_GC)
solr.delete(q='*:*')
solr.commit()

gc_list = []
i = 0
total = 0
with open(sys.argv[1], 'r', encoding='utf-8-sig', errors="ignore") as gc_file:
    gc_reader = csv.DictReader(gc_file, dialect='excel')
    for gc in gc_reader:
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
                'description_en_s': get_field(gc, 'description_en',)
                'description_fr_s': get_field(gc, 'description_fr'),
                'contract_value_f': gc['contract_value'],
                'contract_value_en_s': gc['contract_value'],
                '': gc[''],
                '': gc[''],
                '': gc[''],
            }
            contract_start_dt: datetime = datetime.strptime(gc['contract_period_start'], '%Y-%m-%d'),
            od_obj['contract_start_dt'] = contract_start_dt.strftime('%Y-%m-%dT00:00:00Z')
            od_obj['contract_start_s'] = gc['contract_period_start']

            delivery_dt: datetime = datetime.strptime(gc['delivery_date'], '%Y-%m-%d'),
            od_obj['contract_delivery_dt'] = delivery_dt.strftime('%Y-%m-%dT00:00:00Z')
            od_obj['contract_delivery_s'] = gc['delivery_date']

            contract_value = parse_decimal(od_obj['contract_value_en_s'].replace('$', '').replace(',', ''), locale='en')
            od_obj['contract_value_f'] = contract_value
            od_obj['contract_value_en_s'] = format_currency(contract_value, 'CAD', locale='en_CA')
            od_obj['contract_value_fr_s'] = format_currency(contract_value, 'CAD', locale='fr_CA')

            bi_org_title = str(gc['owner_org_title']).split('|')
            od_obj['owner_org_en_s'] = get_bilingual_field(gc,'owner_org_title', 'en')
            od_obj['owner_org_fr_s'] = get_bilingual_field(gc,'owner_org_title', 'fr')
        except Exception as x:
            print('Error on row {0}: {1}'.format(total, x))
