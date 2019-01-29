import datetime
import os
import simplejson as json
import sys
from django.core.wsgi import get_wsgi_application


application = get_wsgi_application()
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ogc_search.settings')

from open_data.models import QueryLog

with open(sys.argv[1], 'r', encoding='utf8', errors="ignore") as qlog:
    i = 0
    total = 0
    for qentry in qlog:
        try:
            qd = json.loads(qentry)
            path = qd.get('path', '')
            path = path.strip('/')
            path_parts = path.split('/')
            if len(path_parts) == 2:
                language = path_parts[0]
                action = path_parts[1]
                timestamp_str = qd.get('timestamp', '')
                if not timestamp_str == '':
                    timestamp = datetime.datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S")
                search_terms = qd.get('search_text', '')
                organization_terms = qd.get('od-search-orgs', '')
                portal_terms = qd.get('od-search-portal', '')
                jurisdiction_terms = qd.get('od-search-jur', '')
                collection_terms = qd.get('od-search-col', '')
                keyword_terms = qd.get('od-search-keywords', '')
                subject_terms = qd.get('od-search-subjects', '')
                format_terms = qd.get('od-search-format', '')
                res_type_terms = qd.get('od-search-rsct', '')
                frequency_terms = qd.get('od-search-update', '')
                log_entry = QueryLog(
                    language=language,
                    action=action,
                    timestamp=timestamp,
                    search_terms=search_terms,
                    organization_terms=organization_terms,
                    portal_terms=portal_terms,
                    jurisdiction_terms=jurisdiction_terms,
                    collection_terms=collection_terms,
                    keyword_terms=keyword_terms,
                    subject_terms=subject_terms,
                    format_terms=format_terms,
                    res_type_terms=res_type_terms,
                    frequency_terms=frequency_terms)
                log_entry.save()
        except Exception as x:
            print('Error on line {0}: {1}'.format(i, x))
            pass
        i += 1
