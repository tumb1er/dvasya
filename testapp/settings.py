# coding: utf-8

# $Id: $

DEBUG = True

ROOT_URLCONF='testapp.urls'

SECRET_KEY = 'ASDSAD'

INSTALLED_APPS=[
    'django.contrib.staticfiles',
    'rest_framework'
]

STATIC_URL='/static/'