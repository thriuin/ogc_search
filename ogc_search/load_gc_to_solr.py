from babel.numbers import parse_decimal, format_currency, NumberFormatError
import csv
from datetime import date
from dateutil import parser
from django.conf import settings
import os
import pysolr
from search_util import get_choices, get_choices_json, SynonymFinder
from urlsafe import url_part_escape
import sys
from yaml import load

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader


fields_with_synonyms = ['recipient_legal_name_txt_en', 'recipient_legal_name_txt_fr', 'recipient_operating_name_txt_en',
                        'recipient_operating_name_txt_fr', 'research_organization_name_txt_en',
                        'research_organization_name_txt_fr', 'program_name_txt_en', 'program_name_txt_fr',
                        'program_purpose_txt_en', 'program_purpose_txt_fr', 'agreement_title_txt_en',
                        'agreement_title_txt_fr']


def get_field(grants, field_key, default_value='-'):
    if field_key not in grants:
        return default_value
    else:
        if len(grants[field_key]) == 0:
            return default_value
        else:
            return grants[field_key]


def get_choice_field(choices, grants, field_key, lang, default_value="-"):
    if field_key not in choices:
        return default_value
    elif field_key not in grants:
        return default_value
    elif grants[field_key] not in choices[field_key][lang]:
        return default_value
    else:
        return choices[field_key][lang][grants[field_key]]


def get_bilingual_field(grants, field_key: str, lang: str, default_value="-"):
    if field_key not in grants:
        return default_value
    elif len(grants[field_key]) == 0:
        return default_value
    else:
        values = grants[field_key].split('|')
        if len(values) == 1:
            return values[0]
        else:
            if lang == 'fr':
                return values[1]
            else:
                return values[0]


BULK_SIZE = 1000
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ogc_search.settings')

sf = SynonymFinder()

gc_schema = {}
with open(settings.GRANTS_YAML_FILE, mode='r', encoding='utf8', errors="ignore") as ckan_schema_file:
    gc_schema = load(ckan_schema_file, Loader=Loader)

controlled_lists = {'agreement_type': get_choices('agreement_type', gc_schema),
                    'recipient_type': get_choices('recipient_type', gc_schema),
                    'recipient_province': get_choices('recipient_province', gc_schema),
                    'recipient_country': get_choices_json(settings.COUNTRY_JSON_FILE),
                    'foreign_currency_type': get_choices_json(settings.CURRENCY_JSON_FILE),
                    }

solr = pysolr.Solr(settings.SOLR_GC)
solr.delete(q='*:*')
solr.commit()

