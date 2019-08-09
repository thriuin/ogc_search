import csv
from datetime import datetime
from django.conf import settings
import os
import pysolr
from search_util import get_choices, get_choices_json
import sys
from yaml import load

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ogc_search.settings')

gc_schema = {}
with open(settings.GRANTS_YAML_FILE, mode='r', encoding='utf8', errors="ignore") as ckan_schema_file:
    gc_schema = load(ckan_schema_file, Loader=Loader)

controlled_lists = {'agreement_type': get_choices('agreement_type', gc_schema),
                    'recipient_type': get_choices('recipient_type', gc_schema),
                    'recipient_province': get_choices('recipient_province', gc_schema),
                    'country': get_choices_json(settings.COUNTRY_JSON_FILE),
                    'currency': get_choices_json(settings.CURRENCY_JSON_FILE),
                    }

solr = pysolr.Solr(settings.SOLR_GC)
solr.delete(q='*:*')
solr.commit()

gc_list = []
bulk_size = 500
i = 0
total = 0
with open(sys.argv[1], 'r', encoding='utf-8-sig', errors="ignore") as gc_file:
    gc_reader = csv.DictReader(gc_file, dialect='excel')
    for gc in gc_reader:
        try:
            od_obj = {
                'id': "{0}-{1}-{2}".format(gc['owner_org'], gc['ref_number'], gc['amendment_number']),
                'ref_number_s': gc['ref_number'],
                'amendment_number_s': gc['amendment_number'],
                'amendment_date_s': gc['amendment_date'] if 'amendment_date' in gc else '',
                'agreement_type_en_s': controlled_lists['agreement_type']['en'][gc['agreement_type']],
                'agreement_type_fr_s': controlled_lists['agreement_type']['fr'][gc['agreement_type']]
            }
            gc_list.append(od_obj)
            i += 1
            total += 1
            if i == bulk_size:
                solr.add(gc_list)
                solr.commit()
                gc_list = []
                print('{0} Records Processed'.format(total))
                i = 0
        except Exception as x:
            print('Error on row {0}: {1}'.format(i, x))

    if len(gc_list) > 0:
        solr.add(gc_list)
        solr.commit()
        print('{0} Records Processed'.format(total))

