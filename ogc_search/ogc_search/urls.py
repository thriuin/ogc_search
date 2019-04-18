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
from ATI.views import ATISearchView
from briefing_notes.views import BNSearchView, BNExportView
from open_data import views
from open_data.views import ODSearchView, ODExportView, handle_404_error

urlpatterns = [
    path('', views.default_search),
    ]
urlpatterns += i18n_patterns(
    path('od/', cache_page(300)(ODSearchView.as_view()), name='ODQuery'),
    path('od/export/', ODExportView.as_view(), name='ODExport'),
    path('404/', handle_404_error),
)

if settings.BN_ENABLED:
    urlpatterns += i18n_patterns(
        path('bn/', BNSearchView.as_view(), name='ATIQuery'),
        path('bn/export/', BNExportView.as_view(), name='BNExport')
    )

if settings.ATI_ENABLED:
    urlpatterns += i18n_patterns(
        path('ati/', ATISearchView.as_view(), name='ATIQuery'),
        path('ati/export/', BNExportView.as_view(), name='BNExport')
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



