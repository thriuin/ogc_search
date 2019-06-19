import csv
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

si_schema = {}
with open(settings.SI_YAML_FILE, mode='r', encoding='utf8', errors="ignore") as ckan_schema_file:
    si_schema = load(ckan_schema_file, Loader=Loader)


def get_cs_choices(field_name, lang = 'en'):
    choices_en = {}
    choices_fr = {}

    if 'resources' in si_schema:
        for setting in si_schema['resources'][0]['fields']:
            if field_name == setting['datastore_id']:
                if 'choices' in setting:
                    for choice in setting['choices'].keys():
                        choices_en[choice] = setting['choices'][choice]['en']
                        choices_fr[choice] = setting['choices'][choice]['fr']
                break
    return {'en': choices_en, 'fr': choices_fr}


def is_discontinued_id(an_id: str):
    '''
    Temporary fix - to be replaced with new logic - currently a manually curated list of discontinued services
    :param an_id: A service ID
    :return: Falso if the provided service ID is not in the list, otherwise True
    '''
    discontinued_ids = [
        "aafc-aac - 15",
        "aafc-aac - 25",
        "esdc-edsc - 01",
        "esdc-edsc - 02",
        "esdc-edsc - 03",
        "esdc-edsc - 04",
        "esdc-edsc - 05",
        "esdc-edsc - 06",
        "esdc-edsc - 07",
        "esdc-edsc - 08",
        "esdc-edsc - 13",
        "esdc-edsc - 15",
        "esdc-edsc - 26",
        "esdc-edsc - 27",
        "esdc-edsc - 28",
        "esdc-edsc - 33",
        "esdc-edsc - 902",
        "ic - 16",
        "ic - 17",
        "ic - 18",
        "ic - 32",
        "pwgsc-tpsgc - 05",
        "pwgsc-tpsgc - 06",
        "pwgsc-tpsgc - 07",
        "pwgsc-tpsgc - 08",
        "pwgsc-tpsgc - 09",
        "pwgsc-tpsgc - 11",
        "pwgsc-tpsgc - 12",
        "pwgsc-tpsgc - 13",
        "pwgsc-tpsgc - 15",
        "pwgsc-tpsgc - 16",
        "pwgsc-tpsgc - 19",
        "pwgsc-tpsgc - 22",
        "pwgsc-tpsgc - 23",
        "pwgsc-tpsgc - 28",
        "pwgsc-tpsgc - 29",
        "pwgsc-tpsgc - 30",
        "pwgsc-tpsgc - 31",
        "pwgsc-tpsgc - 33",
        "pwgsc-tpsgc - 35",
        "pwgsc-tpsgc - 37",
        "pwgsc-tpsgc - 42",
        "pwgsc-tpsgc - 43",
        "ssc-spc - 10",
        "ssc-spc - 11",
        "ssc-spc - 12",
        "ssc-spc - 22",
        "ssc-spc - 23",
        "ssc-spc - 24",
        "ssc-spc - 30",
    ]
    if an_id in discontinued_ids:
        return True
    else:
        return False


def expand_count_field(field_value, lang):
    if field_value == 'NA' and lang == 'en':
        return 'Not Available'
    elif field_value == 'NA' and lang == 'fr':
        return 'pas disponibles'
    elif field_value == 'ND' and lang == 'en':
        return 'No Data'
    elif field_value == 'ND' and lang == 'fr':
        return 'aucune donnée'
    else:
        return field_value


controlled_lists = {'external_internal': get_cs_choices('external_internal'),
                    'service_type': get_cs_choices('service_type'),
                    'special_designations': get_cs_choices('special_designations'),
                    'client_target_groups': get_cs_choices('client_target_groups'),
                    'service_fee': get_cs_choices('service_fee'),
                    'cra_business_number': get_cs_choices('cra_business_number'),
                    'use_of_sin': get_cs_choices('use_of_sin'),
                    'e_registration': get_cs_choices('e_registration'),
                    'e_authentication': get_cs_choices('e_authentication'),
                    'e_application': get_cs_choices('e_application'),
                    'e_decision': get_cs_choices('e_decision'),
                    'e_issuance': get_cs_choices('e_issuance'),
                    'e_feedback': get_cs_choices('e_feedback'),
                    'client_feedback': get_cs_choices('client_feedback'),
                    }


