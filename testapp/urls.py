# coding: utf-8

# $Id: $
from dvasya.urls import patterns, url, include
from testapp.views import default_view, agrs_view


included = patterns('',
    url('^test/([\d]+)/', agrs_view),
    url('^test/(?P<kwarg>[\w]+)/', agrs_view),
)

urlpatterns = patterns('',
    url('^include/', include('testapp.urls.included')),
    url('^$', default_view),
)
