import csv
from django.conf import settings
import os
import pysolr
import urlsafe
import sys
from yaml import load

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ogc_search.settings')

ap_schema = {}
with open(settings.NAP_YAML_FILE, mode='r', encoding='utf8', errors="ignore") as ckan_schema_file:
    ap_schema = load(ckan_schema_file, Loader=Loader)


def get_cs_choices(field_name, lang = 'en'):
    choices_en = {}
    choices_fr = {}
    nap_url_en = {}
    nap_url_fr = {}
    full_text_en = {}
    full_text_fr = {}
    cmt_url_en = {}
    cmt_url_fr = {}
    due_date = {}

    if 'resources' in ap_schema:
        for setting in ap_schema['resources'][0]['fields']:
            if field_name == setting['datastore_id']:
                if 'choices' in setting:
                    for choice in setting['choices'].keys():
                        choices_en[choice] = setting['choices'][choice]['en']
                        choices_fr[choice] = setting['choices'][choice]['fr']
                        if field_name in ('commitments', 'milestones'):
                            nap_url_en[choice] = setting['choices'][choice]['NAP_url']['en']
                            nap_url_fr[choice] = setting['choices'][choice]['NAP_url']['fr']
                        if field_name == 'indicators':
                            cmt_url_en[choice] = setting['choices'][choice]['cmt_url']['en']
                            cmt_url_fr[choice] = setting['choices'][choice]['cmt_url']['fr']
                            due_date[choice] = setting['choices'][choice]['due_date'] if 'due_date' in (setting['choices'][choice]) else ''
                        if field_name in ('milestones', 'indicators'):
                            full_text_en[choice] = setting['choices'][choice]['full_text']['en']
                            full_text_fr[choice] = setting['choices'][choice]['full_text']['fr']
                break
    result_dict = {'en': choices_en, 'fr': choices_fr}
    if field_name in ('commitments', 'milestones'):
        result_dict['nap_url_en'] = nap_url_en
        result_dict['nap_url_fr'] = nap_url_fr
    if field_name in ('milestones', 'indicators'):
        result_dict['full_text_en'] = full_text_en
        result_dict['full_text_fr'] = full_text_fr
    if field_name == 'indicators':
        result_dict['cmt_url_en'] = cmt_url_en
        result_dict['cmt_url_fr'] = cmt_url_fr
        result_dict['due_date'] = due_date
    return result_dict


controlled_lists = {'commitments': get_cs_choices('commitments'),
                    'milestones': get_cs_choices('milestones'),
                    'indicators': get_cs_choices('indicators'),
                    'status': get_cs_choices('status')}

solr = pysolr.Solr(settings.SOLR_NAP)
solr.delete(q='*:*')
solr.commit()

bn_list = []
bulk_size = 10
i = 0
total = 0
with open(sys.argv[1], 'r', encoding='utf-8-sig', errors="ignore") as bn_file:
    nap_reader = csv.DictReader(bn_file, dialect='excel')
    for nap in nap_reader:
        try:
            od_obj = {
                'id': urlsafe.url_part_escape("{0},{1}".format(nap['reporting_period'], nap['indicators'])),
                'commitments_en_s': nap['commitments'] + " - " + controlled_lists['commitments']['en'][nap['commitments']],
                'commitments_fr_s': nap['commitments'] + " - " + controlled_lists['commitments']['fr'][nap['commitments']],
                'commitment_txt_en': controlled_lists['commitments']['en'][nap['commitments']],
                'commitment_txt_fr': controlled_lists['commitments']['fr'][nap['commitments']],
                'milestones_en_s': nap['milestones'],
                'milestones_fr_s': nap['milestones'],
                'indicators_en_s': nap['indicators'],
                'indicators_fr_s': nap['indicators'],
                'status_en_s': controlled_lists['status']['en'][nap['status']],
                'status_fr_s': controlled_lists['status']['fr'][nap['status']],
                'progress_en_s': nap['progress_en'],
                'progress_fr_s': nap['progress_fr'],
                'evidence_en_s': nap['evidence_en'],
                'evidence_fr_s': nap['evidence_fr'],
                'challenges_en_s': nap['challenges_en'],
                'challenges_fr_s': nap['challenges_fr'],
                'reporting_period_s': nap['reporting_period'],
                'commitment_nap_url_en_s': controlled_lists['commitments']['nap_url_en'][nap['commitments']],
                'commitment_nap_url_fr_s': controlled_lists['commitments']['nap_url_fr'][nap['commitments']],
                'milestone_nap_url_en_s': controlled_lists['milestones']['nap_url_en'][nap['milestones']],
                'milestone_nap_url_fr_s': controlled_lists['milestones']['nap_url_fr'][nap['milestones']],
                'ind_full_text_en_s': controlled_lists['indicators']['full_text_en'][nap['indicators']],
                'ind_full_text_fr_s': controlled_lists['indicators']['full_text_fr'][nap['indicators']],
                'cmt_url_en_s': controlled_lists['indicators']['cmt_url_en'][nap['indicators']],
                'cmt_url_fr_s': controlled_lists['indicators']['cmt_url_fr'][nap['indicators']],
                'milestone_full_text_en_s': controlled_lists['milestones']['full_text_en'][nap['milestones']],
                'milestone_full_text_fr_s': controlled_lists['milestones']['full_text_fr'][nap['milestones']],
                'milestone_en_s': controlled_lists['milestones']['en'][nap['milestones']],
                'milestone_fr_s': controlled_lists['milestones']['fr'][nap['milestones']],
                'due_date_s': controlled_lists['indicators']['due_date'][nap['indicators']],
            }
            bi_org_title = str(nap['owner_org_title']).split('|')
            od_obj['owner_org_en_s'] = bi_org_title[0].strip()
            od_obj['owner_org_fr_s'] = bi_org_title[1].strip() if len(bi_org_title) > 1 else bi_org_title[0].strip()
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
