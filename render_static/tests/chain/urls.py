from django.urls import path, include

app_name = 'chain'

urlpatterns = [
    path(
        'chain/<str:chain>/',
        include('render_static.tests.spa.urls', namespace='spa')
    ),
]
