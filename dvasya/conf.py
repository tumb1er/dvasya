# coding: utf-8

# $Id: $


__all__ = ['settings']
import os


def _load_settings():
    module_name = os.environ.get("DVASYA_SETTINGS_MODULE", 'settings')
    module = __import__(module_name, fromlist='*')
    print(dir(module))
    return module

settings = _load_settings()
