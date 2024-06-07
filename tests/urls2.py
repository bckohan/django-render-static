from django.urls import path, re_path
from django.urls.converters import register_converter

from .views import TestView


class CustomConverter:
    regex = "[6]{3}"

    def to_python(self, value):
        return int(value)

    def to_url(self, value):
        return str(value)


register_converter(CustomConverter, "ctm")


urlpatterns = [
    re_path(r"^default/(?P<def>\w+)$", TestView.as_view(), name="default"),
    re_path(r"^default2/([\w]+)$", TestView.as_view(), name="default"),
    re_path(r"^special2/((?:first)|(?:third))$", TestView.as_view(), name="special"),
    path(
        "<ctm:one>/<ctm:two>/<ctm:three>/<ctm:four>/<ctm:five>/<ctm:six>/<ctm:seven>/<ctm:eight>",
        TestView.as_view(),
        name="complex",
    ),
    re_path(
        r"^special1/(?P<choice>(:?first)|(:?second))$",
        TestView.as_view(),
        name="special",
    ),
    re_path(
        r"^special1/(?P<choice>(:?first)|(:?second))/(?P<choice1>(:?first)|(:?second))$",
        TestView.as_view(),
        name="special",
    ),
    # non capturing groups - this is actually reversible with one argument
    re_path(r"^special1/(\d{4})/(?:test{2,5})$", TestView.as_view(), name="no_capture"),
    # this should not be reversible - mix of named and unnamed
    re_path(
        r"^invalid/(?P<named>(\d{4}))/(unnamed{1,5})$",
        TestView.as_view(),
        name="bad_mix",
    ),
    # this should error
    re_path(
        r"^invalid/(?P<named>(\d{4}))/(?:(?:one)|(?:two))/(unnamed{1,5})$",
        TestView.as_view(),
        name="bad_mix2",
    ),
]
