# coding: utf-8

# $Id: $

from django.conf.urls import patterns, url, include
from django.contrib.staticfiles.views import serve
from django.contrib import admin
from testapp.django_compat import views

admin.autodiscover()

urlpatterns = patterns('',
    url(r'^admin/', include(admin.site.urls)),
    url('^rest/$', views.SampleView.as_view()),
    url('^static/(?P<path>.*)', serve)
)

