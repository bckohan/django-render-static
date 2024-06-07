"""
Reproduce: https://github.com/bckohan/django-render-static/issues/65
"""

from django.urls import path, re_path

from .views import TestView

urlpatterns = [
    path(
        "prefix/<int:url_param>/postfix",
        TestView.as_view(),
        kwargs={"kwarg_param": "1"},
        name="bug65",
    ),
    path(
        "prefix/<int:url_param>/postfix/value1",
        TestView.as_view(),
        kwargs={"kwarg_param": "1"},
        name="bug65",
    ),
    path(
        "prefix/<int:url_param>/postfix/value2",
        TestView.as_view(),
        kwargs={"kwarg_param": "2"},
        name="bug65",
    ),
    path(
        "prefix/<int:url_param>/postfix/value1",
        TestView.as_view(),
        kwargs={"kwarg_param": "a"},
        name="bug65",
    ),
    path("prefix", TestView.as_view(), kwargs={"kwarg_param": "2"}, name="bug65"),
    path("prefix2", TestView.as_view(), kwargs={"kwarg_param": 4}, name="bug65"),
    path(
        "prefix_int/<int:url_param>/postfix_int/<int:kwarg_param>",
        TestView.as_view(),
        kwargs={"kwarg_param": 1},
        name="bug65",
    ),
    re_path(
        r"^re_path/(?P<url_param>\d+)/$",
        TestView.as_view(),
        kwargs={"kwarg_param": 4},
        name="bug65",
    ),
    re_path(r"^re_path/unamed/(\d+)$", TestView.as_view(), name="bug65"),
]
