import csv
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

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ogc_search.settings')


solr = pysolr.Solr(settings.SOLR_ATI)
solr.delete(q='*:*')
solr.commit()

ati_list = []
bulk_size = 500
i = 0
total = 0
with open(sys.argv[1], 'r', encoding='utf-8-sig', errors="ignore") as ati_file:
    ati_reader = csv.DictReader(ati_file, dialect='excel')
    for ati_rec in ati_reader:
        try:
            od_obj = {
                'id': '{0}-{1}'.format(ati_rec['owner_org'], ati_rec['request_number']),
                'request_no_s': ati_rec['request_number'],
                'summary_en_s': ati_rec['summary_en'],
                'summary_fr_s': ati_rec['summary_fr'],
                'month_i': ati_rec['month'],
                'year_i': ati_rec['year'],
                'owner_org_s': ati_rec['owner_org'],
                'umd_i': ati_rec['umd_number'],
                'pages_i': ati_rec['pages'],
                'nil_report_b': 'f',
            }
            bi_org_title = str(ati_rec['owner_org_title']).split('|')
            od_obj['owner_org_en_s'] = bi_org_title[0].strip()
            od_obj['owner_org_fr_s'] = bi_org_title[1].strip() if len(bi_org_title) == 2 else ''
            bi_disposition = str(ati_rec['disposition']).split('/')
            od_obj['disposition_en_s'] = bi_disposition[0].strip()
            od_obj['disposition_fr_s'] = bi_disposition[1].strip() if len(bi_disposition) == 2 else ''

            ati_list.append(od_obj)
            i += 1
            total += 1
            if i == bulk_size:
                solr.add(ati_list)
                solr.commit()
                ati_list = []
                print('{0} Records Processed'.format(total))
                i = 0
        except Exception as x:
            print('Error on row {0}: {1}'.format(i, x))

    if len(ati_list) > 0:
        solr.add(ati_list)
        solr.commit()
        print('{0} Records Processed'.format(total))

if len(sys.argv) < 2:
    exit(code=-1)

ati_list = []
bulk_size = 500
i = 0
total = 0
with open(sys.argv[2], 'r', encoding='utf-8-sig', errors="ignore") as ati_nil_file:
    ati_reader = csv.DictReader(ati_nil_file, dialect='excel')
    for ati_rec in ati_reader:
        try:
            od_obj = {
                'id': '{0}-nil-{1}'.format(ati_rec['owner_org'], i),
                'month_i': ati_rec['month'],
                'year_i': ati_rec['year'],
                'owner_org_s': ati_rec['owner_org'],
                'nil_report_b': 't',
            }
            bi_org_title = str(ati_rec['owner_org_title']).split('|')
            od_obj['owner_org_en_s'] = bi_org_title[0].strip()
            od_obj['owner_org_fr_s'] = bi_org_title[1].strip() if len(bi_org_title) == 2 else ''
            ati_list.append(od_obj)
            i += 1
            total += 1
            if i == bulk_size:
                solr.add(ati_list)
                solr.commit()
                ati_list = []
                print('{0} Records Processed'.format(total))
                i = 0
        except Exception as x:
            print('Error on row {0}: {1}'.format(i, x))

    if len(ati_list) > 0:
        solr.add(ati_list)
        solr.commit()
        print('{0} Records Processed'.format(total))