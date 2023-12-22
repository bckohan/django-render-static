from django.urls import re_path

from .views import TestView

urlpatterns = [
    # this half works in django reverse - there's no way to call it with an
    # argument
    # re_path(
    #     r'^blog/(page-([0-9]+)/)?$',
    #     TestView.as_view(),
    #     name='nested_re_path_unnamed'
    # ),
    re_path(
        r"^comments/(?:page-(?P<page_number>[0-9]+)/)?$",
        TestView.as_view(),
        name="nested_re_path_named",
    )
]
