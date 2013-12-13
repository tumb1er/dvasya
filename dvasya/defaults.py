# coding: utf-8

# $Id: $

# root url configuration module name
ROOT_URLCONF = 'urls'

# debug flag
DEBUG = True

# internal logging setup
LOGGING = {
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '%(created)s %(levelname): %(message)',
            'datefmt': '%Y-%m-%D %H%M%S',
        }
    },
    'handlers': {
        'console':{
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
            'formatter': 'default',
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