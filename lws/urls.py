"""
URLs: the Django admin is the application; /api/v1/ is for other systems and apps. The old screens' addresses
(/, /tickets/<id>/, /login/) redirect to their admin equivalents so that
bookmarks and links in old emails keep working.
"""
from django.contrib import admin
from django.db import connection
from django.http import HttpResponse
from django.urls import include, path, re_path
from django.views.generic import RedirectView

from lwf.api import api
from lwf.api_demo import api_demo
from lwf.documents import protected_media


def healthz(request):
    """Load balancer check: the app answers and reaches the database."""
    connection.ensure_connection()
    return HttpResponse('ok', content_type='text/plain')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', api.urls),
    path('api-demo/', api_demo, name='api_demo'),
    path('i18n/', include('django.conf.urls.i18n')),
    path('healthz', healthz),
    path('media/<path:name>', protected_media, name='media'),
    path('', RedirectView.as_view(pattern_name='admin:index'), name='home'),
    path('login/', RedirectView.as_view(pattern_name='admin:login', query_string=True)),
    re_path(r'^tickets/(?P<object_id>\d+)/', RedirectView.as_view(pattern_name='admin:lwf_ticket_change')),
    re_path(r'^(?:dashboard|tickets)/', RedirectView.as_view(pattern_name='admin:index')),
]
