from django.conf import settings
import pysolr

solr = pysolr.Solr(settings.SOLR_URL)
solr.delete(q='*:*')
solr.commit()
