from babel.dates import format_date
import csv
import json
from datetime import datetime
from django.conf import settings
import os
import pysolr
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
sd_status = {}
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
                            sd_status[choice['value']] = {'en': choice['label']['en'], 'fr': choice['label']['fr']}

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
    for org in orgs:
        values = [str(x).strip() for x in org['display_name'].split('|')]
        if len(values) == 1:
            organizations[org['name']] = {'en': values[0], 'fr': values[0]}
        else:
            organizations[org['name']] = {'en': values[0], 'fr': values[1]}

# Load the latest dataset status codes from CKAN. These are loaded from a JSON file generated with the ckanapi utility
# "ckanapi search datasets include_private=true q=type:prop"

with open(sys.argv[3], 'r', encoding='utf-8', errors="ignore") as ckan_file:
    records = ckan_file.readlines()
    for record in  records:
        ds = json.loads(record)
        # Assumption made here that the mandatory 'id', 'status', and 'date_forwarded' fields are present
        if 'id' in ds and 'status' in ds and 'date_forwarded' in ds:
            ckan_ds_records[ds['id']] = {'status': ds['status'], 'date_forwarded': ds['date_forwarded']}

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
        if sd['uuid'] in ckan_ds_records:
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
                    'suggestion_id': sd['suggestion_id']
                }
                date_received = datetime.strptime(sd['date_created'], '%Y-%m-%d')
                od_obj['date_received_dt'] = date_received
                od_obj['date_create_en_s'] = format_date(date_received, locale='en')
                od_obj['date_create_fr_s'] = format_date(date_received, locale='fr')

                date_received = datetime.strptime(ckan_ds_records[sd['uuid']]['date_forwarded'], '%Y-%m-%d')
                od_obj['date_forwarded_dt'] = date_received
                od_obj['date_forwarded_en_s'] = format_date(date_received, locale='en')
                od_obj['date_forwarded_fr_s'] = format_date(date_received, locale='fr')

                # Optional field
                if sd['dataset_released_date']:
                    date_released = datetime.strptime(sd['dataset_released_date'], '%Y-%m-%d')
                    od_obj['date_released_dt'] = date_released
                    od_obj['date_released_en_s'] = format_date(date_released, locale='en')
                    od_obj['date_released_fr_s'] = format_date(date_released, locale='fr')
                else:
                    od_obj['date_released_dt'] = ""
                    od_obj['date_released_en_s'] = "-"
                    od_obj['date_released_fr_s'] = "-"

                # By default, use the status from the Drupal CSV file. However, this value
                # will be overridden by the status from CKAN, if it is set.
                if sd['dataset_suggestion_status'] in sd_status:
                    od_obj['status_en_s'] = sd_status[sd['dataset_suggestion_status']]['en']
                    od_obj['status_fr_s'] = sd_status[sd['dataset_suggestion_status']]['fr']
                else:
                    od_obj['status_en_s'] = "-"
                    od_obj['status_fr_s'] = "-"

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
                else:
                    od_obj['reason_en_s'] = "Not Provided"
                    od_obj['reason_fr_s'] = "Non fourni"

                if sd['dataset_suggestion_status'] in sd_status:
                    od_obj['status_en_s'] = sd_status[sd['dataset_suggestion_status']]['en']
                    od_obj['status_fr_s'] = sd_status[sd['dataset_suggestion_status']]['fr']

                last_status_date = datetime(2000, 1, 1)
                if sd['uuid'] in ckan_ds_records:
                    status_msg_en = []
                    status_msg_fr = []
                    for status_update in ckan_ds_records[sd['uuid']]['status']:
                        status_dict_en = {}
                        status_dict_fr = {}
                        status_date = datetime.strptime(status_update['date'], '%Y-%m-%d')
                        if status_date > last_status_date:
                            last_status_date = status_date
                            od_obj['status_en_s'] = sd_status[status_update['reason']]['en']
                            od_obj['status_fr_s'] = sd_status[status_update['reason']]['fr']

                        status_dict_en['date'] = format_date(status_date, locale='en')
                        status_dict_en['reason'] = sd_status[status_update['reason']]['en']
                        if "comments" in status_update and 'en' in status_update['comments']:
                            status_dict_en['comment'] = status_update['comments']['en']
                        status_msg_en.append(status_dict_en)

                        status_dict_fr['date'] = format_date(status_date, locale='fr')
                        status_dict_fr['reason'] = sd_status[status_update['reason']]['fr']
                        if "comments" in status_update and 'fr' in status_update['comments']:
                            status_dict_fr['comment'] = status_update['comments']['fr']
                        status_msg_fr.append(status_dict_fr)

                    od_obj['status_updates_en_s'] = status_msg_en
                    od_obj['status_updates_fr_s'] = status_msg_fr
                    od_obj['status_updates_export_en_s'] = "\n".join(str(status_msg_en))
                    od_obj['status_updates_export_fr_s'] = "\n".join(str(status_msg_fr))
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
        else:
            print('Missing Drupal Record: ' + sd['uuid'])

    if len(sd_list) > 0:
        solr.add(sd_list)
        solr.commit()
        print('{0} Suggested Datasets Processed'.format(total))
