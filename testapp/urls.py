# coding: utf-8

# $Id: $
from dvasya.urls import patterns, url, include
from testapp.views import dump_args_view, TestView


included = patterns('',
    url('^test/([\d]+)/', dump_args_view),
    url('^test/(?P<kwarg>[\w]+)/', dump_args_view),
)

urlpatterns = patterns('',
    url('^include/', include('testapp.urls.included')),
    url('^class/', TestView.as_view()),
)
