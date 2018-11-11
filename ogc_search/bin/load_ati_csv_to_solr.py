import csv
import hashlib
import pysolr

def to_month(value):
    months_en = [
        'January',
        'February',
        'March',
        'April',
        'May',
        'June',
        'July',
        'August',
        'September',
        'October',
        'November',
        'December'
    ]
    months_fr = [
        'janvier',
        'février',
        'mars',
        'avril',
        'mai',
        'juin',
        'juillet',
        'août',
        'septembre',
        'octobre',
        'novembre',
        'décembre'
    ]

    month_int = 0
    try:
        month_int = int(value)
    except ValueError:
        pass
    if month_int < 1 or month_int > 12:
        return '', ''
    else:
        return months_en[month_int - 1], months_fr[month_int - 1]


with open('/home/rthompson/PycharmProjects/ogc_django/ati.csv', encoding='utf-8-sig') as atifile:
    solr = pysolr.Solr('http://127.0.0.1:8983/solr/core_ati_search')
    solr.delete(q='*:*')
    atireader = csv.DictReader(atifile)
    ati_list = []
    bulk_size = 250
    i = 0
    total = 0
    for row in atireader:
        hash_md5 = hashlib.md5()
        hash_md5.update(u"{0}{1}".format(row['request_number'], row['owner_org']).encode('utf-8'))
        ati_id = hash_md5.hexdigest()
        owner_org_titles = str(row['owner_org_title']).split('|')
        owner_org_title_en = owner_org_titles[0]
        owner_org_title_fr = owner_org_titles[1]
        dispositions = str(row['disposition']).split('/')
        disposition_en_s = str(dispositions[0]).strip() if len(dispositions) > 0 else ''
        disposition_fr_s = str(dispositions[1]).strip() if len(dispositions) > 1 else ''
        month_en, month_fr = to_month(row['month'])
        ati_list.append({
            'id': ati_id,
            'year_i': row['year'],
            'month_i': row['month'],
            'search_month_en': month_en,
            'search_month_fr': month_fr,
            'request_number_s': row['request_number'],
            'summary_txt_en': row['summary_en'],
            'summary_txt_fr': row['summary_fr'],
            'disposition_en_s': disposition_en_s,
            'disposition_fr_s': disposition_fr_s,
            'pages_i': row['pages'],
            'owner_org_s': row['owner_org'],
            'owner_org_title_en_s': owner_org_title_en,
            'owner_org_title_fr_s': owner_org_title_fr,
        })
        i += 1
        if i == bulk_size:
            solr.add(ati_list)
            ati_list = []
            total += i
            i = 0
            print("{0} rows added".format(total))
    if len(ati_list) > 0:
        solr.add(ati_list)
        total += len(ati_list)
        print("{0} rows added".format(total))
