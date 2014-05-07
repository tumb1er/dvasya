# coding: utf-8

# $Id: $
import email
from io import BytesIO
import unittest
from urllib.parse import urlencode

from aiohttp.client import HttpRequest
import asyncio
from aiohttp import HttpResponseParser
import aiohttp
from aiohttp.protocol import HttpPayloadParser


try:
    from unittest import mock
except:
    import mock

from dvasya.response import HttpResponse
from dvasya.server import HttpServer


__all__ = ['DvasyaHttpClient', 'DvasyaTestCase']


class ResponseParser:
    """ Parses byte stream from HttpBuffer.

    Constructs django-style HttpClient response object
    """

    def __init__(self, buffer):
        self.buffer = buffer

    def parse_http_message(self, message):
        """ Parses HTTP headers."""
        self.message = message
        headers = email.message.Message()
        for hdr, val in message.headers:
            headers.add_header(hdr, val)
        self.response = HttpResponse(message.reason, status=message.code,
                                     http_version=message.version,
                                     content_type=headers.get('content-type'))
        self.response.headers = headers

    def parse_http_content(self, content):
        """ Parses response body, dealing with transfer-encodings."""
        self.response.content = content.decode('utf-8')

    def feed_eof(self):
        pass

    def __call__(self):
        parser = HttpResponseParser()
        self.feed_data = self.parse_http_message
        yield from parser(self, self.buffer)

        parser = HttpPayloadParser(self.message)
        self.feed_data = self.parse_http_content
        yield from parser(self, self.buffer)
        return self.response


class DvasyaHttpClient:
    """ Test Client for dvasya server. """
    peername = ('127.0.0.1', '12345')

    def _run_request(self, method, path, request_body, headers=None):
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
        self._transport._conn_lost = 0

        self._transport.get_extra_info = mock.Mock(
            side_effect=self._get_extra_info)
        self._create_response()
        self._server = HttpServer(loop=self._loop)
        self._server.connection_made(self._transport)
        self._loop.run_until_complete(
            asyncio.async(self._process_request(), loop=self._loop))
        asyncio.set_event_loop(None)
        return self.response

    @asyncio.coroutine
    def _serialize_request(self, request):
        transport = mock.Mock()
        result = BytesIO()
        transport.write = mock.Mock(side_effect=result.write)
        yield from request.send(transport, transport)
        return result.getvalue()

    @asyncio.coroutine
    def _process_request(self):
        """ Asynchronously processes request.

        Prepares server for processing requests,
        fill input stream with request data,
        runs request handler and parses response.
        """
        request = HttpRequest(self._method, self._path, headers=self._headers,
                              data=self._inputstream)
        data = yield from self._serialize_request(request)

        http_stream = self._server.reader.set_parser(
            self._server._request_parser)
        self._server.reader.feed_data(data)
        self._server.reader.feed_data(self._inputstream)
        message = yield from http_stream.read()
        payload = self._server.reader.set_parser(
            aiohttp.HttpPayloadParser(message))

        yield from self._server.handle_request(message, payload)

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
        return self._run_request('GET', url, b'', headers=headers)

    def head(self, url, headers=None):
        return self._run_request('HEAD', url, b'', headers=headers)

    def delete(self, url, headers=None):
        return self._run_request('DELETE', url, b'', headers=headers)

    def post(self, url, headers=None, data=None, body=b''):
        if not body and data:
            body = bytes(urlencode(data), encoding="utf-8")
        return self._run_request('POST', url, body, headers=headers)

    def put(self, url, headers=None, data=None, body=b''):
        if not body and data:
            body = bytes(urlencode(data), encoding="utf-8")
        return self._run_request('PUT', url, body, headers=headers)

    def patch(self, url, headers=None, data=None, body=b''):
        if not body and data:
            body = bytes(urlencode(data), encoding="utf-8")
        return self._run_request('PATCH', url, body, headers=headers)

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
        self._buffer = aiohttp.parsers.ParserBuffer()


class DvasyaTestCase(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.client = DvasyaHttpClient()

    def tearDown(self):
        super().tearDown()
        self.client.finish()

