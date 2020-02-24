"""ogc_search URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import path
from django.views.decorators.cache import cache_page
from ATI.views import ATISearchView, ATIExportView
from briefing_notes.views import BNSearchView, BNExportView, BNoteView
from contracts.views import CTSearchView, CTExportView, CTContractView
from experimental_inventory.views import EISearchView, EIExperimentView, EIExportView
from grants.views import GCSearchView, GCExportView, GCAmendmentView, GCRecordView
from national_action_plan.views import NAPSearchView, NAPExportView, NAPRecordView
from open_data import views
from open_data.views import ODSearchView, ODExportView, handle_404_error
from qp_notes.views import QPSearchView, QPExportView, QPCardView
from service_inventory.views import SISearchView, SIExportView

urlpatterns = [
    path('', views.default_search),
    ]
urlpatterns += i18n_patterns(
    path('od/', cache_page(300)(ODSearchView.as_view()), name='ODQuery'),
    path('od/export/', ODExportView.as_view(), name='ODExport'),
    path('404/', handle_404_error),
)

if settings.ATI_ENABLED:
    urlpatterns += i18n_patterns(
        path('ati/', ATISearchView.as_view(), name='ATIQuery'),
        path('ati/export/', ATIExportView.as_view(), name='ATIExport')
    )

if settings.BN_ENABLED:
    urlpatterns += i18n_patterns(
        path('bn/', BNSearchView.as_view(), name='BNQuery'),
        path('bn/note/<path:slug>', BNoteView.as_view(), name='BNote'),
        path('bn/export/', BNExportView.as_view(), name='BNExport')
    )

if settings.CT_ENABLED:
    urlpatterns += i18n_patterns(
        path('ct/', CTSearchView.as_view(), name='CTQuery'),
        path('ct/export/', CTExportView.as_view(), name='CTExport'),
        path('ct/id/<path:slug>', CTContractView.as_view(), name='CTContract')
    )

if settings.EI_ENABLED:
    urlpatterns += i18n_patterns(
        path('ei/', EISearchView.as_view(), name='EIQuery'),
        path('ei/export/', EIExportView.as_view(), name='EIExport'),
        path('ei/id/<path:slug>', EIExperimentView.as_view(), name="EIExperiment")
    )

if settings.GC_ENABLED:
    urlpatterns += i18n_patterns(
        path('gc/', GCSearchView.as_view(), name='GCQuery'),
        path('gc/export/', GCExportView.as_view(), name='GCExport'),
        path('gc/amend/<slug:slug>', GCAmendmentView.as_view(), name='GCAmendment'),
        path('gc/id/<path:slug>', GCRecordView.as_view(), name='GCRecord')
    )

if settings.NAP_ENABLED:
    urlpatterns += i18n_patterns(
        path('nap/', NAPSearchView.as_view(), name='NAPQuery'),
        path('nap/export/', NAPExportView.as_view(), name='NAPExport'),
        path('nap/id/<path:slug>', NAPRecordView.as_view(), name='NAPRecord')
    )

if settings.SI_ENABLED:
    urlpatterns += i18n_patterns(
        path('si/', SISearchView.as_view(), name='SIQuery'),
        path('si/export/', SIExportView.as_view(), name='SIExport')
    )

if settings.QP_ENABLED:
    urlpatterns += i18n_patterns(
        path('qp/', QPSearchView.as_view(), name='QPQuery'),
        path('qp/export/', QPExportView.as_view(), name='QPExport'),
        path('qp/id/<path:slug>', QPCardView.as_view(), name='QPCard')
    )

# Use a friendly rendered page for Page Not Found errors
handler404 = handle_404_error

if settings.ADMIN_ENABLED:
    urlpatterns += [
        path('admin/', admin.site.urls),
        ]

# Added for Debug toolbar ----
if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        url('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns



