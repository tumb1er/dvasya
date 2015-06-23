# coding: utf-8

# $Id: $

# root url configuration module name
ROOT_URLCONF = 'urls'

# debug flag
DEBUG = True

# temporary directory for files
FILE_UPLOAD_TEMP_DIR = '/tmp/'

DVASYA_MIDDLEWARES = [
    'dvasya.middleware.RequestProxyMiddleware',
]

URL_RESOLVER_CLASS = 'dvasya.urls.UrlResolver'

# internal logging setup
LOGGING = {
    'disable_existing_loggers': False,
    'version': 1,
    'formatters': {
        'default': {
            'format': '%(name)s %(asctime)s %(levelname)s: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'errors': {
            'format': '%(asctime)s %(method)s %(path)s - %(message)s',
        }
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'default',
        },
        'null': {
            'class': 'logging.NullHandler',
            'formatter': 'default',
        },
        'errors': {
            'level': 'ERROR',
            'class': 'logging.StreamHandler',
            'formatter': 'errors',
        },
    },
    'loggers': {
        'dvasya': {
            'handlers': ['console'],
        },
        'dvasya.request': {
            'handlers': ['errors'],
            'level': 'ERROR',
            'propagate': False,
        },
    }
}
