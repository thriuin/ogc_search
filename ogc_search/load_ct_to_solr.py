from babel.numbers import parse_decimal, format_currency
import csv
from datetime import datetime
from django.conf import settings
import os
import pysolr
from search_util import get_bilingual_field, get_choices, get_choices_json, get_field, get_lookup_field, \
    get_choice_field, get_bilingual_dollar_range, get_choice_lookup_field
import sys
import time
from urlsafe import url_part_escape
from yaml import load
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

BULK_SIZE = 5000
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ogc_search.settings')

gc_schema = {}
with open(settings.CONTRACTS_YAML_FILE, mode='r', encoding='utf8', errors="ignore") as ckan_schema_file:
    gc_schema = load(ckan_schema_file, Loader=Loader)

controlled_lists = {'agreement_type_code': get_choices('agreement_type_code', gc_schema, is_lookup=True,
                                                       extra_lookup='trade_agreement'),
                    'trade_agreement': get_choices('trade_agreement', gc_schema),
                    'land_claims': get_choices('land_claims', gc_schema),
                    'commodity_type': get_choices('commodity_type', gc_schema),
                    'country_of_vendor': get_choices_json(settings.COUNTRY_JSON_FILE),
                    'solicitation_procedure': get_choices('solicitation_procedure', gc_schema),
                    'limited_tendering_reason': get_choices('limited_tendering_reason', gc_schema),
                    'trade_agreement_exceptions': get_choices('trade_agreement_exceptions', gc_schema),
                    'aboriginal_business': get_choices('aboriginal_business', gc_schema),
                    'aboriginal_business_incidental': get_choices('aboriginal_business_incidental', gc_schema),
                    'intellectual_property': get_choices('intellectual_property', gc_schema),
                    'potential_commercial_exploitation': get_choices('potential_commercial_exploitation', gc_schema),
                    'former_public_servant': get_choices('former_public_servant', gc_schema),
                    'contracting_entity': get_choices('contracting_entity', gc_schema),
                    'instrument_type': get_choices('instrument_type', gc_schema),
                    'ministers_office': get_choices('ministers_office', gc_schema),
                    'article_6_exceptions': get_choices('article_6_exceptions', gc_schema),
                    'award_criteria': get_choices('award_criteria', gc_schema),
                    'socioeconomic_indicator': get_choices('socioeconomic_indicator', gc_schema),
                    'document_type_code': get_choices('document_type_code', gc_schema),
                    }

# For now, OGC hs requested that the LCSA and ABSA not be included in the trade agreement facet due to
# uneven implementation of these codes at the present time. Better data should be available in 2022
# 2020-09-11

if datetime.now().year < 2022:
    controlled_lists['agreement_type_code']['en']['A'] = controlled_lists['agreement_type_code']['en']['0']
    controlled_lists['agreement_type_code']['fr']['A'] = controlled_lists['agreement_type_code']['fr']['0']
    controlled_lists['agreement_type_code']['en']['R'] = controlled_lists['agreement_type_code']['en']['0']
    controlled_lists['agreement_type_code']['fr']['R'] = controlled_lists['agreement_type_code']['fr']['0']
    controlled_lists['agreement_type_code']['en']['BA'] = controlled_lists['agreement_type_code']['en']['0']
    controlled_lists['agreement_type_code']['fr']['BA'] = controlled_lists['agreement_type_code']['fr']['0']

solr = pysolr.Solr(settings.SOLR_CT)
solr.delete(q='*:*')
solr.commit()

