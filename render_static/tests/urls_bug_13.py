"""
Reproduce: https://github.com/bckohan/django-render-static/issues/65
"""
from django.urls import include, path

urlpatterns = [
    path(
        'spa1/<int:toparg>/',
        include('render_static.tests.spa.urls', namespace='spa1')
    ),
    path('spa2/', include('render_static.tests.spa.urls', namespace='spa2')),
    path('multi/<slug:top>/', include('render_static.tests.chain.urls')),
    path(
        'noslash/<slug:top>',
        include('render_static.tests.chain.urls', namespace='noslash')
    ),
]
