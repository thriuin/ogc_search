import csv
from datetime import datetime
from django.conf import settings
import os
import pysolr
from search_util import get_choices
import sys
from yaml import load

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ogc_search.settings')

bn_schema = {}
with open(settings.BRIEF_NOTE_YAML_FILE, mode='r', encoding='utf8', errors="ignore") as ckan_schema_file:
    bn_schema = load(ckan_schema_file, Loader=Loader)


controlled_lists = {'addressee': get_choices('addressee', bn_schema),
                    'action_required': get_choices('action_required', bn_schema)}

solr = pysolr.Solr(settings.SOLR_BN)
solr.delete(q='*:*')
solr.commit()

bn_list = []
bulk_size = 500
i = 0
total = 0
with open(sys.argv[1], 'r', encoding='utf-8-sig', errors="ignore") as bn_file:
    bn_reader = csv.DictReader(bn_file, dialect='excel')
    for bn in bn_reader:
        try:
            od_obj = {
                'id': bn['owner_org'] + bn['tracking_number'],
                'tracking_number_s': bn['tracking_number'],
                'title_en_s': bn['title_en'],
                'title_fr_s': bn['title_fr'],
                'org_sector_en_s': bn['originating_sector_en'],
                'org_sector_fr_s': bn['originating_sector_fr'],
                'addressee_en_s': controlled_lists['addressee']['en'][bn['addressee']],
                'addressee_fr_s': controlled_lists['addressee']['fr'][bn['addressee']],
                'action_required_en_s': controlled_lists['action_required']['en'][bn['action_required']],
                'action_required_fr_s': controlled_lists['action_required']['fr'][bn['action_required']],
                'additional_information_en_s':
                    bn['additional_information_en'] if 'additional_information_en' in bn else '',
                'additional_information_fr_s':
                    bn['additional_information_fr'] if 'additional_information_fr' in bn else '',
            }
            date_received = datetime.strptime(bn['date_received'], '%Y-%m-%d')
            od_obj['date_received_tdt'] = date_received
            od_obj['date_received_fmt_s'] = bn['date_received']
            od_obj['month_i'] = date_received.month
            od_obj['year_i'] = date_received.year
            bi_org_title = str(bn['owner_org_title']).split('|')
            od_obj['owner_org_en_s'] = bi_org_title[0].strip()
            od_obj['owner_org_fr_s'] = bi_org_title[1].strip()
            bn_list.append(od_obj)
            i += 1
            total += 1
            if i == bulk_size:
                solr.add(bn_list)
                solr.commit()
                bn_list = []
                print('{0} Records Processed'.format(total))
                i = 0
        except Exception as x:
            print('Error on row {0}: {1}'.format(i, x))

    if len(bn_list) > 0:
        solr.add(bn_list)
        solr.commit()
        print('{0} Records Processed'.format(total))
