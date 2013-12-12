# coding: utf-8

# $Id: $


ROOT_URLCONF = 'urls'
DEBUG = True

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