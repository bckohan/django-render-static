from django.urls import include, path

from ..views import TestView

app_name = "app2"
urlpatterns = [
    path("app1_inc/", include("tests.app1.urls")),
    path("app2/", TestView.as_view(), name="app2_pth"),
    path("app2/<slug:arg1>", TestView.as_view(), name="app2_pth"),
    path(
        "app2/different/<uuid:arg1>/<path:arg2>",
        TestView.as_view(),
        name="app2_pth_diff",
    ),
]
