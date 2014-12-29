# coding: utf-8

# $Id: $
import asyncio
from inspect import isgenerator
from aiohttp.web import Response, Request, StreamResponse
from django.http import StreamingHttpResponse
from django.http.request import HttpRequest
from dvasya.urls import RegexMatchInfo, UrlResolver


class MixedRequest(Request, HttpRequest):
    """ United interface for aiohttp and django Requests."""

    def init(self):
        self.encoding = None
        self.user = None
        self.COOKIES, self.META, self.FILES = {}, {}, {}
        for k, v in self.headers.items():
            self.META[k.upper()] = v

    @classmethod
    def combine(cls, request):
        """ Injects HttpRequest class to request parent classes and initializes
        HttpRequest object attributes for Request instance"""
        request.__class__ = cls
        request.init()
        return request


class MixedStreamingResponse(StreamResponse):

    def __init__(self, *, body=None, status=200,
                 reason=None, headers=None,
                 text=None, content_type=None):
        super().__init__(status=status, reason=reason)
        self._body = body
        if headers is not None:
            self.headers.extend(headers)
        if content_type:
            self.content_type = content_type

    def write_eof(self):
        if self._body:
            for chunk in self._body:
                self.write(chunk)
        return super().write_eof()


class DjangoMatchInfo(RegexMatchInfo):
    """ aiohttp match info to work with django HttpRequest and HttpResponse.

    Transforms aiohttp.web.Request object to django HttpRequest, and constructs
    aiohttp.web.Response if result of request handling is django HttpResponse.
    """

    @staticmethod
    def subclass_request(request: Request) -> MixedRequest:
        """ Patches request class to unite both aiohttp and django Request
        interfaces. """
        return MixedRequest.combine(request)

    @staticmethod
    def subclass_response(response):
        """ Приводит ответ View к классу aiohttp.web.Response. """
        if hasattr(response, 'render'):
            response.render()
        headers = dict(v for k, v in response._headers.items()
                           if k != 'content-type')

        if isinstance(response, StreamingHttpResponse):
            content = response.streaming_content
            return MixedStreamingResponse(body=content,
                            status=response.status_code,
                            headers=headers,
                            content_type=response['Content-Type'])
        else:
            content = response.content
            return Response(body=content,
                            status=response.status_code,
                            headers=headers,
                            content_type=response['Content-Type'])

    @property
    def handler(self):
        return self._wrapper

    @asyncio.coroutine
    def _wrapper(self, request):

        if not isinstance(request, HttpRequest):
            request = self.subclass_request(request)

        ret = self._handler(request, *self._args, **self._kwargs)

        if isgenerator(ret):
            ret = yield from ret

        response = ret
        if not isinstance(response, Response):
            response = self.subclass_response(response)

        return response


class DjangoCompatUrlResolver(UrlResolver):
    match_info_class = DjangoMatchInfo


