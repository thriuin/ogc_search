
from django.conf import settings
from django.shortcuts import get_object_or_404, render, redirect, render_to_response
from django.utils import translation
from django.views.generic import View
from math import floor, ceil
from operator import itemgetter
import os
import pysolr
from .models import ATI, Department
from .ckansearchform import CkanSearchForm


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Create your views here.

def csrf_failure(request, reason=""):

    context = {
        'message': reason
    }
    return render_to_response("404.html", context=context)

def show_atis(request):
    """
    Show the ATI search result template
    :param request: HTTP Request object
    :return: ATI search page
    """
    ati = ATI.objects.all()
    context = {
        'atis': ati
    }
    return render(request, "ati_search.html", context)


def show_page(request):
    return render(request, 'content-en.html')


def show_search(request):
    if request.method == 'POST':
        # process the submitted form
        form = CkanSearchForm(request.POST)
        if form.is_valid():
            search_terms = form.cleaned_data['searchtext']
            return redirect('home-en')
    else:
        form = CkanSearchForm
    context = {
        'form': form
    }
    return render(request, 'search-en.html', context)


def _query_solr(q, startrow='0', pagesize='10', facets={}):
    solr = pysolr.Solr('http://127.0.0.1:8983/solr/core_ati_search')
    solr_facets = []
    solr_facet_fields = ['{!ex=tag_year_i}year_i', '{!ex=tag_month_i}month_i', '{!ex=tag_owner_org_title_en_s}owner_org_title_en_s',
                         '{!ex=tag_owner_org_title_fr_s}owner_org_title_fr_s']
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
        'hl.fl': ['search_year', 'search_month_en', 'search_month_fr', 'request_number_s', 'summary_txt_en',
                  'summary_txt_fr', 'search_disposition_en', 'search_disposition_fr',
                  'search_pages', 'owner_org_s', 'owner_org_title_en_s', 'owner_org_title_fr_s'],
        'hl.simple.pre': '<mark class=highlight>',
        'hl.simple.post': '</mark>',
        'hl.method': 'unified',
    }
    sr = solr.search(q, **extras)
    # If there are highlighted results, substitute the highlighted field in the doc results

    for doc in sr.docs:
        if doc['id'] in sr.highlighting:
            hl_entry = sr.highlighting[doc['id']]
            for hl_fld_id in hl_entry:
                if hl_fld_id in doc and len(hl_entry[hl_fld_id]) > 0:
                    doc[hl_fld_id] = hl_entry[hl_fld_id][0]
    return sr


def _query_solr_row(id_number):
    solr = pysolr.Solr('http://127.0.0.1:8983/solr/core_ati_search')
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


class DepartmentList(View):
    def get(self, request):
        depts = Department.objects.all()

        context = {
            'depts': depts,
        }

        return render(request, "departments.html", context)


class AtiSearchView(View):

    def get(self, request, lang=''):

        search_text = str(request.GET.get('search_text', ''))
        search_terms = search_text.split()
        solr_search_terms = "+".join(search_terms)
        solr_search_months = request.GET.get('search_month', '')
        solr_search_years = request.GET.get('search_year', '')
        solr_search_orgs = request.GET.get('search_org', '')
        # Only en and fr are accepted - anything results in en
        requested_lang = request.GET.get('lang', 'en')
        page_lang = requested_lang if requested_lang in ['en', 'fr'] else 'en'
        translation.activate(page_lang)
        context = dict(search_text=search_text,
                       months_selected_list=str(solr_search_months).split(','),
                       months_selected=solr_search_months,
                       years_selected_list=str(solr_search_years).split(','),
                       years_selected=solr_search_years,
                       organizations_selected_list=str(solr_search_orgs).split(','),
                       organizations_selected=solr_search_orgs)

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

        # Search Solr and return results and facets

        if request.LANGUAGE_CODE == 'fr':
            facets_dict = dict(month_i=solr_search_months, year_i=context['years_selected'],
                 owner_org_title_fr_s=context['organizations_selected'])
            query_terms = ('_text_fr_:{}'.format(solr_search_terms) if solr_search_terms != '' else '*')
        else:
            facets_dict = dict(month_i=solr_search_months, year_i=context['years_selected'],
                 owner_org_title_en_s=context['organizations_selected'])
            query_terms = ('_text_en_:{}'.format(solr_search_terms) if solr_search_terms != '' else '*')

        search_results = _query_solr(query_terms, startrow=str(start_row), pagesize='10', facets=facets_dict)

        context['organization_facets'] = _convert_facet_list_to_dict(
            search_results.facets['facet_fields']['owner_org_title_en_s'])
        context['organization_facets_fr'] = _convert_facet_list_to_dict(
            search_results.facets['facet_fields']['owner_org_title_fr_s'])
        context['year_facets'] = _convert_facet_list_to_dict(
            search_results.facets['facet_fields']['year_i'], reverse=True)
        context['month_facets'] = _convert_facet_list_to_dict(
            search_results.facets['facet_fields']['month_i'])
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

        return render(request, "ati_search.html", context)


class AtiSearchDetail(View):

    def get(self, request, lang=''):
        solr_id = str(request.GET.get('idno', '0'))
        context = dict(solr_id=solr_id)
        solr_row = _query_solr_row(solr_id)
        if len(solr_row.docs) > 0:
            context['year'] = solr_row.docs[0].get('year_i', '-')
            context['month_en'] = solr_row.docs[0].get('search_month_en', '-')
            context['month_fr'] = solr_row.docs[0].get('search_month_fr', '-')
            context['disposition_en'] = solr_row.docs[0].get('disposition_en_s', '-')
            context['disposition_fr'] = solr_row.docs[0].get('disposition_fr_s', '-')
            context['request_number'] = solr_row.docs[0].get('request_number_s', '-')
            context['summary_en'] = solr_row.docs[0].get('summary_txt_en', '-')
            context['summary_fr'] = solr_row.docs[0].get('summary_txt_fr', '-')
            context['owner_org_en'] = solr_row.docs[0].get('owner_org_title_en_s', '-')
            context['owner_org_fr'] = solr_row.docs[0].get('owner_org_title_fr_s', '-')
            context['pages'] = solr_row.docs[0].get('pages_i', '-')

        return render(request, "ati_detail.html", context)
