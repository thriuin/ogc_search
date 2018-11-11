from django.conf import settings
import os
import pysolr
import simplejson as json
import sys
from yaml import load
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ogc_search.settings')

ckan_schema_presets = {}
with open(settings.CKAN_YAML_FILE, encoding='utf-8-sig') as ckan_schema_file:
    ckan_schema_presets = load(ckan_schema_file, Loader=Loader)

def get_cs_choices(field_name, lang = 'en'):
    choices_en = {}
    choices_fr = {}

    if 'presets' in ckan_schema_presets:
        for setting in ckan_schema_presets['presets']:
            if field_name == setting['preset_name']:
                if 'values' in setting:
                    for choice in setting['values']['choices']:
                        choices_en[choice['value']] = choice['label']['en']
                    for choice in setting['values']['choices']:
                        choices_fr[choice['value']] = choice['label']['fr']

    return {'en': choices_en, 'fr': choices_fr}

controlled_lists = {}

controlled_lists['subject'] = get_cs_choices('canada_subject')
controlled_lists['type'] = get_cs_choices('canada_resource_related_type')
controlled_lists['collection'] = get_cs_choices('canada_collection')
controlled_lists['jurisdiction'] = get_cs_choices('canada_jurisdiction')
controlled_lists['subject'] = get_cs_choices('canada_subject')
controlled_lists['resource_type'] = get_cs_choices('canada_resource_type')
controlled_lists['frequency'] = get_cs_choices('canada_frequency')

with open(sys.argv[1], 'r') as j:
    for jl in j:
#for l in sys.stdin:
        o = json.loads(jl)
        od_row = {
        'portal_type_en_s': controlled_lists['type']['en'][o['type']],
        'portal_type_fr_s': controlled_lists['type']['fr'][o['type']],
        'collection_type_en_s': controlled_lists['collection']['en'][o['collection']],
        'collection_type_fr_s': controlled_lists['collection']['fr'][o['collection']],
        # 'jurisdiction_en_s':
        # 'jurisdiction_fr_s':
        # 'owner_org_title_en_s':
        # 'owner_org_title_fr_s':
        # 'keywords_en_s':
        # 'keywords_fr_s':
        # 'subject_en_s':
        # 'subject_fr_s':
        # 'resource_type_en_s':
        # 'resource_type_fr_s':
        # 'update_cycle_en_s':
        # 'update_cycle_fr_s':
        # 'id_name_s':
        # 'owner_org_s':
        # 'author_s':
        # 'description_txt_en':
        # 'description_txt_fr':
        # 'title_en_s':
        # 'title_fr_s':
        # 'resource_title_en_s':
        # 'resource_title_fr_s':
        }
