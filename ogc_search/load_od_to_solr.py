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
        owner_org_titles = str(o['organization']['title']).split('|')
        owner_org_title_en = owner_org_titles[0]
        owner_org_title_fr: str = owner_org_titles[1]
        subjects_en = []
        subjects_fr =[]
        for s in o['subject']:
            subjects_en.append(controlled_lists['subject']['en'][s])
            subjects_fr.append(controlled_lists['subject']['fr'][s])
        resource_type_en = []
        resource_type_fr = []
        resource_fmt = []
        resource_title_en = []
        resource_title_fr = []
        for r in o['resources']:
            resource_type_en.append(controlled_lists['resource_type']['en'][r['resource_type']])
            resource_type_fr.append(controlled_lists['resource_type']['fr'][r['resource_type']])
            resource_fmt.append(r['format'])
            resource_title_en.append([r['name_translated']['en']])
            resource_title_fr.append([r['name_translated']['fr']])
        od_row = {
        'portal_type_en_s': controlled_lists['type']['en'][o['type']],
        'portal_type_fr_s': controlled_lists['type']['fr'][o['type']],
        'collection_type_en_s': controlled_lists['collection']['en'][o['collection']],
        'collection_type_fr_s': controlled_lists['collection']['fr'][o['collection']],
        'jurisdiction_en_s': controlled_lists['jurisdiction']['en'][o['jurisdiction']],
        'jurisdiction_fr_s': controlled_lists['jurisdiction']['fr'][o['jurisdiction']],
        'owner_org_title_en_s': owner_org_title_en,
        'owner_org_title_fr_s': owner_org_title_fr,
        'keywords_en_s': o['keywords']['en'],
        'keywords_fr_s': o['keywords']['fr'],
        'subject_en_s': subjects_en,
        'subject_fr_s': subjects_fr,
        'resource_type_en_s': list(set(resource_type_en)),
        'resource_type_fr_s': list(set(resource_type_fr)),
        'update_cycle_en_s': controlled_lists['frequency']['en'][o['frequency']],
        'update_cycle_fr_s': controlled_lists['frequency']['fr'][o['frequency']],
        'id_name_s': o['name'],
        'owner_org_s': o['organization']['name'],
        'author_s': '' if o['author'] is None else o['author'],
        'description_txt_en': o['notes_translated']['en'],
        'description_txt_fr': o['notes_translated']['fr'],
        'title_en_s': o['title_translated']['en'],
        'title_fr_s': o['title_translated']['fr'],
        'resource_format_s': list(set(resource_fmt)),
        'resource_title_en_s': resource_title_en,
        'resource_title_fr_s': resource_title_fr
        }
