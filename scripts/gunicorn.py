#!/usr/bin/env python
# coding: utf-8

# $Id: $
import os
import re
import sys
from gunicorn.app.wsgiapp import run
from gunicorn.workers import SUPPORTED_WORKERS

SUPPORTED_WORKERS['dvasya'] = 'dvasya.contrib.gunicorn.GunicornWorker'


if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw|\.exe)?$', '', sys.argv[0])
    os.environ.setdefault('DVASYA_SETTINGS_MODULE', 'settings')
    if ['-k', 'dvasya'] not in sys.argv:
        sys.argv.extend(['-k', 'dvasya', 'dvasya.contrib.gunicorn:app'])
    sys.exit(run())
