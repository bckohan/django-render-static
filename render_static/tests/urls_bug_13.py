"""
Reproduce: https://github.com/bckohan/django-render-static/issues/65
"""
from django.urls import include, path, re_path

urlpatterns = [
    path(
        'spa1/<int:toparg>/',
        include('render_static.tests.spa.urls', namespace='spa1')
    ),
    path('spa2/', include('render_static.tests.spa.urls', namespace='spa2')),
    path('multi/<slug:top>/', include('render_static.tests.chain.urls')),
    re_path(
        r'^multi/(?P<top>\w+)/',  # todo adding $ at the end breaks this badly
        include('render_static.tests.chain.urls', namespace='chain_re')
    ),
    path(
        'noslash/<slug:top>',
        include('render_static.tests.chain.urls', namespace='noslash')
    ),
]
