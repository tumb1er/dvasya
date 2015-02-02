# coding: utf-8

# $Id: $

DEBUG = True

ROOT_URLCONF = 'testapp.urls'

# All above is needed for Django setup.

SECRET_KEY = 'secret_key_for_django'

INSTALLED_APPS = [
    'django.contrib.staticfiles',
    'rest_framework'
]

STATIC_URL = '/static/'

DEFAULT_CHARSET = 'utf-8'