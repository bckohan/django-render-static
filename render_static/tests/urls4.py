from django.urls import re_path

from .views import TestView

urlpatterns = [
    re_path(r"^special2/((?:first)|(?:third))$", TestView.as_view(), name="special"),
    re_path(
        r"^special1/(?P<choice>(:?first)|(:?second))$",
        TestView.as_view(),
        name="special",
    ),
]
