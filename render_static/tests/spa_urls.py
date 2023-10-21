from django.urls import include, path

urlpatterns = [
    path('spa1/', include('render_static.tests.spa.urls', namespace='spa1')),
    path('spa2/', include('render_static.tests.spa.urls', namespace='spa2'))
]
