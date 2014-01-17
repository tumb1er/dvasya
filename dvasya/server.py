# coding: utf-8

# $Id: $

# Production-ready http server.
#
# Dvasya http server has following capabilities:
# * daemonize
# * master-worker multiprocess configuration
# * pidfile, host and port options
# * worker shutdown on SIGINT, SIGTERM or master death.
#
# inspired by aiohttp.examples.mpsrv.HttpServer
# @see https://github.com/fafhrd91/aiohttp
from http.cookies import SimpleCookie

import os
import signal
import socket
import email.message
from urllib import parse
import time
import sys
import atexit
import asyncio

import aiohttp.server
from aiohttp import websocket

from dvasya.logging import getLogger
from dvasya.response import HttpResponseNotFound
from dvasya.urls import UrlResolver, NoMatch


class HttpServer(aiohttp.server.ServerHttpProtocol):
    """ Asynchronous HTTP Server."""

    resolver = UrlResolver.autodiscover()
    logger = getLogger('dvasya.request')

    @asyncio.coroutine
    def get_response(self, request):
        """ Resolves view class by request path and calls request handler.

        If no handler is found by resolver, returns 404 page.
        """
        try:
            result = yield from self.resolver.dispatch(request, self.transport)
            return result
        except NoMatch as e:
            return HttpResponseNotFound(e)

    def get_http_headers(self, message):
        """ Transforms headers from aiohttp.message to more usable form.

        @param message: http request object
        @type message: aiohttp.RawRequestMessage

        @return: http readers container
        @rtype: email.message.Message
        """
        headers = email.message.Message()
        for hdr, val in message.headers:
            headers.add_header(hdr, val)
        return headers

    @asyncio.coroutine
    def handle_request(self, message, payload):
        """ Handles HTTP request.

        Constructs request from http message,
        computes response and writes content of HttpResponse to client.

        @param message: http request object
        @type message: aiohttp.RawRequestMessage

        @param payload: http request stream handler
        @type payload: aiohttp.parsers.DataQueue

        @rtype : None
        """
        request = aiohttp.Request(self.transport, message.method,
                                  message.path, message.version)
        request.headers = self.get_http_headers(message)

        request.META = self.get_meta(request, self.transport)
        request.GET = self.get_get_params(request)
        request.COOKIES = self.get_cookies(request)
        request.POST = self.get_post_params(request)

        # dispatching and computing response
        response = yield from self.get_response(request)
        # force response not to keep-alive connection (for ab test, mostly)
        response.force_close()
        # attaches transport for aiohttp.HttpMessage and sends headers
        response.attach_transport(self.transport, request)
        # if response has content, sends it to client
        if response.content:
            # FIXME: other encodings?
            if isinstance(response.content, str):
                response.write(bytearray(response.content, "utf-8"))
            else:
                response.write(response.content)
        # finishes response
        response.write_eof()

    @staticmethod
    def get_meta(request, transport):
        """ Constructs META dict for request.

        @see https://docs.djangoproject.com/en/dev/ref/request-response/#django.http.HttpRequest.META

        @param request: http request object
        @type request: aiohttp.Request
        @param transport: transport object
        @type transport: asyncio.transports.Transport

        @rtype: dict
        @return request metadata dictionary
        """
        meta = dict()
        for key, value in request.headers.items():
            meta_key = key.upper().replace('-', '_')
            meta[meta_key] = value
        meta['REMOTE_ADDR'], meta['REMOTE_PORT'] = transport.get_extra_info(
            "peername", (None, None))
        return meta

    @staticmethod
    def get_cookies(request):
        cookie_header = request.headers.get('Cookie')
        cookies = SimpleCookie(cookie_header)
        return dict((k, c.value) for k, c in cookies.items())

    @staticmethod
    def get_get_params(request):
        """ Constructs GET dict for request.

        @see https://docs.djangoproject.com/en/dev/ref/request-response/#django.http.HttpRequest.GET

        @param request: http request object
        @type request: aiohttp.Request

        @rtype: dict
        @return request metadata dictionary
        """
        get = dict()
        path, qs = parse.splitquery(request.path)
        query = parse.parse_qsl(qs)
        for key, value in query:
            if key in get:
                prev_value = get[key]
                if type(prev_value) is not list:
                    get[key] = [prev_value]
                get[key].append(value)
            else:
                get[key] = value
        return get

    @staticmethod
    def get_post_params(request):
        # FIXME: implement
        return {}


class ChildProcess:
    """ Worker process for http server."""

    def __init__(self, up_read, down_write, args, sock):
        self.up_read = up_read
        self.down_write = down_write
        self.args = args
        self.sock = sock

    def protocol_factory(self):
        return HttpServer(debug=True, keep_alive=75)

    def start(self):
        # start server
        self.loop = loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        def stop():
            self.loop.stop()
            os._exit(0)
        loop.add_signal_handler(signal.SIGINT, stop)

        f = loop.create_server(self.protocol_factory, sock=self.sock)
        srv = loop.run_until_complete(f)
        x = srv.sockets[0]
        print('Starting srv worker process {} on {}'.format(
            os.getpid(), x.getsockname()))

        # heartbeat
        asyncio.async(self.heartbeat())

        asyncio.get_event_loop().run_forever()
        os._exit(0)

    @asyncio.coroutine
    def heartbeat(self):
        # setup pipes
        read_transport, read_proto = yield from self.loop.connect_read_pipe(
            aiohttp.StreamProtocol, os.fdopen(self.up_read, 'rb'))
        write_transport, _ = yield from self.loop.connect_write_pipe(
            aiohttp.StreamProtocol, os.fdopen(self.down_write, 'wb'))

        reader = read_proto.set_parser(websocket.WebSocketParser)
        writer = websocket.WebSocketWriter(write_transport)

        while True:
            try:
                msg = yield from reader.read()
            except aiohttp.EofStream:
                print('Superviser is dead, {} stopping...'.format(os.getpid()))
                self.loop.stop()
                break

            if msg.tp == websocket.MSG_PING:
                writer.pong()
            elif msg.tp == websocket.MSG_CLOSE:
                break

        read_transport.close()
        write_transport.close()


