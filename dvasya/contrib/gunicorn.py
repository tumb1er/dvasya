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
# noinspection PyPackageRequirements
from gunicorn.workers import gaiohttp

from dvasya.logging import getLogger
from dvasya.conf import settings
from dvasya.middleware import load_middlewares
from dvasya.urls import UrlResolver, load_resolver


class GunicornWorker(gaiohttp.AiohttpWorker):
    logger = getLogger('dvasya.worker')
    middlewares = load_middlewares()
    resolver_class = UrlResolver

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reinit_logging()
        if os.environ.get('DJANGO_SETTINGS_MODULE'):
            self.install_django_handlers()

    def reinit_logging(self):
        """ Replaces handlers for dvasya loggers with gunicorn log handlers."""
        try:
            loggers = settings.LOGGING['loggers'].keys()
        except KeyError:
            return
        for name in loggers:
            logger = getLogger(name)
            if name == 'dvasya.request':
                handlers = self.log.access_log.handlers
            else:
                handlers = self.log.error_log.handlers
            for h in handlers:
                if h not in logger.handlers:
                    logger.addHandler(h)

    def install_django_handlers(self):
        try:
            # noinspection PyUnresolvedReferences
            import django

            django.setup()
        except ImportError:
            self.logger.warning(
                "DJANGO_SETTINGS_MODULE environment variable is set "
                "but no django is available. Skip installing django handlers.")
        from dvasya.contrib import django as django_contrib

        self.middlewares = [
            django_contrib.DjangoRequestProxyMiddleware.factory
        ]

        self.resolver_class = load_resolver()

    def web_factory(self, handler):
        proto = handler()
        return self.wrap_protocol(proto)

    def get_factory(self, sock, addr):
        application = web.Application(router=self.resolver_class(),
                                      loop=self.loop,
                                      middlewares=self.middlewares,
                                      logger=self.log)
        return functools.partial(self.web_factory, application.make_handler(
            access_log=self.log.access_log
        ))


def app():
    """ Not used """
    return None
