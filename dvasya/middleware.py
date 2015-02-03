# coding: utf-8

# $Id: $
import asyncio
from aiohttp.web import Response, StreamResponse
from dvasya.conf import settings
from dvasya.request import DvasyaRequestProxy
from dvasya.response import HttpInternalError
from dvasya.utils import import_object


class DvasyaMiddlewareBase(object):

    @classmethod
    @asyncio.coroutine
    def factory(cls, app, handler):
        return cls(app, handler)

    def __init__(self, app, handler):
        self.app = app
        self.handler = handler

    @asyncio.coroutine
    def __call__(self, request):
        try:
            # process request
            ret = self.process_request(request)
            if asyncio.iscoroutine(ret):
                ret = yield from ret
            # if process_request() returned none, call next middleware
            if ret is None:
                ret = self.handler(request)
                if asyncio.iscoroutine(ret):
                    ret = yield from ret
            # passing response to process_response
            response = ret
        except Exception as e:
            # process exception
            ret = self.process_exception(request, e)
            if asyncio.iscoroutine(ret):
                ret = yield from ret
            if ret is None:
                if settings.DEBUG:
                    return HttpInternalError(e)
                raise
            response = ret
        # if has response from next middleware, or process_request, or
        # process_exception, call process_response(response)

        ret = self.process_response(request, response)
        if asyncio.iscoroutine(ret):
            ret = yield from ret
        if not isinstance(ret, StreamResponse):
            raise RuntimeError(
                "%s.process_response() must return a StreamResponse"
                % self.__class__.__name__)
        return ret

    def process_request(self, request):
        """ called before handler.

        :param request: aiohttp.web.Request
        :return aiohttp.web.Response or None
        """
        return None

    def process_exception(self, request, exc):
        """ called when exception occured in process_request or in handler.

        :param request: aiohttp.web.Request
        :param exc: Exception
        :return aiohttp.web.Response or None
        """
        return None

    def process_response(self, request, response):
        """ called after receiving response from process_request, handler
        or process_exception

        :param request: aiohttp.web.Request
        :param response: aiohttp.web.Response
        :return aiohttp.web.Response

        MUST return aiohttp.web.Response object!
        """
        return response


class RequestProxyMiddleware(DvasyaMiddlewareBase):
    request_class = DvasyaRequestProxy
    response_class = Response

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


def load_middlewares():
    result = []
    for classname in settings.DVASYA_MIDDLEWARES:
        middleware_class = import_object(classname)
        if not hasattr(middleware_class, 'factory'):
            raise ValueError("Invalid middleware class %s" % classname)
        result.append(middleware_class.factory)
    return result
