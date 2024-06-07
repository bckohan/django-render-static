"""
ADDITIONAL URL TESTS FROM DJANGO-JS-REVERSE

https://github.com/ierror/django-js-reverse/blob/master/django_js_reverse/tests/test_re_paths.py
"""

"""
Copyright (c) 2013-2015 Bernhard Janetzki and individual contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

# -*- coding: utf-8 -*-
from copy import copy

from django.conf.urls import include as django_include
from django.urls import path, re_path

from .views import TestView

basic_patterns = [
    re_path(r"^test_no_url_args/$", TestView.as_view(), name="test_no_url_args"),
    re_path(
        r"^test_script/$",
        TestView.as_view(),
        name="</script><script>console.log(&amp;)</script><!--",
    ),
    re_path(
        r"^test_one_url_args/(?P<arg_one>[-\w]+)/$",
        TestView.as_view(),
        name="test_one_url_args",
    ),
    re_path(
        r"^test_two_url_args/(?P<arg_one>[-\w]+)-(?P<arg_two>[-\w]+)/$",
        TestView.as_view(),
        name="test_two_url_args",
    ),
    re_path(
        r"^test_optional_url_arg/(?:1_(?P<arg_one>[-\w]+)-)?2_(?P<arg_two>[-\w]+)/$",
        TestView.as_view(),
        name="test_optional_url_arg",
    ),
    re_path(
        r"^test_unicode_url_name/$", TestView.as_view(), name="test_unicode_url_name"
    ),
    re_path(
        r"^test_duplicate_name/(?P<arg_one>[-\w]+)/$",
        TestView.as_view(),
        name="test_duplicate_name",
    ),
    re_path(
        r"^test_duplicate_name/(?P<arg_one>[-\w]+)-(?P<arg_two>[-\w]+)/$",
        TestView.as_view(),
        name="test_duplicate_name",
    ),
    re_path(
        r"^test_duplicate_argcount/(?P<arg_one>[-\w]+)?-(?P<arg_two>[-\w]+)?/$",
        TestView.as_view(),
        name="test_duplicate_argcount",
    ),
    path(
        "test_django_gte_2_path_syntax/<int:arg_one>/<str:arg_two>/",
        TestView.as_view(),
        name="test_django_gte_2_path_syntax",
    ),
]

urlpatterns = copy(basic_patterns)

# test exclude namespaces urls
urlexclude = [
    re_path(
        r"^test_exclude_namespace/$",
        TestView.as_view(),
        name="test_exclude_namespace_url1",
    )
]


def include(v, **kwargs):
    return django_include((v, "django_js_reverse"), **kwargs)


# test namespace
pattern_ns_1 = [re_path(r"", django_include(basic_patterns))]

pattern_ns_2 = [re_path(r"", django_include(basic_patterns))]

pattern_ns = [re_path(r"", django_include(basic_patterns))]

pattern_nested_ns = [re_path(r"^ns1/", include(pattern_ns_1, namespace="ns1"))]

pattern_dubble_nested2_ns = [re_path(r"^ns1/", include(pattern_ns_1, namespace="ns1"))]

pattern_dubble_nested_ns = [
    re_path(r"^ns1/", include(pattern_ns_1, namespace="ns1")),
    re_path(r"^nsdn2/", include(pattern_dubble_nested2_ns, namespace="nsdn2")),
]

pattern_only_nested_ns = [
    re_path(r"^ns1/", django_include(pattern_ns_1)),
    re_path(r"^nsdn0/", include(pattern_dubble_nested2_ns, namespace="nsdn0")),
]

urlpatterns += [
    re_path(r"^ns1/", include(pattern_ns_1, namespace="ns1")),
    re_path(r"^ns2/", include(pattern_ns_2, namespace="ns2")),
    re_path(r"^ns_ex/", include(urlexclude, namespace="exclude_namespace")),
    # re_path(r'^ns(?P<ns_arg>[^/]*)/', include(pattern_ns, namespace='ns_arg')),
    re_path(r"^nestedns/", include(pattern_nested_ns, namespace="nestedns")),
    re_path(r"^nsdn/", include(pattern_dubble_nested_ns, namespace="nsdn")),
    re_path(r"^nsno/", include(pattern_only_nested_ns, namespace="nsno")),
]
