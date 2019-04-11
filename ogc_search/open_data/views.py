from django.conf import settings
from django.http import HttpRequest, HttpResponseRedirect, FileResponse
from django.shortcuts import render, redirect
from django.utils.translation import gettext as _
from django.views.generic import View
import logging
from math import ceil
import csv
import hashlib
import os
import pysolr
import re
import time

logger = logging.getLogger('ogc_search')


def _convert_facet_list_to_dict(facet_list: dict, reverse=False) -> dict:
    """
    Solr returns search facet results in the form of an alternating list. Convert the list into a dictionary key
    on the facet
    :param facet_list: facet list returned by Solr
    :param reverse: boolean flag indicating if the search results should be returned in reverse order
    :return: A dictonary of the facet values and counts
    """
    facet_dict = {}
    for i in range(0, len(facet_list)):
        if i % 2 == 0:
            facet_dict[facet_list[i]] = facet_list[i + 1]
    if reverse:
        rkeys = sorted(facet_dict,  reverse=True)
        facet_dict_r = {}
        for k in rkeys:
            facet_dict_r[k] = facet_dict[k]
        return facet_dict_r
    else:
        return facet_dict


def _calc_pagination_range(results, pagesize, current_page):
    pages = int(ceil(results.hits / pagesize))
    delta = 2
    if current_page > pages:
        current_page = pages
    elif current_page < 1:
        current_page = 1
    left = current_page - delta
    right = current_page + delta + 1
    pagination = []
    spaced_pagination = []

    for p in range(1, pages + 1):
        if (p == 1) or (p == pages) or (left <= p < right):
            pagination.append(p)

    last = None
    for p in pagination:
        if last:
            if p - last == 2:
                spaced_pagination.append(last + 1)
            elif p - last != 1:
                spaced_pagination.append(0)
        spaced_pagination.append(p)
        last = p

    return spaced_pagination

# Credit to https://gist.github.com/kgriffs/c20084db6686fee2b363fdc1a8998792 for this function
def _create_pattern(version):
    return re.compile(
        (
            '[a-f0-9]{8}-' +
            '[a-f0-9]{4}-' +
            version + '[a-f0-9]{3}-' +
            '[89ab][a-f0-9]{3}-' +
            '[a-f0-9]{12}$'
        ),
        re.IGNORECASE
)

# Create your views here.

def default_search(request):
    return redirect('/od')

def handle_404_error(request, exception=None):
    context = dict(LANGUAGE_CODE=request.LANGUAGE_CODE,)
    context["cdts_version"] = settings.CDTS_VERSION
    return render(request, '404.html', context, status=404)


