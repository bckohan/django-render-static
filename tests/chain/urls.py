from django.urls import include, path, re_path

app_name = "chain"

urlpatterns = [
    path("chain/<str:chain>/", include("tests.spa.urls", namespace="spa")),
    re_path(
        r"^chain/(?P<chain>\w+)/",
        include("tests.spa.urls", namespace="spa_re"),
    ),
]
