# coding: utf-8

# $Id: $
import asyncio
import cgi
import codecs
from aiohttp.multidict import CIMultiDictProxy, CIMultiDict

from aiohttp.web import Request, Response, StreamResponse
from aiohttp.web_reqrep import FileField
from django.core.urlresolvers import Resolver404
from django.http import StreamingHttpResponse
from django.http.request import HttpRequest
from dvasya.urls import UrlResolver

from dvasya.cookies import parse_cookie
from dvasya.middleware import RequestProxyMiddleware


class DjangoRequestProxy(HttpRequest):
    """ Proxy for aiohttp.web.Request

    Should be used as Django HttpRequest.
    """

    def __init__(self, request: Request):
        super().__init__()
        self.__request = request
        self.encoding = self._parse_encoding(request)
        self.method = request.method
        self.GET = request.GET
        self.COOKIES = parse_cookie(request.headers.get("COOKIE", ""))
        self._init_meta(request)

    def post(self):
        # FIXME: for now (aiohttp==1.14.x) payload is parsed by cgi parser
        task = asyncio.Task(self.__request.post())
        task.add_done_callback(self._process_payload)
        return task

    def _process_payload(self, task):
        data = task.result()
        for key, value in data.items():
            if isinstance(value, FileField):
                self.FILES[key] = self._file_field(value)
            else:
                self.POST[key] = value
        return data

    def _file_field(self, value):
        # FIXME: aiohttp.FileField is not compatible with django one's
        return value

    def _parse_encoding(self, request):
        content_type = request.headers.get('CONTENT-TYPE', '')
        _, content_params = cgi.parse_header(content_type)
        if 'charset' in content_params:
            try:
                codecs.lookup(content_params['charset'])
            except LookupError:
                pass
            else:
                return content_params['charset']
        return None

    def _init_meta(self, request):
        transport = self.__request.transport
        remote_addr, remote_port = transport.get_extra_info("peername")
        meta = CIMultiDict({
            k.replace('-', '_'): v
            for k, v in request.headers.items()})
        peer_info = {
            'REMOTE_ADDR': remote_addr,
            "REMOTE_PORT": remote_port
        }
        meta.update(peer_info)
        self.META = CIMultiDictProxy(meta)


class DjangoRequestProxyMiddleware(RequestProxyMiddleware):
    request_class = DjangoRequestProxy

    def get_response_proxy(self, response):
        if isinstance(response, self.response_class):
            return response
        elif isinstance(response, StreamingHttpResponse):
            response_class = StreamingResponseProxy
        else:
            response_class = ResponseProxy
        return response_class(response)


class ResponseProxy(Response):
    """ Proxy for Django HttpResponse.

    Should be used as aiohttp.web.Response.
    """
    def __init__(self, response):
        if hasattr(response, 'render') and callable(response.render):
            response.render()
        super(ResponseProxy, self).__init__(
            body=response.content,
            status=response.status_code,
            headers=response
        )
        self.__response = response


class StreamingResponseProxy(StreamResponse):
    """ Proxy for Django StreamResponse

    Should be used as aiohttp.web.Response.
    """

    def __init__(self, response: StreamingHttpResponse):
        super().__init__(status=response.status_code)
        self.__response = response

    def write_eof(self):
        if self.__response.streaming_content:
            for chunk in self.__response.streaming_content:
                self.write(chunk)
        return super().write_eof()


class DjangoUrlResolver(UrlResolver):
    def match_pattern(self, pattern, request_path):
        try:
            return super().match_pattern(pattern, request_path)
        except Resolver404:
            return None
