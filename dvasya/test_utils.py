# coding: utf-8

# $Id: $
import email
from functools import wraps
from io import BytesIO
import unittest
from urllib.parse import urlencode
import asyncio

from aiohttp import protocol, streams, web, parsers, client
from dvasya.cookies import parse_cookie
from dvasya.middleware import load_middlewares

try:
    from unittest import mock
except ImportError:
    import mock

from dvasya.urls import UrlResolver, load_resolver
from dvasya.conf import settings

__all__ = ['DvasyaHttpClient', 'DvasyaTestCase', 'override_settings']


class override_settings(object):
    def __init__(self, **kwargs):
        self.old_values = {}
        self.new_values = {}
        for k, v in kwargs.items():
            if hasattr(settings, k):
                self.old_values[k] = getattr(settings, k)
            self.new_values[k] = v

    def __call__(self, decorated):
        if isinstance(decorated, type):
            return self.decorate_class(decorated)
        return self.decorate_callable(decorated)

    def decorate_class(self, klass):
        for attr in klass.__dict__:
            if not attr.startswith('test'):
                continue
            if callable(getattr(klass, attr)):
                new_func = self.decorate_callable(getattr(klass, attr))
                setattr(klass, attr, new_func)
        return klass

    def start(self):
        for k, v in self.new_values.items():
            setattr(settings, k, v)

    def stop(self):
        for k, v in self.new_values.items():
            if k in self.old_values:
                setattr(settings, k, self.old_values[k])
            else:
                delattr(settings, k)

    def decorate_callable(self, func):

        @wraps(func)
        def inner(*args, **kwargs):
            try:
                self.start()
                return func(*args, **kwargs)
            finally:
                self.stop()

        return inner

    def __enter__(self):
        self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


class ResponseParser:
    """ Parses byte stream from HttpBuffer.

    Constructs django-style HttpClient response object
    """

    def __init__(self, buffer):
        self.buffer = buffer

    def parse_http_message(self, message, length=None):
        """ Parses HTTP headers."""
        self.message = message
        headers = email.message.Message()
        for hdr, val in message.headers.items():
            headers.add_header(hdr, val)
        self.response = web.Response(reason=message.reason,
                                     status=message.code,
                                     headers=headers,
                                     body=b'')
        self.response._cookies = parse_cookie(headers.get('set-cookie', ''))

    def parse_http_content(self, content, length=None):
        """ Parses response body, dealing with transfer-encodings."""
        self.response.body += content

    def feed_eof(self):
        pass

    def __call__(self):
        parser = protocol.HttpResponseParser()
        self.feed_data = self.parse_http_message
        yield from parser(self, self.buffer)

        parser = protocol.HttpPayloadParser(self.message)
        self.feed_data = self.parse_http_content
        yield from parser(self, self.buffer)
        return self.response


