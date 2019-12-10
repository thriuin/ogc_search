import csv
import json
from datetime import datetime
from django.conf import settings
import os
import pysolr
from search_util import get_bilingual_field, get_choices, get_choices_json, get_field, get_lookup_field, \
    get_choice_field, get_bilingual_dollar_range
import sys
from yaml import load
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

BULK_SIZE = 1000
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ogc_search.settings')


def get_ministers():
    choices_ministers = {}
    file_name = settings.MINISTER_JSON_FILE
    with open(file_name, 'r', encoding='utf8') as fp:
        choices = json.load(fp)
        for choice in choices.keys():
            choices_ministers[choice] = choice
    return {'en': choices_ministers, 'fr': choices_ministers}


def get_minister_positions(minister, date_received, lang_code, status):
    file_name = settings.MINISTER_JSON_FILE
    minister_positions = []
    with open(file_name, 'r', encoding='utf8') as fp:
        choices = json.load(fp)
        for choice in choices.keys():
            if choice == minister:
                for position in choices[choice]['positions_' + lang_code]:
                    start_date = datetime.strptime(position['start_date'], '%Y-%m-%dT%H:%M:%S')
                    date_rec = datetime.strptime(date_received, '%Y-%m-%d')
                    if position['end_date']:
                        end_date = datetime.strptime(position['end_date'], '%Y-%m-%dT%H:%M:%S')
                    else:
                        end_date = datetime.now()
                    if start_date <= date_rec <= end_date:
                        if status and position['end_date']:
                            if lang_code == 'fr':
                                minister_positions.append('Précédent ' + position['title_' + lang_code])
                            else:
                                minister_positions.append('Former ' + position['title_' + lang_code])
                        else:
                            minister_positions.insert(0, position['title_' + lang_code])
    return minister_positions


def get_minister_status(minister, lang_code):
    file_name = settings.MINISTER_JSON_FILE
    with open(file_name, 'r', encoding='utf8') as fp:
        choices = json.load(fp)
        for choice in choices.keys():
            if choice == minister:
                if choices[choice]['status']:
                    if lang_code == 'fr':
                        return 'Présent'
                    else:
                        return 'Current'
                else:
                    if lang_code == 'fr':
                        return 'Précédent'
                    else:
                        return 'Former'


with open(settings.QP_YAML_FILE, mode='r', encoding='utf8', errors="ignore") as ckan_schema_file:
    schema = load(ckan_schema_file, Loader=Loader)

controlled_lists = {'minister': get_choices_json(settings.MINISTER_JSON_FILE)}
controlled_list_minister = {'minister': get_ministers()}

solr = pysolr.Solr(settings.SOLR_QP)
solr.delete(q='*:*')
solr.commit()

solrBatch = []
i = 0
total = 0
with open(sys.argv[1], 'r', encoding='utf-8-sig', errors="ignore") as file:
    reader = csv.DictReader(file, dialect='excel')
    for csvRow in reader:
        total += 1
        try:
            solrDoc = {
                'id': "{0}_{1}".format(csvRow['reference_number'], csvRow['owner_org']),
                'owner_org_s': get_field(csvRow, 'owner_org'),
                'reference_number_s': get_field(csvRow, 'reference_number'),
                'title_en_s': get_field(csvRow, 'title_en'),
                'title_fr_s': get_field(csvRow, 'title_fr').title(),
                'minister_s': get_choice_field(controlled_list_minister, csvRow, 'minister', 'en', 'Unspecified'),
                'minister_en_txt': get_choice_field(controlled_lists, csvRow, 'minister', 'en', 'Unspecified'),
                'minister_fr_txt': get_choice_field(controlled_lists, csvRow, 'minister', 'fr', 'Unspecified'),
                'minister_position_en_s': get_minister_positions(csvRow['minister'], csvRow['date_received'], 'en', False),
                'minister_position_fr_s': get_minister_positions(csvRow['minister'], csvRow['date_received'], 'fr', False),
                'minister_position_en_txt': get_minister_positions(csvRow['minister'], csvRow['date_received'], 'en', True),
                'minister_position_fr_txt': get_minister_positions(csvRow['minister'], csvRow['date_received'], 'fr', True),
                'minister_status_en_s': get_minister_status(csvRow['minister'], 'en'),
                'minister_status_fr_s': get_minister_status(csvRow['minister'], 'fr'),
                'question_en_s': str(get_field(csvRow, 'question_en')).strip(),
                'question_fr_s': str(get_field(csvRow, 'question_fr')).strip(),
                'background_en_s': str(get_field(csvRow, 'background_en')).strip(),
                'background_fr_s': str(get_field(csvRow, 'background_fr')).strip(),
                'response_en_s': str(get_field(csvRow, 'response_en')).strip(),
                'response_fr_s': str(get_field(csvRow, 'response_fr')).strip(),
                'additional_information_en_s': str(get_field(csvRow, 'additional_information_en')).strip(),
                'additional_information_fr_s': str(get_field(csvRow, 'additional_information_fr')).strip(),
            }

            if csvRow['date_received']:
                solrDoc['date_received_dt'] = datetime.strptime(csvRow['date_received'], '%Y-%m-%d')
                solrDoc['month_i'] = solrDoc['date_received_dt'].month
                solrDoc['year_i'] = solrDoc['date_received_dt'].year

            org_title = str(csvRow['owner_org_title']).split('|')
            solrDoc['owner_org_en_s'] = org_title[0].strip()
            solrDoc['owner_org_fr_s'] = org_title[1].strip()

            solrBatch.append(solrDoc)
            i += 1
            if i == BULK_SIZE:
                solr.add(solrBatch)
                solr.commit()
                solrBatch = []
                print('{0} csvRows Processed'.format(total))
                i = 0

        except Exception as x:
            print('Error on row {0}: {1}. Row data: {2}'.format(total, x, csvRow))

    if len(solrBatch) > 0:
        solr.add(solrBatch)
        solr.commit()
        print('{0} csvRows Processed'.format(total))