# coding: utf-8

# $Id: $


"""
Using gunicorn for managing dvasya workers, security,
load balancing etc...

@see: http://gunicorn.org/
"""

import functools
import os

from aiohttp import web
from gunicorn.workers import gaiohttp

from dvasya.logging import getLogger
from dvasya.urls import UrlResolver


class GunicornWorker(gaiohttp.AiohttpWorker):

    logger = getLogger('dvasya.worker')
    middlewares = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if os.environ.get('DJANGO_SETTINGS_MODULE'):
            self.install_django_handlers()

    def install_django_handlers(self):
        try:
            import django
            django.setup()
        except ImportError:
            self.logger.warning(
                "DJANGO_SETTINGS_MODULE environment variable is set "
                "but no django is available. Skip installing django handlers.")
        from dvasya.contrib.django import django_middleware_factory
        self.middlewares = [django_middleware_factory]

    def web_factory(self, handler):
        proto = handler()
        return self.wrap_protocol(proto)

    def get_factory(self, sock, addr):
        app = web.Application(router=UrlResolver(),
                              loop=self.loop,
                              middlewares=self.middlewares)
        return functools.partial(self.web_factory, app.make_handler())


app = lambda: None