class DvasyaHttpClient:
    """ Test Client for dvasya server. """
    peername = ('127.0.0.1', '12345')

    def __init__(self, *, urlconf=None, middlewares=None, resolver=None):
        self.root_urlconf = urlconf
        self.middlewares = middlewares or load_middlewares()
        self.resolver_class = resolver or load_resolver()

    def create_server(self):
        router = self.resolver_class(root_urlconf=self.root_urlconf)
        app = web.Application(router=router,
                              loop=self._loop,
                              middlewares=self.middlewares)
        handler = app.make_handler()
        return handler

    def request(self, method, path, request_body, headers=None):
        """ Runs request handling procedure.

        Starts async loop, passes http request to server, captures response.
        """
        path = self._fix_url(path)

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        if not isinstance(request_body, bytes):
            request_body = bytes(request_body, encoding='utf-8')
        self._inputstream = request_body
        self._method = method
        self._path = path
        self._headers = headers or {}
        self._transport = mock.Mock()
        self._transport.write = mock.Mock(side_effect=self._capture_response)
        self._transport.close._is_coroutine = False
        self._transport._conn_lost = 0

        self._transport.get_extra_info = mock.Mock(
            side_effect=self._get_extra_info)
        self._create_response()
        self._server = self.create_server()
        self._handler = self._server()
        self._handler.connection_made(self._transport)
        self._loop.run_until_complete(
            asyncio.async(self._process_request(), loop=self._loop))
        asyncio.set_event_loop(None)
        return self.response

    @asyncio.coroutine
    def _serialize_request(self, request):
        transport = mock.Mock()
        result = BytesIO()
        transport.write = mock.Mock(side_effect=result.write)
        request.send(transport, transport)
        yield from request.write_bytes(transport, None)
        return result.getvalue()

    @asyncio.coroutine
    def _process_request(self):
        """ Asynchronously processes request.

        Prepares server for processing requests,
        fill input stream with request data,
        runs request handler and parses response.
        """
        request = client.ClientRequest(self._method, self._path,
                                       headers=self._headers,
                                       data=self._inputstream)
        data = yield from self._serialize_request(request)

        reader = self._handler.reader

        reader.feed_data(data)
        reader.feed_eof()

        prefix = reader.set_parser(self._handler._request_prefix)
        yield from prefix.read()

        # read request headers
        httpstream = reader.set_parser(self._handler._request_parser)
        message = yield from httpstream.read()

        payload = streams.FlowControlStreamReader(
            reader, loop=self._loop)
        reader.set_parser(protocol.HttpPayloadParser(message), payload)

        handler = self._handler.handle_request(message, payload)

        if (asyncio.iscoroutine(handler) or
                isinstance(handler, asyncio.Future)):
            yield from handler

        response_parser = ResponseParser(self._buffer)
        self.response = yield from response_parser()

    def _capture_response(self, bytes):
        """ Captures output stream to separate buffer."""
        self._buffer.feed_data(bytes)

    def _fix_url(self, url):
        if not url.startswith('http://'):
            if not url.startswith('/'):
                url = '/' + url
            url = 'http://localhost' + url
        return url

    def get(self, url, headers=None):
        return self.request('GET', url, b'', headers=headers)

    def head(self, url, headers=None):
        return self.request('HEAD', url, b'', headers=headers)

    def delete(self, url, headers=None):
        return self.request('DELETE', url, b'', headers=headers)

    def post(self, url, headers=None, data=None, body=b''):
        if not body and data:
            body = bytes(urlencode(data), encoding="utf-8")
        return self.request('POST', url, body, headers=headers)

    def put(self, url, headers=None, data=None, body=b''):
        if not body and data:
            body = bytes(urlencode(data), encoding="utf-8")
        return self.request('PUT', url, body, headers=headers)

    def patch(self, url, headers=None, data=None, body=b''):
        if not body and data:
            body = bytes(urlencode(data), encoding="utf-8")
        return self.request('PATCH', url, body, headers=headers)

    def finish(self):
        """ Stops reactor loop."""
        try:
            self._loop.stop()
        except AttributeError:
            pass

    def _get_transport_extra(self):
        """ Prepares extra data for transport."""
        return {
            'peername': self.peername,
            'socket': mock.MagicMock()
        }

    def _get_extra_info(self, key, default=None):
        return self._get_transport_extra().get(key, default)

    def _create_response(self):
        """ Prepares response parser buffer."""
        self._buffer = parsers.ParserBuffer()


class DvasyaTestCase(unittest.TestCase):
    # List of middlewares to init in dvasya app
    middlewares = []

    # ROOT_URLCONF setting form dvasya app
    root_urlconf = None

    resolver_class = UrlResolver

    def setUp(self):
        super().setUp()
        self.client = DvasyaHttpClient(urlconf=self.root_urlconf,
                                       middlewares=self.middlewares,
                                       resolver=self.resolver_class)

    def tearDown(self):
        super().tearDown()
        self.client.finish()