gc_list = []
i = 0
total = 0
with open(sys.argv[1], 'r', encoding='utf-8-sig', errors="ignore") as gc_file:
    gc_reader = csv.DictReader(gc_file, dialect='excel')
    for gc in gc_reader:
        total += 1
        try:
            od_obj = {
                'id': url_part_escape("{0},{1}".format(gc['owner_org'], gc['reference_number'])),
                'ref_number_s': get_field(gc, 'reference_number'),
                'procurement_id_s': get_field(gc, 'procurement_id'),
                'vendor_name_s': get_field(gc, 'vendor_name').title(),
                'vendor_postal_code_s': get_field(gc, 'vendor_postal_code').capitalize(),
                'buyer_name_s': get_field(gc, 'buyer_name'),
                'economic_object_code_s': get_field(gc, 'economic_object_code'),
                'description_en_s': get_field(gc, 'description_en'),
                'description_fr_s': get_field(gc, 'description_fr'),
                'comments_en_s': get_field(gc, 'comments_en'),
                'comments_fr_s': get_field( gc, 'comments_fr'),
                'additional_comments_en_s': get_field(gc, 'additional_comments_en').strip(),
                'additional_comments_fr_s': get_field(gc, 'additional_comments_fr').strip(),
                'commodity_type_en_s': get_choice_field(controlled_lists, gc, 'commodity_type', 'en',
                                                             'Unspecified'),
                'commodity_type_fr_s': get_choice_field(controlled_lists, gc, 'commodity_type', 'fr',
                                                             'type non spécifié'),
                'commodity_code_s': get_field(gc, 'commodity_code'),
                'country_of_origin_s': get_field(gc, 'country_of_vendor'),
                'country_of_origin_en_s': get_choice_field(controlled_lists, gc, 'country_of_vendor', 'en',
                                                           'Unspecified'),
                'country_of_origin_fr_s': get_choice_field(controlled_lists, gc, 'country_of_vendor', 'fr',
                                                           'type non spécifié'),
                'solicitation_procedure_en_s': get_choice_field(controlled_lists, gc,
                                                                'solicitation_procedure', 'en',
                                                                'Unspecified'),
                'solicitation_procedure_fr_s': get_choice_field(controlled_lists, gc,
                                                                'solicitation_procedure', 'fr',
                                                                'type non spécifié'),
                'limited_tendering_reason_en_s': get_choice_field(controlled_lists, gc,
                                                                  'limited_tendering_reason', 'en',
                                                                  'Unspecified'),
                'limited_tendering_reason_fr_s': get_choice_field(controlled_lists, gc,
                                                                  'limited_tendering_reason', 'fr',
                                                                  'type non spécifié'),
                'trade_agreement_exceptions_en_s': get_choice_field(controlled_lists, gc, 'trade_agreement_exceptions',
                                                                    'en', 'Unspecified'),
                'trade_agreement_exceptions_fr_s': get_choice_field(controlled_lists, gc, 'trade_agreement_exceptions',
                                                                    'fr', 'type non spécifié'),
                'aboriginal_business_en_s': get_choice_field(controlled_lists, gc, 'aboriginal_business', 'en',
                                                             'Unspecified'),
                'aboriginal_business_fr_s': get_choice_field(controlled_lists, gc, 'aboriginal_business', 'fr',
                                                             'type non spécifié'),
                'aboriginal_business_incidental_en_s': get_choice_field(controlled_lists, gc,
                                                                        'aboriginal_business_incidental', 'en',
                                                                        'Unspecified'),
                'aboriginal_business_incidental_fr_s': get_choice_field(controlled_lists, gc,
                                                                        'aboriginal_business_incidental', 'fr',
                                                                        'type non spécifié'),
                'intellectual_property_en_s': get_choice_field(controlled_lists, gc, 'intellectual_property',
                                                               'en', 'Unspecified'),
                'intellectual_property_fr_s': get_choice_field(controlled_lists, gc, 'intellectual_property',
                                                               'fr', 'type non spécifié'),
                'potential_commercial_exploitation_en_s': get_choice_field(controlled_lists, gc,
                                                                           'potential_commercial_exploitation', 'en'),
                'potential_commercial_exploitation_fr_s': get_choice_field(controlled_lists, gc,
                                                                           'potential_commercial_exploitation', 'fr'),
                'former_public_servant_en_s': get_choice_field(controlled_lists, gc, 'former_public_servant', 'en',
                                                               'Unspecified'),
                'former_public_servant_fr_s': get_choice_field(controlled_lists, gc, 'former_public_servant', 'fr',
                                                               'type non spécifié'),
                'contracting_entity_en_s': get_choice_field(controlled_lists, gc, 'contracting_entity', 'en',
                                                            'Unspecified'),
                'contracting_entity_fr_s': get_choice_field(controlled_lists, gc, 'contracting_entity', 'fr',
                                                            'type non spécifié'),
                'standing_offer_number_s': get_field(gc, 'standing_offer_number'),
                'instrument_type_en_s': get_choice_field(controlled_lists, gc, 'instrument_type', 'en',
                                                         'Unspecified'),
                'instrument_type_fr_s': get_choice_field(controlled_lists, gc, 'instrument_type', 'fr',
                                                         'type non spécifié'),
                'ministers_office_en_s': get_choice_field(controlled_lists, gc, 'ministers_office', 'en',
                                                          'Unspecified'),
                'ministers_office_fr_s': get_choice_field(controlled_lists, gc, 'ministers_office', 'fr',
                                                          'type non spécifié'),
                'number_of_bids_s': get_field(gc, 'number_of_bids'),
                'article_6_exceptions_en_s': get_choice_field(controlled_lists, gc, 'article_6_exceptions', 'en',
                                                              'Unspecified'),
                'article_6_exceptions_fr_s': get_choice_field(controlled_lists, gc, 'article_6_exceptions', 'fr',
                                                              'type non spécifié'),
                'award_criteria_en_s': get_choice_field(controlled_lists, gc, 'award_criteria', 'en',
                                                        'Unspecified'),
                'award_criteria_fr_s': get_choice_field(controlled_lists, gc, 'award_criteria', 'fr',
                                                        'type non spécifié'),
                'socioeconomic_indicator_en_s': get_choice_field(controlled_lists, gc, 'socioeconomic_indicator',
                                                                 'en', 'Unspecified'),
                'socioeconomic_indicator_fr_s': get_choice_field(controlled_lists, gc, 'socioeconomic_indicator',
                                                                 'fr', 'type non spécifié'),
                'reporting_period_s': gc['reporting_period'],
                'nil_report_b': 'f',
            }
            od_obj['report_type_en_s'] = od_obj['instrument_type_en_s']
            od_obj['report_type_fr_s'] = od_obj['instrument_type_fr_s']

            working_year = 9999
            if gc['contract_date'] != "":
                contract_dt: datetime = datetime.strptime(gc['contract_date'], '%Y-%m-%d')
                od_obj['contract_date_dt'] = contract_dt.strftime('%Y-%m-%dT00:00:00Z')
                od_obj['contract_date_s'] = gc['contract_date']
                od_obj['contract_year_s'] = str(contract_dt.year)
                od_obj['contract_month_s'] = str("%02d" % contract_dt.month)
                working_year = contract_dt.year
            else:
                od_obj['contract_start_s'] = "-"
                od_obj['contract_year_s'] = ""
                od_obj['contract_month_s'] = ""

            if gc['contract_period_start'] != "":
                contract_start_dt: datetime = datetime.strptime(gc['contract_period_start'], '%Y-%m-%d')
                od_obj['contract_start_dt'] = contract_start_dt.strftime('%Y-%m-%dT00:00:00Z')
                od_obj['contract_start_s'] = gc['contract_period_start']

            if gc['delivery_date'] != "":
                delivery_dt: datetime = datetime.strptime(gc['delivery_date'], '%Y-%m-%d')
                od_obj['contract_delivery_dt'] = delivery_dt.strftime('%Y-%m-%dT00:00:00Z')
                od_obj['contract_delivery_s'] = gc['delivery_date']
            else:
                od_obj['contract_delivery_s'] = "-"

            if gc['contract_value'] != "":
                contract_value = parse_decimal(gc['contract_value'].replace('$', '').replace(',', ''), locale='en')
                od_obj['contract_value_f'] = contract_value
                od_obj['contract_value_en_s'] = format_currency(contract_value, 'CAD', locale='en_CA')
                od_obj['contract_value_fr_s'] = format_currency(contract_value, 'CAD', locale='fr_CA')
            else:
                od_obj['contract_value_en_s'] = "-"
                od_obj['contract_value_fr_s'] = "-"

            if gc['original_value'] != "":
                original_value = parse_decimal(gc['original_value'].replace('$', '').replace(',', ''), locale='en')
                od_obj['original_value_f'] = original_value
                od_obj['original_value_en_s'] = format_currency(original_value, 'CAD', locale='en_CA')
                od_obj['original_value_fr_s'] = format_currency(original_value, 'CAD', locale='fr_CA')
            else:
                od_obj['original_value_en_s'] = 'Unspecified'
                od_obj['original_value_fr_s'] = 'type non spécifié'

            if gc['amendment_value'] != "":
                amendment_value = parse_decimal(gc['amendment_value'].replace('$', '').replace(',', ''), locale='en')
                od_obj['amendment_value_f'] = amendment_value
                od_obj['amendment_value_en_s'] = format_currency(amendment_value, 'CAD', locale='en_CA')
                od_obj['amendment_value_fr_s'] = format_currency(amendment_value, 'CAD', locale='fr_CA')
            else:
                od_obj['amendment_value_en_s'] = "-"
                od_obj['amendment_value_fr_s'] = "-"

            bi_org_title = str(gc['owner_org_title']).split('|')
            od_obj['owner_org_en_s'] = get_bilingual_field(gc,'owner_org_title', 'en')
            od_obj['owner_org_fr_s'] = get_bilingual_field(gc,'owner_org_title', 'fr')

            if gc['agreement_type_code'] != "":
                # Do some data cleanup on the Agreement Type Code
                if gc['agreement_type_code'] == 'O':
                    gc['agreement_type_code'] = '0'
                if gc['agreement_type_code'][0:1] == "0":
                    gc['agreement_type_code'] = '0'
                if gc['agreement_type_code'] == 'A,R':
                    gc['agreement_type_code'] = 'AR'
                if gc['agreement_type_code'] == 'AIT':
                    gc['agreement_type_code'] = 'I'
                gc['agreement_type_code'] = str(gc['agreement_type_code']).upper().strip()
                agreement_types_en = get_lookup_field(controlled_lists, gc, 'agreement_type_code', 'en', ['Unspecified'])
                od_obj['agreement_type_code_en_s'] = agreement_types_en

                agreement_types_fr = get_lookup_field(controlled_lists, gc, 'agreement_type_code', 'fr', ['type non spécifié'])
                od_obj['agreement_type_code_fr_s'] = agreement_types_fr

            else:
                od_obj['agreement_type_code_en_s'] = 'Unspecified'
                od_obj['agreement_type_code_export_en_s'] = 'Unspecified'
                od_obj['agreement_type_code_fr_s'] = 'type non spécifié'
                od_obj['agreement_type_code_export_fr_s'] = 'type non spécifié'

            # Combine all crown owned exemptions into one
            if od_obj['intellectual_property_en_s'].startswith('Crown owned – ex'):
                od_obj['intellectual_property_en_s'] = 'Crown owned – exception'
            if od_obj['intellectual_property_fr_s'].startswith("Droits appartenant à l'État ex"):
                od_obj['intellectual_property_fr_s'] = "Droits appartenant à l'État exception"

            # This insanity is because there are two trade agreement fields in the contracts schema that need to be
            # merged into one field for faceting.

            trade_agreement_en = get_choice_field(controlled_lists, gc, 'trade_agreement', 'en', 'Unspecified'),
            trade_agreement_fr = get_choice_field(controlled_lists, gc, 'trade_agreement', 'fr',
                                                         'type non spécifié'),

            # if trade_agreements was not specified, then use the agreement type code
            if trade_agreement_en and trade_agreement_en[0] == 'Unspecified':
                od_obj['trade_agreement_en_s'] = agreement_types_en
            else:
                od_obj['trade_agreement_en_s'] = trade_agreement_en
            # export multi-value field should be quoted
            od_obj['agreement_type_code_export_en_s'] = ",".join(
                str(code) for code in od_obj['trade_agreement_en_s']
            )

            if (trade_agreement_fr and trade_agreement_fr[0] == 'type non spécifié' ):
                od_obj['trade_agreement_fr_s'] = agreement_types_fr
            else:
                od_obj['trade_agreement_fr_s'] = trade_agreement_fr
            od_obj['agreement_type_code_export_fr_s'] = ",".join(
                str(code) for code in od_obj['trade_agreement_fr_s']
            )

            # OPEN-690 For pre-2022 contracts : If the agreement type is A, B, or BA, then set these two indicators
            # for display on the details page, otherwise set to the empty value "-"
            if working_year < 2022 and gc['agreement_type_code'] == "A":
                od_obj['absa_psar_ind_en_s'] = 'Yes'
                od_obj['absa_psar_ind_fr_s'] = 'Oui'
                od_obj['lcsa_clca_ind_en_s'] = '-'
                od_obj['lcsa_clca_ind_fr_s'] = '-'
            elif working_year < 2022 and gc['agreement_type_code'] == "B":
                od_obj['absa_psar_ind_en_s'] = '-'
                od_obj['absa_psar_ind_fr_s'] = '-'
                od_obj['lcsa_clca_ind_en_s'] = 'Yes'
                od_obj['lcsa_clca_ind_fr_s'] = 'Oui'
            elif working_year < 2022 and gc['agreement_type_code'] == "BA":
                od_obj['absa_psar_ind_en_s'] = 'Yes'
                od_obj['absa_psar_ind_fr_s'] = 'Oui'
                od_obj['lcsa_clca_ind_en_s'] = 'Yes'
                od_obj['lcsa_clca_ind_fr_s'] = 'Oui'
            else:
                od_obj['absa_psar_ind_en_s'] = '-'
                od_obj['absa_psar_ind_fr_s'] = '-'
                od_obj['lcsa_clca_ind_en_s'] = '-'
                od_obj['lcsa_clca_ind_fr_s'] = '-'

            if gc['contract_value']:
                contract_range = get_bilingual_dollar_range(gc['contract_value'])
            else:
                contract_range = get_bilingual_dollar_range(gc['amendment_value'])
            od_obj['contract_value_range_en_s'] = contract_range['en']['range']
            od_obj['contract_value_range_fr_s'] = contract_range['fr']['range']

            if gc['original_value']:
                original_range = get_bilingual_dollar_range(gc['contract_value'])
                od_obj['original_value_range_en_s'] = original_range['en']['range']
                od_obj['original_value_range_fr_s'] = original_range['fr']['range']

            if gc['amendment_value']:
                original_range = get_bilingual_dollar_range(gc['amendment_value'])
                od_obj['amendment_value_range_en_s'] = original_range['en']['range']
                od_obj['amendment_value_range_fr_s'] = original_range['fr']['range']

            if 'land_claims' in gc and gc['land_claims'] != '':
                od_obj['land_claims_en_s'] = get_choice_field(controlled_lists, gc, 'land_claims', 'en', 'Unspecified'),
                od_obj['land_claims_fr_s'] = get_choice_field(controlled_lists, gc, 'land_claims', 'fr',
                                                         'type non spécifié'),
            else:
                od_obj['land_claims_fr_s'] = 'type non spécifié'
                od_obj['land_claims_en_s'] = 'Unspecified'

            gc_list.append(od_obj)
            i += 1
            if i == BULK_SIZE:
                for a in reversed(range(10)):
                    try:
                        solr.add(gc_list)
                        solr.commit()
                        gc_list = []
                        print('{0} Records Processed'.format(total))
                        i = 0
                        break
                    except pysolr.SolrError as sx:
                        if not a:
                            raise
                        print("Solr error: {0}. Waiting to try again ... {1}".format(sx, a))
                        time.sleep((10 - a) * 5)

        except Exception as x:
            print('Error on row {0}: {1}. Row data: {2}'.format(total, x, gc))

    if gc_list:
        for a in reversed(range(10)):
            try:
                solr.add(gc_list)
                solr.commit()
                print('{0} Records Processed'.format(total))
                break
            except pysolr.SolrError as sx:
                if not a:
                    raise
                print("Solr error: {0}. Waiting to try again ... {1}".format(sx, a))
                time.sleep((10 - a) * 5)

