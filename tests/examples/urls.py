from django.contrib import admin
from django.urls import path

from ..views import TestView as MyView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("simple", MyView.as_view(), name="simple"),
    path("simple/<int:arg1>", MyView.as_view(), name="simple"),
    path("different/<int:arg1>/<str:arg2>", MyView.as_view(), name="different"),
]
