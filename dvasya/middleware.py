# coding: utf-8

# $Id: $
import asyncio
from aiohttp.web import Response
from dvasya.request import DvasyaRequestProxy


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
        result = self.handler(proxy)
        if asyncio.iscoroutine(result):
            result = yield from result
        return self.get_response_proxy(result)

    def get_request_proxy(self, request):
        return self.request_class(request)

    def get_response_proxy(self, result):
        if isinstance(result, self.response_class):
            return result
        else:
            # noinspection PyArgumentList
            return self.response_class(result)
