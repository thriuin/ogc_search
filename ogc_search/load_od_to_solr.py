from django.conf import settings
import os
import pysolr
import simplejson as json
import sys
from yaml import load

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ogc_search.settings')

ckan_schema_presets = {}
with open(settings.CKAN_YAML_FILE, mode='r', encoding='utf8', errors="ignore") as ckan_schema_file:
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


controlled_lists = {'subject': get_cs_choices('canada_subject'),
                    'type': get_cs_choices('canada_resource_related_type'),
                    'collection': get_cs_choices('canada_collection'),
                    'jurisdiction': get_cs_choices('canada_jurisdiction'),
                    'resource_type': get_cs_choices('canada_resource_type'),
                    'frequency': get_cs_choices('canada_frequency')}

solr = pysolr.Solr(settings.SOLR_URL)
solr.delete(q='*:*')
solr.commit()

with open(sys.argv[1], 'r', encoding='utf8', errors="ignore") as j:
    od_list = []
    bulk_size = 500
    i = 0
    total = 0
    for jl in j:
        try:
            o = json.loads(jl)
            owner_org_titles = str(o['organization']['title']).split('|')
            owner_org_title_en: str = owner_org_titles[0].strip()
            owner_org_title_fr: str = owner_org_titles[1]
            subjects_en = []
            subjects_fr = []
            for s in o['subject']:
                subjects_en.append(controlled_lists['subject']['en'][s].replace(",", ""))
                subjects_fr.append(controlled_lists['subject']['fr'][s].replace(",", ""))
            resource_type_en = []
            resource_type_fr = []
            resource_fmt = []
            resource_title_en = []
            resource_title_fr = []

            for r in o['resources']:
                resource_type_en.append(
                    controlled_lists['resource_type']['en'][r['resource_type']]
                    if r['resource_type'] in controlled_lists['resource_type']['en'] else '')
                resource_type_fr.append(
                    controlled_lists['resource_type']['fr'][r['resource_type']]
                    if r['resource_type'] in controlled_lists['resource_type']['fr'] else '')
                resource_fmt.append(r['format'])

                if 'en' in r['name_translated']:
                    resource_title_en.append(r['name_translated']['en'])
                elif 'fr-t-en' in r['name_translated']:
                    resource_title_en.append(r['name_translated']['fr-t-en'])
                if 'fr' in r['name_translated']:
                    resource_title_fr.append(r['name_translated']['fr'].strip())
                elif 'en-t-fr' in r['name_translated']:
                    resource_title_fr.append(r['name_translated']['en-t-fr'].strip())

            od_obj = {
                'portal_type_en_s': controlled_lists['type']['en'][o['type']],
                'portal_type_fr_s': controlled_lists['type']['fr'][o['type']],
                'collection_type_en_s': controlled_lists['collection']['en'][o['collection']],
                'collection_type_fr_s': controlled_lists['collection']['fr'][o['collection']],
                'jurisdiction_en_s': controlled_lists['jurisdiction']['en'][o['jurisdiction']],
                'jurisdiction_fr_s': controlled_lists['jurisdiction']['fr'][o['jurisdiction']],
                'owner_org_title_en_s': owner_org_title_en,
                'owner_org_title_fr_s': owner_org_title_fr,
                'subject_en_s': subjects_en,
                'subject_fr_s': subjects_fr,
                'resource_type_en_s': list(set(resource_type_en)),
                'resource_type_fr_s': list(set(resource_type_fr)),
                'update_cycle_en_s': controlled_lists['frequency']['en'][o['frequency']],
                'update_cycle_fr_s': controlled_lists['frequency']['fr'][o['frequency']],
                'id_name_s': o['name'],
                'owner_org_s': o['organization']['name'],
                'author_txt': '' if o['author'] is None else o['author'],
                'description_txt_en': o['notes_translated']['en'] if 'en' in o['notes_translated'] else '',
                'description_txt_fr': o['notes_translated']['fr'] if 'fr' in o['notes_translated'] else '',
                'description_xlt_txt_fr': o['notes_translated']['fr-t-en'] if 'fr-t-en' in o[
                    'notes_translated'] else '',
                'description_xlt_txt_en': o['notes_translated']['en-t-fr'] if 'en-t-f-r' in o[
                    'notes_translated'] else '',
                'title_en_s': str(o['title_translated']['en']).strip() if 'en' in o['title_translated'] else '',
                'title_fr_s': str(o['title_translated']['fr']).strip() if 'fr' in o['title_translated'] else '',
                'title_xlt_fr_s': o['title_translated']['fr-t-en'] if 'fr-t-en' in o['title_translated'] else '',
                'title_xlt_en_s': o['title_translated']['en-t-fr'] if 'en-t-fr' in o['title_translated'] else '',
                'resource_format_s': list(set(resource_fmt)),
                'resource_title_en_s': resource_title_en,
                'resource_title_fr_s': resource_title_fr,
                'last_modified_tdt': o['metadata_modified'] + 'Z',
                'ogp_link_en_s': '{0}{1}'.format(settings.OPEN_DATA_EN_URL_BASE, o['name']),
                'ogp_link_fr_s': '{0}{1}'.format(settings.OPEN_DATA_FR_URL_BASE, o['name']),
            }
            if 'en' in o['keywords']:
                od_obj['keywords_en_s'] = o['keywords']['en']
            elif 'fr-t-en' in o['keywords']:
                od_obj['keywords_en_s'] = o['keywords']['fr-t-en']
            if 'fr' in o['keywords']:
                od_obj['keywords_fr_s'] = o['keywords']['fr']
            elif 'en-t-fr' in o['keywords']:
                od_obj['keywords_fr_s'] = o['keywords']['en-t-fr']
            od_list.append(od_obj)
            i += 1
            if i == bulk_size:
                solr.add(od_list)
                solr.commit()
                od_list = []
                total += i
                print('{0} Records Processed'.format(total))
                i = 0
        except Exception as x:
            print('Error on line {0}: {1}'.format(i, x))

    if len(od_list) > 0:
        solr.add(od_list)
        solr.commit()
        print('{0} Records Processed'.format(total))