gc_list = []
i = 0
total = 0
with open(sys.argv[1], 'r', encoding='utf-8-sig', errors="ignore") as gc_file:
    gc_reader = csv.DictReader(gc_file, dialect='excel')
    for gc in gc_reader:
        try:
            od_obj = {
                'id': url_part_escape("{0},{1},{2}".format(gc['owner_org'], gc['ref_number'], gc['amendment_number'])),
                'ref_number_s': gc['ref_number'],
                'owner_org_en_s':  get_bilingual_field(gc, 'owner_org_title', 'en').strip(),
                'owner_org_fr_s': get_bilingual_field(gc, 'owner_org_title', 'fr').strip(),
                'amendment_number_s': gc['amendment_number'],
                'amendment_date_s': get_field(gc, 'amendment_date'),
                'agreement_type_en_s': get_choice_field(controlled_lists, gc, 'agreement_type', 'en', "Unspecified"),
                'agreement_type_fr_s': get_choice_field(controlled_lists, gc, 'agreement_type', 'fr', "type non spécifié"),
                'recipient_type_en_s': get_choice_field(controlled_lists, gc, 'recipient_type', 'en'),
                'recipient_type_fr_s': get_choice_field(controlled_lists, gc, 'recipient_type', 'fr'),
                'recipient_business_number_s': get_field(gc, 'recipient_business_number'),
                'recipient_legal_name_txt_en': get_bilingual_field(gc, 'recipient_legal_name', 'en'),
                'recipient_legal_name_txt_fr': get_bilingual_field(gc, 'recipient_legal_name', 'fr'),
                'recipient_operating_name_txt_en': get_bilingual_field(gc, 'recipient_operating_name', 'en'),
                'recipient_operating_name_txt_fr': get_bilingual_field(gc, 'recipient_operating_name', 'fr'),
                'research_organization_name_txt_en': get_bilingual_field(gc, 'research_organization_name', 'en'),
                'research_organization_name_txt_fr': get_bilingual_field(gc, 'research_organization_name', 'fr'),
                'recipient_country_en_s': get_choice_field(controlled_lists, gc, 'recipient_country', 'en'),
                'recipient_country_fr_s': get_choice_field(controlled_lists, gc, 'recipient_country', 'fr'),
                'recipient_province_en_s': get_choice_field(controlled_lists, gc, 'recipient_province', 'en'),
                'recipient_province_fr_s': get_choice_field(controlled_lists, gc, 'recipient_province', 'fr'),
                'recipient_city_en_s': get_bilingual_field(gc, 'recipient_city', 'en'),
                'recipient_city_fr_s': get_bilingual_field(gc, 'recipient_city', 'fr'),
                'recipient_postal_code_txt': get_field(gc, 'recipient_postal_code'),
                'federal_riding_name_txt_en': get_field(gc, 'federal_riding_name_en'),
                'federal_riding_name_txt_fr': get_field(gc, 'federal_riding_name_fr'),
                'federal_riding_number_s': get_field(gc, 'federal_riding_number'),
                'program_name_txt_en': get_field(gc, 'prog_name_en'),
                'program_name_txt_fr': get_field(gc, 'prog_name_fr'),
                'program_purpose_txt_en': get_field(gc, 'prog_purpose_en'),
                'program_purpose_txt_fr': get_field(gc, 'prog_purpose_fr'),
                'agreement_title_txt_en': get_field(gc, 'agreement_title_en'),
                'agreement_title_txt_fr': get_field(gc, 'agreement_title_fr'),
                'agreement_number_s': get_field(gc, 'agreement_number'),
                'agreement_value_en_s': get_field(gc, 'agreement_value'),
                'foreign_currency_type_en_s': get_choice_field(controlled_lists, gc, 'foreign_currency_type', 'en'),
                'foreign_currency_type_fr_s': get_choice_field(controlled_lists, gc, 'foreign_currency_type', 'fr'),
                'foreign_currency_value_s': get_field(gc, 'foreign_currency_value').strip("$"),
                'agreement_start_date_s': get_field(gc, 'agreement_start_date'),
                'agreement_end_date_s': get_field(gc, 'agreement_end_date'),
                'coverage_txt_en': get_bilingual_field(gc, 'coverage', 'en'),
                'coverage_txt_fr': get_bilingual_field(gc, 'coverage', 'fr'),
                'description_txt_en': get_field(gc, 'description_en'),
                'description_txt_fr': get_field(gc, 'description_fr'),
                'naics_identifier_s': get_field(gc, 'naics_identifier'),
                'expected_results_txt_en': get_field(gc, 'expected_results_en'),
                'expected_results_txt_fr': get_field(gc, 'expected_results_fr'),
                'additional_information_txt_en': get_field(gc, 'additional_information_en'),
                'additional_information_txt_fr': get_field(gc, 'additional_information_fr'),
                'report_type_en_s': 'Grants and Contributions',
                'report_type_fr_s': "Subventions et contributions",
                'nil_report_b': 'f',
            }
            # do not accept invalid federal riding numbers
            try:
                int(od_obj['federal_riding_number_s'])
            except ValueError:
                #  May happen with amendments
                od_obj['federal_riding_number_s'] = "-"

            # Set a year for the agreement
            try:
                start_date = parser.parse(od_obj['agreement_start_date_s'])
                od_obj['year_i'] = start_date.year
            except ValueError:
                # May happen with amendments
                pass
            try:
                agreement_value = parse_decimal(od_obj['agreement_value_en_s'].replace('$', '').replace(',', ''), locale='en')
                # Additional formatting for the agreement value
                od_obj['agreement_value_fs'] = agreement_value
                od_obj['agreement_value_en_s'] = format_currency(agreement_value, 'CAD', locale='en_CA')
                od_obj['agreement_value_fr_s'] = format_currency(agreement_value, 'CAD', locale='fr_CA')
                # Set a value range
                if agreement_value < 0:
                    od_obj['agreement_value_range_en_s'] = '(a) Negative'
                    od_obj['agreement_value_range_fr_s'] = '(a) negatif'
                elif agreement_value < 10000:
                    od_obj['agreement_value_range_en_s'] = '(b) Less than $10,000'
                    od_obj['agreement_value_range_fr_s'] = '(b) moins de 10 000 $'
                elif 10000 <= agreement_value < 25000:
                    od_obj['agreement_value_range_en_s'] = '(c) $10,000 - $25,000'
                    od_obj['agreement_value_range_fr_s'] = '(c) de 10 000 $ à 25 000 $'
                elif 25000 <= agreement_value < 100000:
                    od_obj['agreement_value_range_en_s'] = '(d) $25,000 - $100,000'
                    od_obj['agreement_value_range_fr_s'] = '(d) de 25 000 $ à 100 000 $'
                elif 100000 <= agreement_value < 1000000:
                    od_obj['agreement_value_range_en_s'] = '(e) $100,000 - $1,000,000'
                    od_obj['agreement_value_range_fr_s'] = '(e) de 100 000 $ à 1 000 000 $'
                elif 1000000 <= agreement_value < 5000000:
                    od_obj['agreement_value_range_en_s'] = '(f) $1,000,000 - $5,000,000'
                    od_obj['agreement_value_range_fr_s'] = '(f) de 1 000 000 $ à 5 000 000 $'
                else:
                    od_obj['agreement_value_range_en_s'] = '(g) More than $5,000,000'
                    od_obj['agreement_value_range_fr_s'] = '(g) plus de cinq millions $'
            except NumberFormatError:
                pass

            for field_name in fields_with_synonyms:
                if field_name.endswith('en') or field_name.endswith('en_s'):
                    sf.search_text(od_obj[field_name], 'en')
                elif field_name.endswith('fr') or field_name.endswith('fr_s'):
                    sf.search_text(od_obj[field_name], 'fr')
            od_obj['english_synonyms'] = sf.get_synonyms('en')
            od_obj['french_synonyms'] = sf.get_synonyms('fr')
            sf.reset()

            gc_list.append(od_obj)
            i += 1
            total += 1
            if i == BULK_SIZE:
                solr.add(gc_list)
                solr.commit()
                gc_list = []
                print('{0} Records Processed'.format(total))
                i = 0
        except Exception as x:
            print('Error on row {0}: {1}'.format(total, x))

    if len(gc_list) > 0:
        solr.add(gc_list)
        solr.commit()
        print('{0} Records Processed'.format(total))

