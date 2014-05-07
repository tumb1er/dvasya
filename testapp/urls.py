# coding: utf-8

# $Id: $
from dvasya.urls import patterns, url, include
from testapp.views import function_view, ClassBasedView


included = patterns('',
    url('^test_args/([\d]+)/(?P<kwarg>[\w]+)/', function_view),
    url('^test_include/$', function_view)
)

urlpatterns = patterns('',
    url('^include/', include('testapp.urls.included')),
    url('^class/', ClassBasedView.as_view()),
    url('^function/$', function_view),
)
