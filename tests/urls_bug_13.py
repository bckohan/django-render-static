"""
Reproduce: https://github.com/bckohan/django-render-static/issues/65
"""

from django.urls import include, path, re_path

urlpatterns = [
    path("spa1/<int:toparg>/", include("tests.spa.urls", namespace="spa1")),
    path("spa2/", include("tests.spa.urls", namespace="spa2")),
    path("multi/<slug:top>/", include("tests.chain.urls")),
    re_path(
        r"^multi/(?P<top>\w+)/",
        include("tests.chain.urls", namespace="chain_re"),
    ),
    path(
        "noslash/<slug:top>",
        include("tests.chain.urls", namespace="noslash"),
    ),
]
