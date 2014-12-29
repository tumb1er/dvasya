# coding: utf-8

# $Id: $
from dvasya.urls import patterns, url
from testapp import views


included = patterns('',
    url('^test_args/([\d]+)/([\w]+)/', views.function_view),
    url('^test_args_kwargs/([\d]+)/(?P<kwarg>[\w]+)/', views.function_view),
    url('^test_include/$', views.function_view)
)

