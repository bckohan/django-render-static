from django.urls import path

from ..views import TestView

app_name = 'app1'
urlpatterns = [
    path('app1/', TestView.as_view(), name='app1_pth'),
    path('app1/<int:arg1>', TestView.as_view(), name='app1_pth'),
    path('app1/different/<int:arg1>/<str:arg2>', TestView.as_view(), name='app1_pth'),
    path('app1/different/detail/<uuid:id>/', TestView.as_view(), name='app1_detail'),
    path('app1/test/converter/<year:year>/', TestView.as_view(), name='custom_tst')
]
