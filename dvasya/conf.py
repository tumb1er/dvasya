# coding: utf-8

# $Id: $
from dvasya import defaults


__all__ = ['settings']
import os


def _load_settings():
    module_name = os.environ.get("DVASYA_SETTINGS_MODULE", 'settings')
    module = __import__(module_name, fromlist='*')
    for attr in dir(defaults):
        if not hasattr(module, attr):
            setattr(module, attr, getattr(defaults, attr))
    return module

settings = _load_settings()
