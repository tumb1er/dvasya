# coding: utf-8

# $Id: $
from dvasya.urls import patterns, url, include
from testapp import views


urlpatterns = patterns('',
    url('^include/', include('testapp.included_urls.included')),
    url('^class/', views.ClassBasedView.as_view()),
    url('^function/$', views.function_view),
    url('^json/$', views.json_view),
)
