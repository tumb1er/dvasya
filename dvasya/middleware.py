# coding: utf-8

# $Id: $
import asyncio
from aiohttp.web import Response, HTTPInternalServerError
from dvasya.conf import settings
from dvasya.request import DvasyaRequestProxy
from dvasya.response import HttpInternalError


class RequestProxyMiddleware(object):
    request_class = DvasyaRequestProxy
    response_class = Response

    @classmethod
    @asyncio.coroutine
    def factory(cls, app, handler):
        return cls(app, handler)

    def __init__(self, app, handler):
        self.app = app
        self.handler = handler

    def __call__(self, request):
        proxy = self.get_request_proxy(request)
        try:
            result = self.handler(proxy)
            if asyncio.iscoroutine(result):
                result = yield from result
        except Exception as e:
            if settings.DEBUG:
                return HttpInternalError(e)
            raise

        return self.get_response_proxy(result)

    def get_request_proxy(self, request):
        return self.request_class(request)

    def get_response_proxy(self, result):
        if isinstance(result, self.response_class):
            return result
        else:
            # noinspection PyArgumentList
            return self.response_class(result)

    def format_traceback(self, exc):
        import traceback
        trace = traceback.format_exc()
        return "<h2>"
