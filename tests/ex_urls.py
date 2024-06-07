from django.contrib import admin
from django.urls import include, path

from .views import TestView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("simple", TestView.as_view(), name="simple"),
    path("simple/<int:arg1>", TestView.as_view(), name="simple"),
    path("different/<int:arg1>/<str:arg2>", TestView.as_view(), name="different"),
]
