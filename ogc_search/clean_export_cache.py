import os
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ogc_search.settings')

clean_cmd = "find {0} -name '*.csv' -type f -mmin +30 exec rm {{}}\;".format(settings.EXPORT_FILE_CACHE_DIR)
os.system(clean_cmd)