class Worker:
    """ Worker controller for superviser.

    Starts child process and establishes communication with it.
    """

    _started = False

    def __init__(self, loop, args, sock):
        self.loop = loop
        self.args = args
        self.sock = sock
        self.start()

    def start(self):
        assert not self._started
        self._started = True

        up_read, up_write = os.pipe()
        down_read, down_write = os.pipe()
        args, sock = self.args, self.sock

        pid = os.fork()
        if pid:
            # parent
            os.close(up_read)
            os.close(down_write)
            asyncio.async(self.connect(pid, up_write, down_read))
        else:
            # child
            os.close(up_write)
            os.close(down_read)

            # cleanup after fork
            asyncio.set_event_loop(None)

            # setup process
            process = ChildProcess(up_read, down_write, args, sock)
            process.start()

    @asyncio.coroutine
    def heartbeat(self, writer):
        delay = self.args.heartbeat or 15
        force_kill = bool(self.args.heartbeat)
        while True:
            yield from asyncio.sleep(delay)

            if (time.monotonic() - self.ping) < delay * 2:
                writer.ping()
            else:
                print('Worker process {} became unresponsive'.format(
                    self.pid))
                if force_kill:
                    print("Restarting process: {}".format(self.pid))
                    self.kill()
                    self.start()
                return

    @asyncio.coroutine
    def chat(self, reader):
        while True:
            try:
                msg = yield from reader.read()
            except aiohttp.EofStream:
                print('Restart unresponsive worker process: {}'.format(
                    self.pid))
                self.kill()
                self.start()
                return

            if msg.tp == websocket.MSG_PONG:
                self.ping = time.monotonic()

    @asyncio.coroutine
    def connect(self, pid, up_write, down_read):
        # setup pipes
        read_transport, proto = yield from self.loop.connect_read_pipe(
            aiohttp.StreamProtocol, os.fdopen(down_read, 'rb'))
        write_transport, _ = yield from self.loop.connect_write_pipe(
            aiohttp.StreamProtocol, os.fdopen(up_write, 'wb'))

        # websocket protocol
        reader = proto.set_parser(websocket.WebSocketParser)
        writer = websocket.WebSocketWriter(write_transport)

        # store info
        self.pid = pid
        self.ping = time.monotonic()
        self.rtransport = read_transport
        self.wtransport = write_transport
        self.chat_task = asyncio.Task(self.chat(reader))
        self.heartbeat_task = asyncio.Task(self.heartbeat(writer))

    def kill(self):
        self._started = False
        self.chat_task.cancel()
        self.heartbeat_task.cancel()
        self.rtransport.close()
        self.wtransport.close()
        os.kill(self.pid, signal.SIGTERM)


class Superviser:
    """ Master process for http server."""

    def __init__(self, args):
        self.loop = asyncio.get_event_loop()
        self.args = args
        self.workers = []
        self.pidfile = os.path.join(os.getcwd(), self.args.pidfile)

    def start(self):
        # bind socket
        sock = self.sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.args.host, self.args.port))
        sock.listen(1024)
        sock.setblocking(False)
        self.prefork()

        # start processes
        for idx in range(self.args.workers):
            self.workers.append(Worker(self.loop, self.args, sock))

        self.loop.add_signal_handler(signal.SIGINT, lambda: self.loop.stop())
        self.loop.add_signal_handler(signal.SIGTERM, lambda: self.loop.stop())
        self.loop.run_forever()
        if not self.args.no_daemon:
            self.delpid()

    def prefork(self):
        if not self.args.no_daemon:
            self.daemonize()

    def daemonize(self):
        """
        Deamonize, do double-fork magic.
        """
        try:
            pid = os.fork()
            if pid > 0:
                # Exit first parent.
                sys.exit(0)
        except OSError as e:
            message = "Fork #1 failed: {}\n".format(e)
            sys.stderr.write(message)
            sys.exit(1)

        # Decouple from parent environment.
        os.chdir("/")
        os.setsid()
        os.umask(0)

        # Do second fork.
        try:
            pid = os.fork()
            if pid > 0:
                # Exit from second parent.
                sys.exit(0)
        except OSError as e:
            message = "Fork #2 failed: {}\n".format(e)
            sys.stderr.write(message)
            sys.exit(1)

        # Open pidfile.
        pid = str(os.getpid())
        pidfile = open(self.pidfile, 'w+')
        
        # Redirect standard file descriptors.
        sys.stdout.flush()
        sys.stderr.flush()

        # FIXME: what if normal stdout redirect is needed?
        si = open('/dev/null', 'r')
        so = open('/dev/null', 'a+')
        se = open('/dev/null', 'a+')
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

        pidfile.write("{}\n".format(pid))
        pidfile.close()

        # Register a function to clean up.
        atexit.register(self.delpid)

    def delpid(self):
        f = open('/tmp/atexit.txt', 'w')
        f.write(self.pidfile)
        f.close()
        os.remove(self.pidfile)