# Load Nil values

gc_list = []
i = 0
total = 0
with open(sys.argv[2], 'r', encoding='utf-8-sig', errors="ignore") as gc_nil_file:
    gc_reader = csv.DictReader(gc_nil_file, dialect='excel')
    for gc in gc_reader:
        try:
            od_obj = {
                'id': "{0},{1},{2}".format(get_field(gc, 'owner_org'), get_field(gc, 'fiscal_year'), get_field(gc, 'quarter')),
                'owner_org_en_s': get_bilingual_field(gc, 'owner_org_title', 'en').strip(),
                'owner_org_fr_s': get_bilingual_field(gc, 'owner_org_title', 'fr').strip(),
                'fiscal_year_s': get_field(gc, 'fiscal_year'),
                'quarter_s': get_field(gc, 'quarter'),
                'nil_report_b': 't',
                'report_type_en_s': 'Nothing To Report',
                'report_type_fr_s': 'Rien à signaler',
                'amendment_number_s': 'current'
            }
            if len(od_obj['fiscal_year_s']) > 4:
                try:
                    year = int(od_obj['fiscal_year_s'][0:4])
                    if od_obj['quarter_s'] == 'Q1':
                        start_date = date(year, 4, 1)
                    elif od_obj['quarter_s'] == 'Q2':
                        start_date = date(year, 7, 1)
                    elif od_obj['quarter_s'] == 'Q3':
                        start_date = date(year, 10, 1)
                    elif od_obj['quarter_s'] == 'Q4':
                        start_date = date(year + 1, 1, 1)
                    od_obj['agreement_start_date_s'] = start_date.strftime('%Y-%m-%d')
                except ValueError:
                    pass
            gc_list.append(od_obj)
            i += 1
            total += 1
            if i == BULK_SIZE:
                solr.add(gc_list)
                solr.commit()
                gc_list = []
                print('{0} Nil Records Processed'.format(total))
                i = 0
        except Exception as x:
            print('Error on row {0}: {1}'.format(total, x))

    if len(gc_list) > 0:
        solr.add(gc_list)
        solr.commit()
        print('{0} Nil Records Processed'.format(total))