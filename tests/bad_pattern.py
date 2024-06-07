import re

from django.urls import path

from tests.views import TestView


class Unrecognized:
    regex = re.compile("Im not normal")


class NotAPattern:
    pass


urlpatterns = [path("test/simple/", TestView.as_view(), name="bad"), NotAPattern()]

urlpatterns[0].pattern = Unrecognized()
