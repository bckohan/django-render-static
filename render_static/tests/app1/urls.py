from django.urls import path, re_path

from ..views import TestView

app_name = "app1"
urlpatterns = [
    path("app1/", TestView.as_view(), name="app1_pth"),
    path("app1/<int:arg1>", TestView.as_view(), name="app1_pth"),
    path("app1/different/<int:arg1>/<str:arg2>", TestView.as_view(), name="app1_pth"),
    path("app1/different/detail/<uuid:id>/", TestView.as_view(), name="app1_detail"),
    path("app1/test/converter/<year:year>/", TestView.as_view(), name="custom_tst"),
    path("app1/test/converter/<name:name>/", TestView.as_view(), name="unreg_conv_tst"),
    re_path(
        r"/re_path/unamed/([adfa]{2,3})/(\d+)$",
        TestView.as_view(),
        name="re_path_unnamed",
    ),
]
