from django.contrib.sitemaps import Sitemap
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.utils.timezone import now

from tests.views import TestView


class BlogSitemap(Sitemap):
    changefreq = "never"
    priority = 0.5


class Default:
    pass


urlpatterns = [
    path(
        "sitemap.xml",
        sitemap,
        {
            "sitemaps": {
                "blog": BlogSitemap(),
            }
        },
        name="sitemap",
    ),
    path(
        "complex_default/<str:def>",
        TestView.as_view(),
        {"complex_default": {"blog": Default}},
        name="default",
    ),
    path("default/<str:def>", TestView.as_view(), name="default"),
]
