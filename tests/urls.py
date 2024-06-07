from django.contrib import admin
from django.urls import include, path, re_path

from .views import TestView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("test/simple/", TestView.as_view(), name="path_tst"),
    path("test/simple/<int:arg1>", TestView.as_view(), name="path_tst"),
    path("test/different/<int:arg1>/<str:arg2>", TestView.as_view(), name="path_tst"),
    path("sub1/", include("tests.app1.urls", namespace="sub1")),
    path("sub2/", include("tests.app1.urls", namespace="sub2")),
    path("sub3/", include("tests.app2.urls")),
    # django doesnt support inclusions with additional arguments
    # path('<str:root_var>/sub2/', include('tests.app1.urls', namespace='sub2')),
    path("", include("tests.app3.urls")),  # included into the default ns
    re_path(r"^re_path/[adfa]{2,3}$", TestView.as_view(), name="re_path_tst"),
    re_path(r"^re_path/(?P<strarg>\w+)/$", TestView.as_view(), name="re_path_tst"),
    re_path(
        r"^re_path/(?P<strarg>\w+)/(?P<intarg>\d+)$",
        TestView.as_view(),
        name="re_path_tst",
    ),
    re_path(
        r"^re_path/unamed/([adfa]{2,3})/(\d+)$",
        TestView.as_view(),
        name="re_path_unnamed",
    ),
    re_path(
        r"re_path/solo/([adfa]{2,3})/(\d+)/trailing/stuff/$",
        TestView.as_view(),
        name="re_path_unnamed_solo",
    ),
    # django doesnt allow reversals of mixed named/unnamed - we skip them!
    re_path(
        r"^re_path/([adfa]{2,3})/(?P<strarg>\w+)/(\d+){2}/(?P<intarg>\d+)$",
        TestView.as_view(),
        name="re_path_mixed",
    ),
]
