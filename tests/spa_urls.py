from django.urls import include, path

urlpatterns = [
    path("spa1/", include("tests.spa.urls", namespace="spa1")),
    path("spa2/", include("tests.spa.urls", namespace="spa2")),
]
