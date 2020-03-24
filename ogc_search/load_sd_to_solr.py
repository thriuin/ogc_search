from babel.dates import format_date
from babel.numbers import format_number
import csv
import json
from datetime import datetime
from django.conf import settings
from math import ceil
import os
import pysolr
from search_util import get_choices, get_choices_json
import sys
from yaml import load
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

BULK_SIZE = 10
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ogc_search.settings')

ds_schema = {}
organizations = {}
reasons = {}
stati = {}
subjects = {}
ckan_ds_records = {}

# Load the controlled list values
with open(settings.SUGGESTED_DS_YAML_FILE, mode='r', encoding='utf8', errors="ignore") as ckan_schema_file:
    ds_schema = load(ckan_schema_file, Loader=Loader)

    for field in ds_schema['dataset_fields']:
        if 'field_name' in field:
            if field['field_name'] == 'reason':
                for choice in field['choices']:
                    reasons[choice['value']] = {'en': choice['label']['en'], 'fr': choice['label']['fr']}
            elif field['field_name'] == 'status':
                for rf in field['repeating_subfields']:
                    if rf['field_name'] == 'reason':
                        for choice in rf['choices']:
                            stati[choice['value']] = {'en': choice['label']['en'], 'fr': choice['label']['fr']}

# load CKAN subject information
with open(settings.CKAN_YAML_FILE, mode='r', encoding='utf8', errors="ignore") as ckan_schema_file:
    ckan_schema = load(ckan_schema_file, Loader=Loader)
    for preset in ckan_schema['presets']:
        if preset['preset_name'] == 'canada_subject':
            for choice in preset['values']['choices']:
                subjects[choice['value']] = {}
                subjects[choice['value']]['en'] = choice['label']['en']
                subjects[choice['value']]['fr'] = choice['label']['fr']

# load the organization information from CKAN
with open(sys.argv[2], 'r', encoding='utf-8-sig', errors="ignore") as org_file:
    orgs = json.load(org_file)
    for org in orgs['result']:
        values = [str(x).strip() for x in org['display_name'].split('|')]
        if len(values) == 1:
            organizations[org['name']] = {'en': values[0], 'fr': values[0]}
        else:
            organizations[org['name']] = {'en': values[0], 'fr': values[1]}

# Load the latest dataset status codes from CKAN. These are loaded from a JSON file generated with the ckanapi utility
# "ckanapi search datasets include_private=true q=type:prop"

with open(sys.argv[3], 'r', encoding='utf-8', errors="ignore") as ckan_file:
    for ckan_record in ckan_file:
        ds = json.loads(ckan_record)
        if 'id' in ds and 'status' in ds:
            ckan_ds_records[ds['id']] = ds['status']


# Set up Solr

solr = pysolr.Solr(settings.SOLR_SD)
solr.delete(q='*:*')
solr.commit()
sd_list = []

# Load the Drupal CSV file
i = 0
total = 0
with open(sys.argv[1], 'r', encoding='utf-8-sig', errors="ignore") as sd_file:
    sd_reader = csv.DictReader(sd_file, dialect='excel')
    for sd in sd_reader:
        try:
            od_obj = {
                'id': sd['uuid'],
                'title_en_s': sd['title_en'],
                'title_fr_s': sd['title_fr'],
                'owner_org_en_s': organizations[sd['organization']]['en'],
                'owner_org_fr_s': organizations[sd['organization']]['fr'],
                'desc_en_s': sd['description_en'],
                'desc_fr_s': sd['description_fr'],
                'linked_ds_s': sd['dataset_suggestion_status_link'],
                'votes': sd['votes'],
                'keywords_txt_en': str(sd['keywords_en']).split(","),
                'keywords_en_s': sd['keywords_en'],
                'keywords_txt_fr': str(sd['keywords_fr']).split(","),
                'keywords_fr_s': sd['keywords_fr'],
                'comments_en_s': sd['additional_comments_and_feedback_en'],
                'comments_fr_s': sd['additional_comments_and_feedback_fr'],
            }
            date_received = datetime.strptime(sd['date_created'], '%Y-%m-%d')
            od_obj['date_received_dt'] = date_received
            od_obj['date_create_en_s'] = format_date(date_received, locale='en')
            od_obj['date_create_fr_s'] = format_date(date_received, locale='fr')

            # Optional field
            if sd['dataset_released_date']:
                date_released = datetime.strptime(sd['dataset_released_date'], '%Y-%m-%d')
                od_obj['date_released_dt'] = date_released
                od_obj['date_released_en_s'] = format_date(date_released, locale='en')
                od_obj['date_released_fr_s'] = format_date(date_released, locale='fr')

            if sd['dataset_suggestion_status'] in stati:
                od_obj['status_en_s'] = stati[sd['dataset_suggestion_status']]['en']
                od_obj['status_fr_s'] = stati[sd['dataset_suggestion_status']]['fr']

            sd_subjects_en = []
            sd_subjects_fr = []
            subject_en = ''
            subject_fr = ''

            if sd['subject']:
                for s in str(sd['subject']).split(','):
                    if s in subjects:
                        sd_subjects_en.append(subjects[s]['en'])
                        sd_subjects_fr.append(subjects[s]['fr'])
            subject_en = ','.join(sd_subjects_en)
            subject_fr = ','.join(sd_subjects_fr)

            od_obj['subjects_en_s'] = sd_subjects_en
            od_obj['subjects_fr_s'] = sd_subjects_fr
            od_obj['subject_list_en_s'] = subject_en
            od_obj['subject_list_fr_s'] = subject_fr

            if sd['reason']:
                if sd['reason'] in reasons:
                    od_obj['reason_en_s'] = reasons[sd['reason']]['en']
                    od_obj['reason_fr_s'] = reasons[sd['reason']]['fr']

            if sd['uuid'] in ckan_ds_records:
                status_msg_en = []
                status_msg_fr = []
                for status_update in ckan_ds_records[sd['uuid']]:
                    status_date = datetime.strptime(status_update['date'], '%Y-%m-%d')
                    fiscal_quarter = int(ceil(status_date.month / 3.)) - 1
                    fiscal_year = status_date.year
                    if fiscal_quarter == 0:
                        fiscal_quarter = 4
                        fiscal_year -= 1
                    status_msg_en.append("{1} Q{0} - {2}".format(fiscal_quarter, fiscal_year,
                                                                 stati[status_update['reason']]['en']))
                    status_msg_fr.append("{1} Q{0} - {2}".format(fiscal_quarter, fiscal_year,
                                                                 stati[status_update['reason']]['fr']))
                status_msg_en.sort()
                status_msg_fr.sort()
                od_obj['status_updates_en_s'] = status_msg_en
                od_obj['status_updates_fr_s'] = status_msg_fr
                od_obj['status_updates_export_en_s'] = "\n".join(status_msg_en)
                od_obj['status_updates_export_fr_s'] = "\n".join(status_msg_fr)
            sd_list.append(od_obj)
            i += 1
            if i == BULK_SIZE:
                solr.add(sd_list)
                solr.commit()
                sd_list = []
                print('{0} Records Processed'.format(i))
                i = 0

        except Exception as x:
            print('Error on row {0}: {1}'.format(i, x))

    if len(sd_list) > 0:
        solr.add(sd_list)
        solr.commit()
        print('{0} Suggested Datasets Processed'.format(total))

