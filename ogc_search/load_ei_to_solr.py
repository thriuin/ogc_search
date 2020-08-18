from babel.dates import format_date
import csv
from datetime import date, datetime
from django.conf import settings
import os
import pysolr
from search_util import get_bilingual_field, get_choices, get_field, get_choice_field
import sys
from urlsafe import url_part_escape
from yaml import load
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

BULK_SIZE = 1000
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ogc_search.settings')

ei_schema = {}
with open(settings.EXPERIMENT_YAML_FILE, mode='r', encoding='utf8', errors="ignore") as ckan_schema_file:
    ei_schema = load(ckan_schema_file, Loader=Loader)

controlled_lists = {'experimental_area': get_choices('experimental_area', ei_schema),
                    'research_design': get_choices('research_design', ei_schema),
                    'status': get_choices('status', ei_schema),
                    }

solr = pysolr.Solr(settings.SOLR_EI)
solr.delete(q='*:*')
solr.commit()

ei_list = []
i = 0
total = 0
with open(sys.argv[1], 'r', encoding='utf-8-sig', errors="ignore") as ei_file:
    ei_reader = csv.DictReader(ei_file, dialect='excel')
    for ei in ei_reader:
        total += 1
        try:
            od_obj = {
                'id': url_part_escape("{0},{1}".format(ei['owner_org'], ei['reference_number'])),
                'ref_number_s': get_field(ei, 'reference_number'),
                'titre_du_projet_en_s': get_field(ei, 'titre_du_projet_en'),
                'titre_du_projet_fr_s': get_field(ei, 'titre_du_projet_fr'),
                'question_de_recherche_en_s': get_field(ei, 'question_de_recherche_en'),
                'question_de_recherche_fr_s': get_field(ei, 'question_de_recherche_fr'),
                'project_summary_en_s': get_field(ei, 'project_summary_en'),
                'project_summary_fr_s': get_field(ei, 'project_summary_fr'),
                'experimental_area_en_s': get_choice_field(controlled_lists, ei, 'experimental_area', 'en',
                                                             'Unspecified'),
                'experimental_area_fr_s': get_choice_field(controlled_lists, ei, 'experimental_area', 'fr',
                                                             'type non spécifié'),
                'research_design_en_s': get_choice_field(controlled_lists, ei, 'research_design', 'en',
                                                           'Unspecified'),
                'research_design_fr_s': get_choice_field(controlled_lists, ei, 'research_design', 'fr',
                                                           'type non spécifié'),
                'design_details_en_s': get_field(ei, 'design_details_en'),
                'design_details_fr_s': get_field(ei, 'design_details_fr'),
                'intervention_en_s': get_field(ei, 'intervention_en'),
                'intervention_fr_s': get_field(ei, 'intervention_fr'),
                'mesure_des_resultats_en_s': get_field(ei, 'mesure_des_resultats_en'),
                'mesure_des_resultats_fr_s': get_field(ei, 'mesure_des_resultats_fr'),
                'resultats_en_s': get_field(ei, 'resultats_en', '-'),
                'resultats_fr_s': get_field(ei, 'resultats_fr', '-'),
                'status_en_s': get_choice_field(controlled_lists, ei, 'status', 'en',
                                                         'Unspecified'),
                'status_fr_s': get_choice_field(controlled_lists, ei, 'status', 'fr',
                                                         'type non spécifié'),
                'lead_branch_en_s': get_field(ei, 'lead_branch_en', '-'),
                'lead_branch_fr_s': get_field(ei, 'lead_branch_fr', '-'),
                'info_supplementaire_en_s': get_field(ei, 'info_supplementaire_en', '-'),
                'info_supplementaire_fr_s': get_field(ei, 'info_supplementaire_fr', '-'),

            }
            if not ei['last_updated'] == "":
                last_updated_datetime: datetime = datetime.strptime(ei['last_updated'], '%Y-%m-%d')
                last_updated_date: date = date(last_updated_datetime.year, last_updated_datetime.month,
                                               last_updated_datetime.day)
                od_obj['last_update_dt'] = last_updated_date.strftime('%Y-%m-%dT00:00:00Z')
                od_obj['last_updated_en_s'] = format_date(last_updated_date, locale='en')
                od_obj['last_updated_fr_s'] = format_date(last_updated_date, locale='fr')
            else:
                od_obj['last_updated'] = "-"

            bi_org_title = str(ei['owner_org_title']).split('|')
            od_obj['owner_org_en_s'] = get_bilingual_field(ei, 'owner_org_title', 'en').strip()
            od_obj['owner_org_fr_s'] = get_bilingual_field(ei, 'owner_org_title', 'fr').strip()

            ei_list.append(od_obj)
            i += 1
            if i == BULK_SIZE:
                solr.add(ei_list)
                solr.commit()
                ei_list = []
                print('{0} Records Processed'.format(total))
                i = 0

        except Exception as x:
            print('Error on row {0}: {1}. Row data: {2}'.format(total, x, ei))

    if len(ei_list) > 0:
        solr.add(ei_list)
        solr.commit()
        print('{0} Records Processed'.format(total))
