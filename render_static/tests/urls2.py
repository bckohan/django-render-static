from django.urls import re_path, path
from django.urls.converters import register_converter
from .views import TestView


class CustomConverter:
    regex = '[6]{3}'

    def to_python(self, value):
        return int(value)

    def to_url(self, value):
        return str(value)


register_converter(CustomConverter, 'ctm')


urlpatterns = [
    re_path(r'^default/(?P<def>\w+)$', TestView.as_view(), name='default'),
    re_path(r'^default2/([\w]+)$', TestView.as_view(), name='default'),
    re_path(r'^special2/((?:first)|(?:second))$', TestView.as_view(), name='special'),
    path(
        '<ctm:one>/<ctm:two>/<ctm:three>/<ctm:four>/<ctm:five>/<ctm:six>/<ctm:seven>/<ctm:eight>',
        TestView.as_view(),
        name='complex'
    ),
    re_path(r'^special1/(?P<choice>(:?first)|(:?second))$', TestView.as_view(), name='special'),
    re_path(r'^special1/(?P<choice>(:?first)|(:?second))/(?P<choice1>(:?first)|(:?second))$',
            TestView.as_view(), name='special'),
]
