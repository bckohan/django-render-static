"""
Reproduce: https://github.com/bckohan/django-render-static/issues/65
"""
from .views import TestView
from django.urls import path


urlpatterns = [
    path(
        'prefix/<int:url_param>/postfix',
        TestView.as_view(),
        kwargs={'kwarg_param': '1'},
        name='bug65'
    ),
    path(
        'prefix/<int:url_param>/postfix/value1',
        TestView.as_view(),
        kwargs={'kwarg_param': '1'},
        name='bug65'
    ),
    path(
        'prefix/<int:url_param>/postfix/value2',
        TestView.as_view(),
        kwargs={'kwarg_param': '2'},
        name='bug65'
    ),
    path(
        'prefix',
        TestView.as_view(),
        kwargs={'kwarg_param': '2'},
        name='bug65'
    ),
    path(
        'prefix_int/<int:url_param>/postfix_int/<int:kwarg_param>',
        TestView.as_view(),
        # kwargs={'kwarg_param': 1},  adding this default breaks reversal
        name='bug65'
    ),
]