def get_multivalue_choice(choices, lang, field_values: str):
    results = []
    for field_value in field_values.split(','):
        if field_value in controlled_lists[choices][lang]:
            results.append(controlled_lists[choices][lang][field_value])
        else:
            print("Unknown value {0} for {1}".format(field_value, choices))
    return results


def get_standards_for_service(std_filename, fiscal_year, new_service_id):
    standards = {}
    with open(std_filename, 'r', encoding='utf-8-sig', errors="ignore") as si_std_file:
        si_std_reader = csv.DictReader(si_std_file, dialect='excel')
        for std in si_std_reader:
            old_service_id = str(std['service_id']).split('-')
            old_service_id = old_service_id[1] if len(old_service_id) == 2 else old_service_id[0]
            service_id_int = int(old_service_id)
            old_service_id = str(service_id_int).zfill(2)
            service_id = "{0} - {1}".format(std['owner_org'], old_service_id)
            if new_service_id == service_id and std['fiscal_yr'] == fiscal_year:
                standards[std['service_std_id']] = std
    return standards


solr = pysolr.Solr(settings.SOLR_SI)
solr.delete(q='*:*')
solr.commit()

si_list = []
bulk_size = 10
i = 0
total = 0
with open(sys.argv[1], 'r', encoding='utf-8-sig', errors="ignore") as si_file:
    si_reader = csv.DictReader(si_file, dialect='excel')
    for si in si_reader:
        if (si['fiscal_yr'] != '2017-2018') and (not is_discontinued_id(si['harmonized_service_id'])):
            continue
        try:
            od_obj = dict(id='{0}-{1}-{2}'.format(si['owner_org'], si['fiscal_yr'], si['service_id']),
                          service_id_s=si['harmonized_service_id'], owner_org_s=si['owner_org'],
                          service_name_en_s=si['harmonized_service_name_en'], service_name_fr_s=si['harmonized_service_name_fr'],
                          service_description_en_s=si['service_description_en'],
                          service_description_fr_s=si['service_description_fr'], authority_en_s=si['authority_en'],
                          authority_fr_s=si['authority_fr'], service_url_en_s=si['service_url_en'],
                          service_url_fr_s=si['service_url_fr'], program_name_en_s=str(si['program_name_en']).strip(),
                          program_name_fr_s=str(si['program_name_fr']).strip(), program_id_code_s=si['program_id_code'],
                          online_application_en_s=expand_count_field(si['online_applications'], 'en'),
                          online_application_fr_s=expand_count_field(si['online_applications'], 'fr'),
                          web_visits_info_service_en_s=expand_count_field(si['web_visits_info_service'], 'en'),
                          web_visits_info_service_fr_s=expand_count_field(si['web_visits_info_service'], 'fr'),
                          calls_received_en_s=expand_count_field(si['calls_received'], 'en'),
                          calls_received_fr_s=expand_count_field(si['calls_received'], 'fr'),
                          in_person_applications_en_s=expand_count_field(si['in_person_applications'], 'en'),
                          in_person_applications_fr_s=expand_count_field(si['in_person_applications'], 'fr'),
                          email_applications_en_s=expand_count_field(si['email_applications'], 'en'),
                          email_applications_fr_s=expand_count_field(si['email_applications'], 'fr'),
                          fax_applications_en_s=expand_count_field(si['fax_applications'], 'en'),
                          fax_applications_fr_s=expand_count_field(si['fax_applications'], 'fr'),
                          postal_mail_applications_en_s=expand_count_field(si['postal_mail_applications'], 'en'),
                          postal_mail_applications_fr_s=expand_count_field(si['postal_mail_applications'], 'fr'),
                          special_remarks_en_s=si['special_remarks_en'], special_remarks_fr_s=si['special_remarks_fr'],
                          fiscal_year_s=si['fiscal_yr'],
                          external_internal_en_s=controlled_lists['external_internal']['en'][si['external_internal']],
                          external_internal_fr_s=controlled_lists['external_internal']['fr'][si['external_internal']],
                          service_type_en_s=controlled_lists['service_type']['en'][si['service_type']],
                          service_type_fr_s=controlled_lists['service_type']['fr'][si['service_type']],
                          special_designations_en_s=str(controlled_lists['special_designations']['en'][
                              si['special_designations']]),
                          special_designations_fr_s=str(controlled_lists['special_designations']['fr'][
                              si['special_designations']]),
                          client_target_groups_en_s=get_multivalue_choice('client_target_groups','en',
                              si['client_target_groups']),
                          client_target_groups_fr_s=get_multivalue_choice('client_target_groups','fr',
                              si['client_target_groups']),
                          service_fee_en_s=controlled_lists['service_fee']['en'][si['service_fee']],
                          service_fee_fr_s=controlled_lists['service_fee']['fr'][si['service_fee']],
                          cra_business_number_en_s=controlled_lists['cra_business_number']['en'][
                              si['cra_business_number']],
                          cra_business_number_fr_s=controlled_lists['cra_business_number']['fr'][
                              si['cra_business_number']],
                          use_of_sin_en_s=controlled_lists['use_of_sin']['en'][si['use_of_sin']] if not si['use_of_sin'] == '' else '',
                          use_of_sin_fr_s=controlled_lists['use_of_sin']['fr'][si['use_of_sin']] if not si['use_of_sin'] == '' else '',
                          e_registration_en_s=controlled_lists['e_registration']['en'][si['e_registration']],
                          e_registration_fr_s=controlled_lists['e_registration']['fr'][si['e_registration']],
                          e_authentication_en_s=controlled_lists['e_authentication']['en'][si['e_authentication']],
                          e_authentication_fr_s=controlled_lists['e_authentication']['fr'][si['e_authentication']],
                          e_application_en_s=controlled_lists['e_application']['en'][si['e_application']],
                          e_application_fr_s=controlled_lists['e_application']['fr'][si['e_application']],
                          e_decision_en_s=controlled_lists['e_decision']['en'][si['e_decision']],
                          e_decision_fr_s=controlled_lists['e_decision']['fr'][si['e_decision']],
                          e_issuance_en_s=controlled_lists['e_issuance']['en'][si['e_issuance']],
                          e_issuance_fr_s=controlled_lists['e_issuance']['fr'][si['e_issuance']],
                          e_feedback_en_s=controlled_lists['e_feedback']['en'][si['e_feedback']],
                          e_feedback_fr_s=controlled_lists['e_feedback']['fr'][si['e_feedback']],
                          client_feedback_en_s=get_multivalue_choice('client_feedback','en',si['client_feedback']) if not si['client_feedback'] == '' else '',
                          client_feedback_fr_s=get_multivalue_choice('client_feedback','fr',si['client_feedback']) if not si['client_feedback'] == '' else '')

            od_obj['new_service_id_s'] = si['harmonized_service_id']
            standards = get_standards_for_service(sys.argv[2], od_obj['fiscal_year_s'], si['harmonized_service_id'])
            if len(standards) > 0:
                standards_list = []
                for std in standards:
                    std_dict = {'service_std_id': standards[std]['service_std_id'],
                                'service_std_en': standards[std]['service_std_en'],
                                'service_std_fr': standards[std]['service_std_fr'],
                                'service_std_url_en': standards[std]['service_std_url_en'],
                                'service_std_url_fr': standards[std]['service_std_url_fr'],
                                'service_std_type': standards[std]['service_std_type'],
                                'service_std_target': standards[std]['service_std_target'],
                                'q1_performance_result': standards[std]['q1_performance_result'],
                                'q1_business_volume': standards[std]['q1_business_volume'],
                                'q2_performance_result': standards[std]['q2_performance_result'],
                                'q2_business_volume': standards[std]['q2_business_volume'],
                                'q3_performance_result': standards[std]['q3_performance_result'],
                                'q3_business_volume': standards[std]['q3_business_volume'],
                                'q4_performance_result': standards[std]['q4_performance_result'],
                                'q4_business_volume': standards[std]['q4_business_volume'],
                                }
                    standards_list.append(std_dict)
                od_obj['standards'] = standards_list

            bi_org_title = str(si['owner_org_title']).split('|')
            od_obj['owner_org_en_s'] = bi_org_title[0].strip()
            od_obj['owner_org_fr_s'] = bi_org_title[1].strip()

            si_list.append(od_obj)
            i += 1
            total += 1
            if i == bulk_size:
                solr.add(si_list)
                solr.commit()
                si_list = []
                print('{0} Records Processed'.format(total))
                i = 0
        except Exception as x:
            print('Error on row {0}: {1}'.format(i, x))

    if len(si_list) > 0:
        solr.add(si_list)
        solr.commit()
        print('{0} Records Processed'.format(total))
