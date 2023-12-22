from django.urls import path

from .views import TestView

urlpatterns = [
    path("order1", TestView.as_view(), name="order"),
    path("order2", TestView.as_view(), name="order"),
    path("order3/<str:kwarg1>", TestView.as_view(), name="order"),
    path("order4/<str:kwarg1>", TestView.as_view(), name="order"),
]
