# coding: utf-8

# $Id: $

from django.conf.urls import patterns, url
from django.contrib.staticfiles.views import serve
from testapp.django_compat import views


urlpatterns = patterns('',
    url('^rest/$', views.SampleView.as_view()),
    url('^static/(?P<path>.*)', serve)
)

