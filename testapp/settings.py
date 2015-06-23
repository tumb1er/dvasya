# coding: utf-8

# $Id: $

DEBUG = True

ROOT_URLCONF = 'testapp.urls'

URL_RESOLVER_CLASS = 'dvasya.contrib.django.DjangoUrlResolver'

# All above is needed for Django setup.

SECRET_KEY = 'secret_key_for_django'

INSTALLED_APPS = [
    'django.contrib.staticfiles',
    'django.contrib.contenttypes',
    'django.contrib.admin',
    'rest_framework',
]

STATIC_URL = '/static/'

DEFAULT_CHARSET = 'utf-8'