class ODSearchView(View):
    """
    Open Data search view provides an interactive form to allow searching of a custom Solr core that has the data
    from Open Canada.
    """

    def __init__(self):
        super().__init__()
        # French search fields
        self.solr_fields_fr = ("portal_type_fr_s,collection_type_fr_s,jurisdiction_fr_s,owner_org_title_fr_s,"
                               "owner_org_title_txt_fr,subject_fr_s,resource_type_fr_s,update_cycle_fr_s,"
                               "description_txt_fr,description_xlt_txt_fr,title_fr_s,title_txt_fr,title_xlt_fr_s,"
                               "resource_title_fr_s,resource_title_txt_fr,"
                               "keywords_fr_s,keywords_txt_fr,id,_version_,last_modified_tdt,resource_format_s,"
                               "id_name_s")

        self.solr_facet_fields_fr = ['{!ex=tag_portal_type_fr_s}portal_type_fr_s',
                                     '{!ex=tag_collection_type_fr_s}collection_type_fr_s',
                                     '{!ex=tag_jurisdiction_fr_s}jurisdiction_fr_s',
                                     '{!ex=tag_owner_org_title_fr_s}owner_org_title_fr_s',
                                     '{!ex=tag_keywords_fr_s}keywords_fr_s',
                                     '{!ex=tag_subject_fr_s}subject_fr_s',
                                     '{!ex=tag_resource_format_s}resource_format_s',
                                     '{!ex=tag_resource_type_fr_s}resource_type_fr_s',
                                     '{!ex=tag_update_cycle_fr_s}update_cycle_fr_s']
        self.solr_hl_fields_fr = ['description_txt_fr', 'title_txt_fr', 'owner_org_title_txt_fr', 'keywords_txt_fr']
        self.solr_query_fields_fr = ['owner_org_title_txt_fr^2', 'description_txt_fr^3', 'keywords_txt_fr^4',
                                     'title_txt_fr^5', 'author_txt^2', 'resource_title_txt_fr^3', '_text_fr_^0.5']
        self.solr_phrase_fields_fr = ['description_txt_fr~3^10', 'title_txt_fr~3^10']
        self.solr_bigram_fields_fr = ['description_txt_fr', 'title_txt_fr', 'keywords_txt_fr']
        self.solr_facet_limits_fr = {'f.keywords_fr_s.facet.limit': 250,
                                     'f.keywords_fr_s.facet.sort': 'count'}

        # English search fields
        self.solr_fields_en = ("portal_type_en_s,collection_type_en_s,jurisdiction_en_s,owner_org_title_en_s,"
                               "owner_org_title_txt_en,subject_en_s,resource_type_en_s,update_cycle_en_s,"
                               "description_txt_en,description_xlt_txt_fr,title_en_s,title_txt_en,title_xlt_en_s,"
                               "resource_title_en_s,resource_title_txt_en,"
                               "keywords_en_s,keywords_txt_en,id,_version_,last_modified_tdt,"
                               "resource_format_s,id_name_s")
        self.solr_facet_fields_en = ['{!ex=tag_portal_type_en_s}portal_type_en_s',
                                     '{!ex=tag_collection_type_en_s}collection_type_en_s',
                                     '{!ex=tag_jurisdiction_en_s}jurisdiction_en_s',
                                     '{!ex=tag_owner_org_title_en_s}owner_org_title_en_s',
                                     '{!ex=tag_keywords_en_s}keywords_en_s',
                                     '{!ex=tag_subject_en_s}subject_en_s',
                                     '{!ex=tag_resource_format_s}resource_format_s',
                                     '{!ex=tag_resource_type_en_s}resource_type_en_s',
                                     '{!ex=tag_update_cycle_en_s}update_cycle_en_s']
        self.solr_facet_limits_en = {'f.keywords_en_s.facet.limit': 250,
                                     'f.keywords_en_s.facet.sort': 'count'}
        self.solr_hl_fields_en = ['description_txt_en', 'title_txt_en', 'owner_org_title_txt_en', 'keywords_txt_en']
        self.solr_query_fields_en = ['owner_org_title_txt_en^2', 'description_txt_en', 'keywords_txt_en^2',
                                     'title_txt_en^3', 'author_txt', 'resource_title_txt_en^2']
        self.solr_phrase_fields_en = ['description_txt_en~3^10', 'title_txt_en~3^10']
        self.solr_bigram_fields_en = ['description_txt_en', 'title_txt_en', 'keywords_txt_en']
        self.solr_trigram_fields_en = ['description_txt_en', 'title_txt_en']
        self.solr_facet_limits_en = {'f.keywords_en_s.facet.limit': 250,
                                     'f.keywords_en_s.facet.sort': 'count'}

        self.phrase_xtras_en = {
            'hl': 'on',
            'hl.simple.pre': '<mark class="highlight">',
            'hl.simple.post': '</mark>',
            'hl.method': 'unified',
            'hl.snippets': 10,
            'hl.fl': self.solr_hl_fields_en,
            'hl.preserveMulti': 'true',
            'pf': self.solr_phrase_fields_en,
            'ps': 10,
            'mm': '3<70%',
            'bq': 'last_modified_tdt:[NOW/DAY-2YEAR TO NOW/DAY]',
            'pf2': self.solr_bigram_fields_en,
            'pf3': self.solr_bigram_fields_en
        }
        self.phrase_xtras_fr = {
            'hl': 'on',
            'hl.simple.pre': '<mark class="highlight">',
            'hl.simple.post': '</mark>',
            'hl.method': 'unified',
            'hl.snippets': 10,
            'hl.fl': self.solr_hl_fields_fr,
            'hl.preserveMulti': 'true',
            'pf': self.solr_phrase_fields_fr,
            'ps': 10,
            'mm': '3<70%',
            'bq': 'last_modified_tdt:[NOW/DAY-2YEAR TO NOW/DAY]',
            'pf2': self.solr_bigram_fields_fr,
        }
        self.uuid_regex = _create_pattern('[1-5]')

    @staticmethod
    def split_with_quotes(csv_string):
        # As per https://stackoverflow.com/a/23155180
        return re.findall(r'[^"\s]\S*|".+?"', csv_string)

    def solr_query(self, q, startrow='0', pagesize='10', facets={}, language='en', search_text='',
                   sort_order='score asc', ids=''):
        solr = pysolr.Solr(settings.SOLR_URL)
        solr_facets = []

        if language == 'fr':
            extras = {
                'start': startrow,
                'rows': pagesize,
                'facet': 'on',
                'facet.sort': 'index',
                'facet.field': self.solr_facet_fields_fr,
                'fq': solr_facets,
                'fl': self.solr_fields_fr,
                'defType': 'edismax',
                'qf': self.solr_query_fields_fr,
                'sort': sort_order,
            }
            extras.update(self.solr_facet_limits_fr)
        else:
            extras = {
                'start': startrow,
                'rows': pagesize,
                'facet': 'on',
                'facet.sort': 'index',
                'facet.field': self.solr_facet_fields_en,
                'fq': solr_facets,
                'fl': self.solr_fields_en,
                'defType': 'edismax',
                'qf': self.solr_query_fields_en,
                'sort': sort_order,
            }
            extras.update(self.solr_facet_limits_en)

        # Regular search, facets are respected
        if ids == '':
            for facet in facets.keys():
                if facets[facet] != '':
                    facet_terms = facets[facet].split(',')
                    quoted_terms = ['"{0}"'.format(item) for item in facet_terms]
                    facet_text = '{{!tag=tag_{0}}}{0}:({1})'.format(facet, ' OR '.join(quoted_terms))
                    solr_facets.append(facet_text)

            if q != '*':
                if language == 'fr':
                    extras.update(self.phrase_xtras_fr)
                elif language == 'en':
                    extras.update(self.phrase_xtras_en)
        else:
            ids_list = str(ids).split(',')
            q = ""
            for id in ids_list:
                if self.uuid_regex.match(id):
                    q += 'id_s:"{0}" OR '.format(id)
            if q.endswith(' OR '):
                q = q[:-4]

        sr = solr.search(q, **extras)

        # If there are highlighted results, substitute the highlighted field in the doc results

        for doc in sr.docs:
            if doc['id'] in sr.highlighting:
                hl_entry = sr.highlighting[doc['id']]
                for hl_fld_id in hl_entry:
                    if hl_fld_id in doc and len(hl_entry[hl_fld_id]) > 0:
                        if type(doc[hl_fld_id]) is list:
                            # Scan Multi-valued Solr fields for matching highlight fields
                            for y in hl_entry[hl_fld_id]:
                                y_filtered = re.sub('</mark>', '', re.sub(r'<mark class="highlight">', "", y))
                                x = 0
                                for hl_fld_txt in doc[hl_fld_id]:
                                    if hl_fld_txt == y_filtered:
                                        doc[hl_fld_id][x] = y
                                    x += 1
                        else:
                            # Straight-forward field replacement with highlighted text
                            doc[hl_fld_id] = hl_entry[hl_fld_id][0]
        return sr

    def get(self, request):

        # If a list of ids is provided, then the facets and search text are ignored.

        search_text = ''
        solr_search_terms  = ''
        solr_search_portal = ''
        solr_search_col    = ''
        solr_search_jur    = ''
        solr_search_orgs   = ''
        solr_search_keyw   = ''
        solr_search_subj   = ''
        solr_search_fmts   = ''
        solr_search_rsct   = ''
        solr_search_updc   = ''

        solr_search_ids = request.GET.get('ids', '')

        if solr_search_ids == '':
            # Handle search text

            search_text = str(request.GET.get('search_text', ''))
            # Respect quoted strings
            search_terms = self.split_with_quotes(search_text)
            if len(search_terms) == 0:
                solr_search_terms = "*"
            elif len(search_terms) == 1:
                solr_search_terms = '"{0}"'.format(search_terms)
            else:
                solr_search_terms = ' '.join(search_terms)

            # Retrieve any search facets and add to context

            solr_search_portal = request.GET.get('od-search-portal', '')
            solr_search_col    = request.GET.get('od-search-col', '')
            solr_search_jur    = request.GET.get('od-search-jur', '')
            solr_search_orgs   = request.GET.get('od-search-orgs', '')
            solr_search_keyw   = request.GET.get('od-search-keywords', '')
            solr_search_subj   = request.GET.get('od-search-subjects', '')
            solr_search_fmts   = request.GET.get('od-search-format', '')
            solr_search_rsct   = request.GET.get('od-search-rsct', '')
            solr_search_updc   = request.GET.get('od-search-update', '')

        context = dict(search_text=search_text,
                       portal_selected_list=str(solr_search_portal).split(','),
                       portal_selected=solr_search_portal,
                       col_selected_list=str(solr_search_col).split(','),
                       col_selected=solr_search_col,
                       jur_selected_list=str(solr_search_jur).split(','),
                       jur_selected=solr_search_jur,
                       organizations_selected_list=str(solr_search_orgs).split(','),
                       organizations_selected=solr_search_orgs,
                       keyw_selected_list=str(solr_search_keyw).split(','),
                       keyw_selected=solr_search_keyw,
                       subject_selected_list=str(solr_search_subj).split(','),
                       subject_selected=solr_search_subj,
                       format_selected_list=str(solr_search_fmts).split(','),
                       format_selected=solr_search_fmts,
                       rsct_selected_list=str(solr_search_rsct).split(','),
                       rsct_selected=solr_search_rsct,
                       update_selected_list=str(solr_search_updc).split(','),
                       update_selected=solr_search_updc,
                       )

        # Calculate a starting row for the Solr search results. We only retrieve one page at a time

        try:
            page = int(request.GET.get('page', 1))
        except ValueError:
            page = 1
        if page < 1:
            page = 1
        elif page > 10000:  # @magic_number: arbitrary upper range
            page = 10000
        start_row = 10 * (page - 1)

        alerts = []
        if 'Open Maps'in context['col_selected_list'] or 'Cartes Ouvertes' in context['col_selected_list']:
            alerts.append(_('<b>Open Maps</b>: Search for geospatial data or click <b>Add to cart</b> to select multiple datasets to plot on a single map. Click <b>View on Map</b> to visualize and overlay the datasets using a geospatial viewer'))
        if 'Open Information' in context['portal_selected_list'] or  'Information ouverte' in context['portal_selected_list']:
            alerts.append(_('<b></b>Please note that the Open Information Portal contains a sample of government of Canada publications and information resources. For more resources, please visit <a href="http://publications.gc.ca/">Government of Canada Publications</a> and <a href="http://www.bac-lac.gc.ca/">Library and Archives Canada</a>.'))
        context['alerts'] = alerts
        # Set Sort order

        solr_search_sort = request.GET.get('sort', 'last_modified_tdt desc')
        if solr_search_sort not in ['score desc', 'last_modified_tdt desc', 'title_en_s asc']:
            solr_search_sort = 'score desc'
        context['sortby'] = solr_search_sort

        # Search Solr and return results and facets

        if request.LANGUAGE_CODE == 'fr':
            facets_dict = dict(portal_type_fr_s=context['portal_selected'],
                               collection_type_fr_s=context['col_selected'],
                               jurisdiction_fr_s=context['jur_selected'],
                               owner_org_title_fr_s=context['organizations_selected'],
                               keywords_fr_s=context['keyw_selected'],
                               subject_fr_s=context['subject_selected'],
                               resource_format_s=context['format_selected'],
                               resource_type_fr_s=context['rsct_selected'],
                               update_cycle_fr_s=context['update_selected'])
        else:
            facets_dict = dict(portal_type_en_s=context['portal_selected'],
                               collection_type_en_s=context['col_selected'],
                               jurisdiction_en_s=context['jur_selected'],
                               owner_org_title_en_s=context['organizations_selected'],
                               keywords_en_s=context['keyw_selected'],
                               subject_en_s=context['subject_selected'],
                               resource_format_s=context['format_selected'],
                               resource_type_en_s=context['rsct_selected'],
                               update_cycle_en_s=context['update_selected'])

        # Retrieve search results and transform facets results to python dict

        search_results = self.solr_query(solr_search_terms, startrow=str(start_row), pagesize='10', facets=facets_dict,
                                         language=request.LANGUAGE_CODE, search_text=search_text,
                                         sort_order=solr_search_sort, ids=solr_search_ids)

        export_url = "/{0}/od/export/?{1}".format(request.LANGUAGE_CODE, request.GET.urlencode())

        context['export_url'] = export_url

        if request.LANGUAGE_CODE == 'fr':
            context['portal_facets'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['portal_type_fr_s'])
            context['collection_facets'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['collection_type_fr_s'])
            context['jurisdiction_facets'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['jurisdiction_fr_s'])
            context['org_facets_en'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_title_fr_s'])
            context['org_facets_fr'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_title_fr_s'])
            context['keyword_facets'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['keywords_fr_s'])
            context['subject_facets'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['subject_fr_s'])
            context['format_facets'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['resource_format_s'])
            context['type_facets'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['resource_type_fr_s'])
            context['frequency_facets'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['update_cycle_fr_s'])
        else:
            context['portal_facets'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['portal_type_en_s'])
            context['collection_facets'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['collection_type_en_s'])
            context['jurisdiction_facets'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['jurisdiction_en_s'])
            context['org_facets_en'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_title_en_s'])
            context['org_facets_fr'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_title_en_s'])
            context['keyword_facets'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['keywords_en_s'])
            context['subject_facets'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['subject_en_s'])
            context['format_facets'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['resource_format_s'])
            context['type_facets'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['resource_type_en_s'])
            context['frequency_facets'] = _convert_facet_list_to_dict(
                search_results.facets['facet_fields']['update_cycle_en_s'])

        context['results'] = search_results

        # Set up previous and next page numbers

        pagination = _calc_pagination_range(context['results'], 10, page)
        context['pagination'] = pagination
        context['previous_page'] = (1 if page == 1 else page - 1)
        last_page = (pagination[len(pagination) - 1] if len(pagination) > 0 else 1)
        last_page = (1 if last_page < 1 else last_page)
        context['last_page'] = last_page
        next_page = page + 1
        next_page = (last_page if next_page > last_page else next_page)
        context['next_page'] = next_page
        context['currentpage'] = page

        # Base url to link back to Open Data for ht efull record

        context["od_en_url"] = settings.OPEN_DATA_EN_URL_BASE
        context["od_fr_url"] = settings.OPEN_DATA_FR_URL_BASE
        context["od_ds_id"] = settings.OPEN_DATA_DATASET_ID
        context["od_ds_title_en"] = settings.OPEN_DATA_DATASET_TITLE_EN
        context["od_ds_title_fr"] = settings.OPEN_DATA_DATASET_TITLE_FR
        context["cdts_version"] = settings.CDTS_VERSION
        context['od_en_fgp_root'] = settings.OPEN_DATA_EN_FGP_BASE
        context['od_fr_fgp_root'] = settings.OPEN_DATA_FR_FGP_BASE

        return render(request, "od_search.html", context)


class ODExportView(View):
    """
    A view for downloading a simple CSV containing a subset of the fields from the Search View.
    """

    def __init__(self):
        super().__init__()
        self.solr_fields = ['id_s, org_s, title_en_s, title_fr_s, description_en_s, description_fr_s, ogp_link_en_s, ogp_link_fr_s']
        self.solr_query_fields_en = ['owner_org_title_txt_en^2', 'description_txt_en', 'keywords_txt_en^2',
                                     'title_txt_en^3', 'author_txt', 'resource_title_txt_en^2']
        self.solr_query_fields_fr = ['owner_org_title_txt_fr^2', 'description_txt_fr^3', 'keywords_txt_fr^4',
                                     'title_txt_fr^5', 'author_txt^2', 'resource_title_txt_fr^3', '_text_fr_^0.5']
        self.cache_dir = settings.EXPORT_FILE_CACHE_DIR
        if not os.path.exists(self.cache_dir):
            os.mkdir(self.cache_dir)
        self.uuid_regex = _create_pattern('[1-5]')

    def cache_search_results_file(self, cached_filename: str, sr: pysolr.Results):

        if not os.path.exists(cached_filename):
            with open(cached_filename, 'w', newline='', encoding='utf8') as csvfile:
                cache_writer = csv.writer(csvfile, dialect='excel')
                headers = self.solr_fields[0].split(',')
                headers[0] = u'\N{BOM}' + headers[0]
                cache_writer.writerow(headers)
                for i in sr.docs:
                    try:
                        cache_writer.writerow(i.values())
                    except UnicodeEncodeError:
                        pass
        return True

    @staticmethod
    def split_with_quotes(csv_string):
        return re.findall(r'[^"\s]\S*|".+?"', csv_string)

    def solr_query(self, q, facets={}, language='en', sort_order='last_modified_tdt desc', ids=''):

        solr = pysolr.Solr(settings.SOLR_URL, search_handler='/export')
        solr_facets = []
        for facet in facets.keys():
            if facets[facet] != '':
                facet_terms = facets[facet].split(',')
                quoted_terms = ['"{0}"'.format(item) for item in facet_terms]
                facet_text = '{{!tag=tag_{0}}}{0}:({1})'.format(facet, ' OR '.join(quoted_terms))
                solr_facets.append(facet_text)

        if language == 'fr':
            extras = {
                'fq': solr_facets,
                'fl': self.solr_fields,
                'defType': 'edismax',
                'qf': self.solr_query_fields_fr,
                'sort': sort_order,
            }
        else:
            extras = {
                'fq': solr_facets,
                'fl': self.solr_fields,
                'defType': 'edismax',
                'qf': self.solr_query_fields_en,
                'sort': sort_order,
            }
        if not ids == '':
            ids_list = str(ids).split(',')
            q = ""
            for id in ids_list:
                if self.uuid_regex.match(id):
                    q += 'id:{0} OR '.format(id)
            if q.endswith(' OR '):
                q = q[:-4]
        sr = solr.search(q, **extras)
        return sr

    def get(self, request: HttpRequest):

        # Check to see if a recent cached results exists and return that instead if it exists

        hashed_query = hashlib.sha1(request.GET.urlencode().encode('utf8')).hexdigest()
        cached_filename = os.path.join(self.cache_dir, "{}.csv".format(hashed_query))
        if os.path.exists(cached_filename):
            if time.time() - os.path.getmtime(cached_filename) > 600:
                os.remove(cached_filename)
            else:
                if settings.EXPORT_FILE_CACHE_URL == "":
                    return FileResponse(open(cached_filename, 'rb'), as_attachment=True)
                else:
                    return HttpResponseRedirect(settings.EXPORT_FILE_CACHE_URL + "{}.csv".format(hashed_query))

        # If a list of ids is provided, then the facets and search text are ignored.

        search_text = ''
        solr_search_terms = ''
        solr_search_portal = ''
        solr_search_col = ''
        solr_search_jur = ''
        solr_search_orgs = ''
        solr_search_keyw = ''
        solr_search_subj = ''
        solr_search_fmts = ''
        solr_search_rsct = ''
        solr_search_updc = ''

        solr_search_ids = request.GET.get('ids', '')
        if solr_search_ids == '':

            # Handle search text

            search_text = str(request.GET.get('search_text', ''))

            # Respect quoted strings
            search_terms = self.split_with_quotes(search_text)
            if len(search_terms) == 0:
                solr_search_terms = "*"
            elif len(search_terms) == 1:
                solr_search_terms = '"{0}"'.format(search_terms)
            else:
                solr_search_terms = ' '.join(search_terms)

            # Retrieve any search facets and add to context

            solr_search_portal = request.GET.get('od-search-portal', '')
            solr_search_col = request.GET.get('od-search-col', '')
            solr_search_jur = request.GET.get('od-search-jur', '')
            solr_search_orgs = request.GET.get('od-search-orgs', '')
            solr_search_keyw = request.GET.get('od-search-keywords', '')
            solr_search_subj = request.GET.get('od-search-subjects', '')
            solr_search_fmts = request.GET.get('od-search-format', '')
            solr_search_rsct = request.GET.get('od-search-rsct', '')
            solr_search_updc = request.GET.get('od-search-update', '')

        if request.LANGUAGE_CODE == 'fr':
            facets_dict = dict(portal_type_fr_s=solr_search_portal,
                               collection_type_fr_s=solr_search_col,
                               jurisdiction_fr_s=solr_search_jur,
                               owner_org_title_fr_s=solr_search_orgs,
                               keywords_fr_s=solr_search_keyw,
                               subject_fr_s=solr_search_subj,
                               resource_format_s=solr_search_fmts,
                               resource_type_fr_s=solr_search_rsct,
                               update_cycle_fr_s=solr_search_updc)
        else:
            facets_dict = dict(portal_type_en_s=solr_search_portal,
                               collection_type_en_s=solr_search_col,
                               jurisdiction_en_s=solr_search_jur,
                               owner_org_title_en_s=solr_search_orgs,
                               keywords_en_s=solr_search_keyw,
                               subject_en_s=solr_search_subj,
                               resource_format_s=solr_search_fmts,
                               resource_type_en_s=solr_search_rsct,
                               update_cycle_en_s=solr_search_updc)

        search_results = self.solr_query(solr_search_terms, facets=facets_dict, language=request.LANGUAGE_CODE,
                                         ids=solr_search_ids)
        self.cache_search_results_file(cached_filename, search_results)
        if settings.EXPORT_FILE_CACHE_URL == "":
            return FileResponse(open(cached_filename, 'rb'), as_attachment=True)
        else:
            return HttpResponseRedirect(settings.EXPORT_FILE_CACHE_URL + "{}.csv".format(hashed_query))
