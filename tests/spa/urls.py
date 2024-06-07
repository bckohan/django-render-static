from django.urls import path

from ..views import TestView
from .views import SPAIndex

app_name = "spa"

urlpatterns = [
    path("", SPAIndex.as_view(), name="index"),
    path("qry/", TestView.as_view(), name="qry"),
    path("qry/<int:arg>", TestView.as_view(), name="qry"),
]