# Load the Nothing to Report CSV

gc_list = []
i = 0
total = 0
with open(sys.argv[2], 'r', encoding='utf-8-sig', errors="ignore") as gc_nil_file:
    gc_reader = csv.DictReader(gc_nil_file, dialect='excel')
    for gc in gc_reader:
        try:
            #
            od_obj = {
                'id': url_part_escape("{0},{1}".format(gc['owner_org'], gc['reporting_period'])),
                'owner_org_en_s': get_bilingual_field(gc, 'owner_org_title', 'en').strip(),
                'owner_org_fr_s': get_bilingual_field(gc, 'owner_org_title', 'fr').strip(),
                'reporting_period_s': get_field(gc, 'reporting_period'),
                'nil_report_b': 't',
                'report_type_en_s': 'Nothing To Report',
                'report_type_fr_s': 'Rien à signaler',
            }

            gc_list.append(od_obj)
            i += 1
            total += 1
            if i == BULK_SIZE:
                for a in reversed(range(10)):
                    try:
                        solr.add(gc_list)
                        solr.commit()
                        gc_list = []
                        print('{0} Nil Records Processed'.format(total))
                        i = 0
                        break
                    except pysolr.SolrError as sx:
                        if not a:
                            raise
                        print("Solr error: {0}. Waiting to try again ... {1}".format(sx, a))
                        time.sleep((10 - a) * 5)

        except Exception as x:
            print('Error on row {0}: {1}'.format(total, x))

    if gc_list:
        for a in reversed(range(10)):
            try:
                solr.add(gc_list)
                solr.commit()
                print('{0} Nil Records Processed'.format(total))
                break
            except pysolr.SolrError as sx:
                if not a:
                    raise
                print("Solr error: {0}. Waiting to try again ... {1}".format(sx, a))
                time.sleep((10 - a) * 5)