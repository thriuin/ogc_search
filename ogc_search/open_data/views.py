from django.conf import settings
from django.http import HttpRequest, HttpResponseRedirect, FileResponse
from django.shortcuts import render, redirect
from django.utils.translation import gettext as _
from django.views.generic import View
import logging
import hashlib
import os
import re
import search_util
import time
from urllib import parse

logger = logging.getLogger('ogc_search')


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


def default_search(request):
    return redirect('/od')


def handle_404_error(request, exception=None):
    context = dict(LANGUAGE_CODE=request.LANGUAGE_CODE,)
    context["cdts_version"] = settings.CDTS_VERSION
    context["adobe_analytics_url"] = settings.ADOBE_ANALYTICS_URL
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
                               "desc_summary_txt_fr,resource_title_fr_s,resource_title_txt_fr,"
                               "keywords_fr_s,keywords_txt_fr,keywords_xlt_txt_fr,id,_version_,last_modified_tdt,"
                               "published_tdt,resource_format_s,id_name_s,display_options_s")

        self.solr_facet_fields_fr = ['{!ex=tag_portal_type_fr_s}portal_type_fr_s',
                                     '{!ex=tag_collection_type_fr_s}collection_type_fr_s',
                                     '{!ex=tag_jurisdiction_fr_s}jurisdiction_fr_s',
                                     '{!ex=tag_owner_org_title_fr_s}owner_org_title_fr_s',
                                     '{!ex=tag_keywords_fr_s}keywords_fr_s',
                                     '{!ex=tag_subject_fr_s}subject_fr_s',
                                     '{!ex=tag_resource_format_s}resource_format_s',
                                     '{!ex=tag_resource_type_fr_s}resource_type_fr_s',
                                     '{!ex=tag_update_cycle_fr_s}update_cycle_fr_s']
        self.solr_hl_fields_fr = ['description_txt_fr', 'title_txt_fr', 'owner_org_title_txt_fr', 'keywords_txt_fr',
                                  'desc_summary_txt_fr']
        self.solr_query_fields_fr = ['owner_org_title_txt_fr^2', 'description_txt_fr^3', 'description_xlt_txt_fr^3',
                                     'keywords_txt_fr^4', 'keywords_xlt_txt_fr^4',
                                     'title_txt_fr^5', 'title_xlt_fr_s^3',
                                     'author_txt^2', 'resource_title_txt_fr^3', '_text_fr_^0.5',
                                     'id_s^5',
                                     'data_series_issue_identification_fr']
        self.solr_phrase_fields_fr = ['description_txt_fr~3^10', 'title_txt_fr~3^10']
        self.solr_bigram_fields_fr = ['description_txt_fr', 'title_txt_fr', 'keywords_txt_fr']
        self.solr_facet_limits_fr = {'f.keywords_fr_s.facet.limit': 250,
                                     'f.keywords_fr_s.facet.sort': 'count'}

        # English search fields
        self.solr_fields_en = ("portal_type_en_s,collection_type_en_s,jurisdiction_en_s,owner_org_title_en_s,"
                               "owner_org_title_txt_en,subject_en_s,resource_type_en_s,update_cycle_en_s,"
                               "description_txt_en,description_xlt_txt_en,title_en_s,title_txt_en,title_xlt_en_s,"
                               "desc_summary_txt_en,resource_title_en_s,resource_title_txt_en,"
                               "keywords_en_s,keywords_txt_en,keywords_xlt_txt_en,id,_version_,last_modified_tdt,"
                               "published_tdt,resource_format_s,id_name_s,display_options_s")
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
        self.solr_hl_fields_en = ['description_txt_en', 'title_txt_en', 'owner_org_title_txt_en', 'keywords_txt_en',
                                  'desc_summary_txt_en']
        self.solr_query_fields_en = ['owner_org_title_txt_en^2', 'description_txt_en^3', 'description_xlt_txt_en^3',
                                     'keywords_txt_en^4', 'keywords_xlt_txt_en^4',
                                     'title_txt_en^5', 'title_xlt_en_s^3',
                                     'author_txt^2', 'resource_title_txt_en^3', '_text_en_^0.5',
                                     'id_s^5', 'data_series_issue_identification_en']
        self.solr_phrase_fields_en = ['description_txt_en~3^10', 'title_txt_en~3^10']
        self.solr_bigram_fields_en = ['description_txt_en', 'title_txt_en', 'keywords_txt_en']
        self.solr_trigram_fields_en = ['description_txt_en', 'title_txt_en']
        self.solr_facet_limits_en = {'f.keywords_en_s.facet.limit': 250,
                                     'f.keywords_en_s.facet.sort': 'count'}
        self.mlt_fields_en = "author_txt,description_txt_en,description_xlt_txt_en," \
                             "data_series_issue_identification_en,title_txt_en,keywords_txt_en,keywords_xlt_txt_en," \
                             "resource_title_txt_en,desc_summary_txt_en"
        self.mlt_fields_fr = "author_txt,description_txt_fr,description_xlt_txt_fr," \
                             "data_series_issue_identification_fr,title_txt_fr,keywords_txt_fr,keywords_xlt_txt_fr," \
                             "resource_title_txt_fr,desc_summary_txt_fr"

        self.phrase_xtras_en = {
            'hl': 'on',
            'hl.simple.pre': '<mark>',
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
            'pf3': self.solr_bigram_fields_en,
        }
        self.phrase_xtras_fr = {
            'hl': 'on',
            'hl.simple.pre': '<mark>',
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

        mlt_search_id = request.GET.get("mlt_id", '')

        if solr_search_ids == '' and mlt_search_id == '':
            # Handle search text
            search_text = str(request.GET.get('search_text', ''))

            # Get any search terms
            solr_search_terms = search_util.get_search_terms(request)

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
                       portal_selected_list=str(solr_search_portal).split('|'),
                       portal_selected=solr_search_portal,
                       col_selected_list=str(solr_search_col).split('|'),
                       col_selected=solr_search_col,
                       jur_selected_list=str(solr_search_jur).split('|'),
                       jur_selected=solr_search_jur,
                       organizations_selected_list=str(solr_search_orgs).split('|'),
                       organizations_selected=solr_search_orgs,
                       keyw_selected_list=str(solr_search_keyw).split('|'),
                       keyw_selected=solr_search_keyw,
                       subject_selected_list=str(solr_search_subj).split('|'),
                       subject_selected=solr_search_subj,
                       format_selected_list=str(solr_search_fmts).split('|'),
                       format_selected=solr_search_fmts,
                       rsct_selected_list=str(solr_search_rsct).split('|'),
                       rsct_selected=solr_search_rsct,
                       update_selected_list=str(solr_search_updc).split('|'),
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
        if 'Open Maps'in context['col_selected_list']:
            alerts.append(_(settings.OPEN_MAPS_INFO_EN))
        elif 'Cartes Ouvertes' in context['col_selected_list']:
            alerts.append(_(settings.OPEN_MAPS_INFO_FR))
        if 'Open Information' in context['portal_selected_list']:
            alerts.append(_(settings.OPEN_INFORMATION_INFO_EN))
        elif 'Information ouverte' in context['portal_selected_list']:
            alerts.append(_(settings.OPEN_INFORMATION_INFO_FR))
        if 'User' in context['jur_selected_list']:
            alerts.append(_(settings.OPEN_DATA_EXTERNAL_INFO_EN))
        elif 'Utilisateur' in context['jur_selected_list']:
            alerts.append(_(settings.OPEN_DATA_EXTERNAL_INFO_FR))
        context['alerts'] = alerts

        # Set Sort order

        solr_search_sort = request.GET.get('sort', 'score desc')
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
        if mlt_search_id == '':
            if request.LANGUAGE_CODE == 'fr':
                search_results = search_util.solr_query(solr_search_terms, settings.SOLR_URL, self.solr_fields_fr,
                                                        self.solr_query_fields_fr, self.solr_facet_fields_fr,
                                                        self.phrase_xtras_fr, start_row=str(start_row),
                                                        pagesize=str(settings.OPEN_DATA_ITEMS_PER_PAGE),
                                                        facets=facets_dict, sort_order=solr_search_sort,
                                                        uuid_list=solr_search_ids, facet_limit=self.solr_facet_limits_fr
                                                        )
            else:
                search_results = search_util.solr_query(solr_search_terms, settings.SOLR_URL, self.solr_fields_en,
                                                        self.solr_query_fields_en, self.solr_facet_fields_en,
                                                        self.phrase_xtras_en, start_row=str(start_row),
                                                        pagesize=str(settings.OPEN_DATA_ITEMS_PER_PAGE),
                                                        facets=facets_dict, sort_order=solr_search_sort,
                                                        uuid_list=solr_search_ids, facet_limit=self.solr_facet_limits_en
                                                        )
            context['mlt_message'] = ''
        else:
            if request.LANGUAGE_CODE == 'fr':
                search_results = search_util.solr_mlt(mlt_search_id, settings.SOLR_URL, self.solr_fields_fr,
                                                      self.solr_facet_fields_fr, self.mlt_fields_fr,
                                                      start_row='0', pagesize='10')
                context['mlt_message'] = " similaries à <strong>{0}</strong>".format(search_results.docs[0]['title_fr_s'])
            else:
                search_results = search_util.solr_mlt(mlt_search_id, settings.SOLR_URL, self.solr_fields_en,
                                                      self.solr_facet_fields_en, self.mlt_fields_en,
                                                      start_row='0', pagesize='10')
                context['mlt_message'] = " similar to <strong>{0}</strong>".format(search_results.docs[0]['title_en_s'])
            search_results.docs = search_results.raw_response['moreLikeThis'][mlt_search_id]['docs']

        context['export_url'] = "/{0}/od/export/?{1}".format(request.LANGUAGE_CODE, request.GET.urlencode())


        if request.LANGUAGE_CODE == 'fr':
            context['portal_facets'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['portal_type_fr_s'])
            context['collection_facets'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['collection_type_fr_s'])
            context['jurisdiction_facets'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['jurisdiction_fr_s'])
            context['org_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_title_fr_s'])
            context['org_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_title_fr_s'])
            context['keyword_facets'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['keywords_fr_s'])
            context['subject_facets'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['subject_fr_s'])
            context['format_facets'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['resource_format_s'])
            context['type_facets'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['resource_type_fr_s'])
            context['frequency_facets'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['update_cycle_fr_s'])
        else:
            context['portal_facets'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['portal_type_en_s'])
            context['collection_facets'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['collection_type_en_s'])
            context['jurisdiction_facets'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['jurisdiction_en_s'])
            context['org_facets_en'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_title_en_s'])
            context['org_facets_fr'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['owner_org_title_en_s'])
            context['keyword_facets'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['keywords_en_s'])
            context['subject_facets'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['subject_en_s'])
            context['format_facets'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['resource_format_s'])
            context['type_facets'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['resource_type_en_s'])
            context['frequency_facets'] = search_util.convert_facet_list_to_dict(
                search_results.facets['facet_fields']['update_cycle_en_s'])

        context['results'] = search_results

        # Set up previous and next page numbers

        pagination = search_util.calc_pagination_range(context['results'], 10, page)
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
        # Allow for, but do not require, a custom alert message
        if hasattr(settings, 'OPEN_DATA_PORTAL_ALERT_BASE'):
            context['od_portal_alert_base'] = settings.OPEN_DATA_PORTAL_ALERT_BASE
        else:
            context['od_portal_alert_base'] = "/data/static/_site_messaging/header_od_ckan."

            # Adobe Analytics URL
        context["adobe_analytics_url"] = settings.ADOBE_ANALYTICS_URL

        return render(request, "od_search.html", context)


class ODExportView(ODSearchView):
    """
    A view for downloading a simple CSV containing a subset of the fields from the Search View.
    """

    def __init__(self):
        super().__init__()
        self.solr_fields = ['id_s, owner_org_title_en_s, owner_org_title_fr_s, title_en_s, title_fr_s, description_en_s, description_fr_s, ogp_link_en_s, ogp_link_fr_s']
        self.solr_query_fields_en = ['owner_org_title_txt_en^2', 'description_txt_en', 'keywords_txt_en^2',
                                     'title_txt_en^3', 'author_txt', 'resource_title_txt_en^2']
        self.solr_query_fields_fr = ['owner_org_title_txt_fr^2', 'description_txt_fr^3', 'keywords_txt_fr^4',
                                     'title_txt_fr^5', 'author_txt^2', 'resource_title_txt_fr^3', '_text_fr_^0.5']
        self.cache_dir = settings.EXPORT_FILE_CACHE_DIR
        if not os.path.exists(self.cache_dir):
            os.mkdir(self.cache_dir)
        self.uuid_regex = _create_pattern('[1-5]')

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
        mlt_search_id = request.GET.get("mlt_id", '')

        if solr_search_ids == '' and mlt_search_id == '':

            # Handle search text

            search_text = str(request.GET.get('search_text', ''))

            # Respect quoted strings
            search_terms = search_util.split_with_quotes(search_text)
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

        if mlt_search_id == "":
            search_results = search_util.solr_query_for_export(solr_search_terms, settings.SOLR_URL, self.solr_fields,
                                                               self.solr_query_fields_en, self.solr_facet_fields_en,
                                                               "id asc", facets_dict, self.phrase_xtras_en, solr_search_ids)
        else:
            if request.LANGUAGE_CODE == 'fr':
                search_results = search_util.solr_query_for_export_mlt(mlt_search_id,settings.SOLR_URL,
                                                                       self.solr_fields, self.mlt_fields_fr,
                                                                       self.solr_query_fields_fr, 'title_fr_s asc',
                                                                       10)
            else:
                search_results = search_util.solr_query_for_export_mlt(mlt_search_id,settings.SOLR_URL,
                                                                       self.solr_fields, self.mlt_fields_en,
                                                                       self.solr_query_fields_en, 'title_en_s asc',
                                                                       10)

        if search_util.cache_search_results_file(cached_filename=cached_filename, sr=search_results):
            if settings.EXPORT_FILE_CACHE_URL == "":
                return FileResponse(open(cached_filename, 'rb'), as_attachment=True)
            else:
                return HttpResponseRedirect(settings.EXPORT_FILE_CACHE_URL + "{}.csv".format(hashed_query))


class ODMltView(ODSearchView):
    """
    A View for return an  HTML fragment with a list of  ten items from a More Like This query to  an Open Data
    record.
    """

    def __init__(self):
        super().__init__()

    def get(self, request, slug=''):

        mlt_search_id = slug

        context = {
            'od_base_en': settings.OPEN_DATA_EN_URL_BASE,
            'od_base_fr': settings.OPEN_DATA_FR_URL_BASE,
        }
        if request.LANGUAGE_CODE == 'fr':
            search_results = search_util.solr_mlt(mlt_search_id, settings.SOLR_URL, self.solr_fields_fr,
                                                  self.solr_facet_fields_fr, self.mlt_fields_fr,
                                                  start_row='0', pagesize='10')
        else:
            search_results = search_util.solr_mlt(mlt_search_id, settings.SOLR_URL, self.solr_fields_en,
                                                  self.solr_facet_fields_en, self.mlt_fields_en,
                                                  start_row='0', pagesize='10')
        search_results.docs = search_results.raw_response['moreLikeThis'][mlt_search_id]['docs']
        context['results'] = search_results
        return render(request, "mlt_list.html", context)
