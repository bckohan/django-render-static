from django.urls import path, include, re_path

app_name = 'chain'

urlpatterns = [
    path(
        'chain/<str:chain>/',
        include('render_static.tests.spa.urls', namespace='spa')
    ),
    re_path(
        r'^chain/(?P<chain>\w+)/',
        include('render_static.tests.spa.urls', namespace='spa_re')
    )
]
