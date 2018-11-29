from django.shortcuts import render
from django.conf import settings
from django.shortcuts import get_object_or_404, render, redirect, render_to_response
from django.utils import translation
from django.views.generic import View
import logging
from math import floor, ceil
from operator import itemgetter
import os
import pysolr

logger = logging.getLogger(__name__)

def _query_solr(q, startrow='0', pagesize='10', facets={}, language='en', search_text='', sort_order='score asc'):
    solr = pysolr.Solr('http://127.0.0.1:8983/solr/core_od_search')
    solr_facets = []
    if language == 'fr':
        solr_facet_fields = ['{!ex=tag_portal_type_fr_s}portal_type_fr_s',
                             '{!ex=tag_collection_type_fr_s}collection_type_fr_s',
                             '{!ex=tag_jurisdiction_fr_s}jurisdiction_fr_s',
                             '{!ex=tag_owner_org_title_fr_s}owner_org_title_fr_s',
                             '{!ex=tag_keywords_fr_s}keywords_fr_s',
                             '{!ex=tag_subject_fr_s}subject_fr_s',
                             '{!ex=tag_resource_format_s}resource_format_s',
                             '{!ex=tag_resource_type_fr_s}resource_type_fr_s',
                             '{!ex=tag_update_cycle_fr_s}update_cycle_fr_s']
    else:
        solr_facet_fields = ['{!ex=tag_portal_type_en_s}portal_type_en_s',
                             '{!ex=tag_collection_type_en_s}collection_type_en_s',
                             '{!ex=tag_jurisdiction_en_s}jurisdiction_en_s',
                             '{!ex=tag_owner_org_title_en_s}owner_org_title_en_s',
                             '{!ex=tag_keywords_en_s}keywords_en_s',
                             '{!ex=tag_subject_en_s}subject_en_s',
                             '{!ex=tag_resource_format_s}resource_format_s',
                             '{!ex=tag_resource_type_en_s}resource_type_en_s',
                             '{!ex=tag_update_cycle_en_s}update_cycle_en_s']
    for facet in facets.keys():
        if facets[facet] != '':
            facet_terms = facets[facet].split(',')
            quoted_terms = ['"{0}"'.format(item) for item in facet_terms]
            facet_text = '{{!tag=tag_{0}}}{0}:({1})'.format(facet, ' OR '.join(quoted_terms))
            solr_facets.append(facet_text)
    extras = {
        'start': startrow,
        'rows': pagesize,
        'facet': 'on',
        'facet.sort': 'index',
        'facet.field': solr_facet_fields,
        'fq': solr_facets,
        'hl': 'on',
        'hl.simple.pre': '<mark class="highlight">',
        'hl.simple.post': '</mark>',
        'hl.method': 'unified',
        'sort': sort_order
    }
    if language == 'fr':
        extras['hl.fl'] = ['description_txt_fr', 'title_txt_fr', 'owner_org_title_txt_fr', 'keywords_txt_fr']
        extras['f.keywords_fr_s.facet.limit'] = 250
        extras['f.keywords_fr_s.facet.sort'] = 'count'
    else:
        extras['hl.fl'] = ['description_txt_en', 'title_txt_en', 'owner_org_title_txt_en', 'keywords_txt_en']
        extras['f.keywords_en_s.facet.limit'] = 250
        extras['f.keywords_en_s.facet.sort'] = 'count'
    extras['hl.preserveMulti'] = 'true'

    sr = solr.search(q, **extras)
    print('Solr Query: Terms {0}, Extras {1}'.format(q, extras))

    # If there are highlighted results, substitute the highlighted field in the doc results

    for doc in sr.docs:
        if doc['id'] in sr.highlighting:
            hl_entry = sr.highlighting[doc['id']]
            for hl_fld_id in hl_entry:
                if hl_fld_id in doc and len(hl_entry[hl_fld_id]) > 0:
                    if type(doc[hl_fld_id]) is list:
                        # Multi-valued Solr field
                        for y in hl_entry[hl_fld_id]:
                            w = y[24:]
                            z = w[:-7]
                            x = 0
                            for zz in doc[hl_fld_id]:
                                if zz == z:
                                    doc[hl_fld_id][x] = y
                                x += 1
                    else:
                        # Straight forward string replacement
                        doc[hl_fld_id] = hl_entry[hl_fld_id][0]
    return sr


def _query_solr_row(id_number):
    solr = pysolr.Solr('http://127.0.0.1:8983/solr/ckan_od_search')
    q = 'id:{}'.format(id_number)
    return solr.search(q)

def _convert_facet_list_to_dict(facet_list: dict, reverse=False) -> dict:
    '''
    Solr returns search facet results in the form of an alternating list. Convert the list into a dictionary key
    on the facet
    :param facet_list: facet list returned by Solr
    :param reverse: boolean flag indicating if the search results should be returned in reverse order
    :return: A dictonary of the facet values and counts
    '''
    facet_dict = {}
    for i in range(0, len(facet_list)):
        if i % 2 == 0:
            facet_dict[facet_list[i]] = facet_list[i + 1]
    if reverse:
        rkeys= sorted(facet_dict,  reverse=True)
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


# Create your views here.
def od_search(request):
    return render(request, 'search-en.html')

class ODSearchView(View):

    def get(self, request):

        search_text = str(request.GET.get('search_text', ''))
        search_terms = search_text.split()
        solr_search_terms = "+".join(search_terms)
        solr_search_portal = request.GET.get('search_portal', '')
        solr_search_col = request.GET.get('search_collection', '')
        solr_search_jur = request.GET.get('search_jur', '')
        solr_search_orgs = request.GET.get('search_orgs', '')
        solr_search_keyw = request.GET.get('search_keywords', '')
        solr_search_subj = request.GET.get('search_subject', '')
        solr_search_fmts = request.GET.get('search_format', '')
        solr_search_rsct = request.GET.get('search_rsct', '')
        solr_search_updc = request.GET.get('search_update', '')
        # Only en and fr are accepted - anything results in en
        #requested_lang = translation.get_language()
        #page_lang = requested_lang if requested_lang in ['en', 'fr'] else 'en'

        #translation.activate(page_lang)

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

        # Set Sort order
        solr_search_sort = request.GET.get('sort', 'score')
        if not solr_search_sort in ['score asc', 'last_modified_tdt desc', 'title_en_s asc']:
            solr_search_sort = 'score asc'
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
            query_terms = ('_text_fr_:{}'.format(solr_search_terms) if solr_search_terms != '' else '*')
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
            query_terms = ('_text_en_:{}'.format(solr_search_terms) if solr_search_terms != '' else '*')

        search_results = _query_solr(query_terms, startrow=str(start_row), pagesize='10', facets=facets_dict,
                                     language=request.LANGUAGE_CODE , search_text=search_text,
                                     sort_order=solr_search_sort)

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

        i = 0
        #for hl in search_results.highlighting:years_selected
        #    search_results.docs[i]['hl'] = search_results.highlighting[hl]
        #    i += 1

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

        context["od_en_url"] = settings.OPEN_DATA_EN_URL_BASE
        context["od_fr_url"] = settings.OPEN_DATA_FR_URL_BASE

        return render(request, "od_search.html", context)
