# coding: utf-8

# $Id: $
import email
from io import BytesIO
import unittest
from urllib.parse import urlencode
import asyncio

from aiohttp import protocol, streams, web, parsers, client


try:
    from unittest import mock
except:
    import mock

from dvasya.response import HttpResponse
from dvasya.urls import UrlResolver


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
        for hdr, val in message.headers.items():
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

    def create_server(self):
        router = UrlResolver()
        app = web.Application(router=router, loop=self._loop)
        handler = app.make_handler()
        return handler

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
        self._buffer = parsers.ParserBuffer()


class DvasyaTestCase(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.client = DvasyaHttpClient()

    def tearDown(self):
        super().tearDown()
        self.client.finish()

