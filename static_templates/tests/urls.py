from django.contrib import admin
from django.urls import include, path, re_path

from .app1 import urls as app1_urls
from .views import TestView

"""
- Same names can generate different urls, so url generated must be mapped to argument set
    - how to do this in javascript?
- When args are same, given same name the path further down the list takes precedence
- Strategy of doing string replace on reversed paths is complicated by not knowing how to generate
    dummy strings from regex
    - Options:
        1) Use a lib to generate dummy strings
            - not many available, ones that are have problematic licenses or dont seem reliable
        ** 2) Only support paths with registered converters and hardcode dummy strings based on 
            converter type
            - do not support re_path for now
            - or allow specification of generators for specific args in re_paths
        3) Do direct string manipulation of pattern, bypassing reverse logic
            - how to get route string out of regex string?
            - maybe do 2 for paths and this one for re_paths?
- Only work with namespaces (which default to app_name if not provided on include)
    - notable when the same app is included multiple times
    - include note in the docs
- Nested includes, nest namespaces
        
"""
urlpatterns = [
    #path('admin/', admin.site.urls),
    path('test/simple/', TestView.as_view(), name='path_tst'),
    path('test/simple/<int:arg1>', TestView.as_view(), name='path_tst'),
    path('test/different/<int:arg1>/<str:arg2>', TestView.as_view(), name='path_tst'),
    path('sub1/', include('static_templates.tests.app1.urls', namespace='sub1')),
    path('sub2/', include('static_templates.tests.app1.urls', namespace='sub2')),
    path('sub3/', include('static_templates.tests.app2.urls')),
    re_path(r'^re_path/[adfa]{2,3}$', TestView.as_view(), name='re_path_tst'),
    re_path(r'^re_path/(?P<strarg>\w+)/$', TestView.as_view(), name='re_path_tst'),
    re_path(r'^re_path/(?P<strarg>\w+)/(?P<intarg>\d+)/$', TestView.as_view(), name='re_path_tst'),
    #re_path(r'^re_path/([adfa]{2,3})$', TestView.as_view(), name='re_path_tst'), TODO support unamed arguments
]
