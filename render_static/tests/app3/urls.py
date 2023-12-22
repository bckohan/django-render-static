from django.urls import path

from ..views import TestView

urlpatterns = [
    path("app3/", TestView.as_view(), name="app3_idx"),
    path("app3/<int:arg1>", TestView.as_view(), name="app3_arg"),
    path("app3/test/converter/<name:name>/", TestView.as_view(), name="unreg_conv_tst"),
]
