# coding: utf-8

# $Id: $
from dvasya.urls import patterns, url, include
from testapp.views import default_view, args, TestView


included = patterns('',
    url('^test/([\d]+)/', args),
    url('^test/(?P<kwarg>[\w]+)/', args),
)

urlpatterns = patterns('',
    url('^include/', include('testapp.urls.included')),
    url('^class/', TestView.as_view()),
    url('^$', default_view),
)
