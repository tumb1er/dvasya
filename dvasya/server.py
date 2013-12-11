# coding: utf-8

# $Id: $
import os
import signal
import socket
import email.message
import time

import aiohttp.server
from aiohttp import websocket
import asyncio
from urllib import parse
from dvasya.response import HttpResponseNotFound
from dvasya.urls import UrlResolver, NoMatch


class HttpServer(aiohttp.server.ServerHttpProtocol):
    resolver = UrlResolver.autodiscover()

    @asyncio.coroutine
    def get_response(self, request):
        try:
            result = yield from self.resolver.dispatch(request, self.transport)
            return result
        except NoMatch as e:
            return HttpResponseNotFound(e)

    @asyncio.coroutine
    def handle_request(self, message, payload):
        request = aiohttp.Request(self.transport, message.method,
                                  message.path, message.version)
        headers = email.message.Message()
        for hdr, val in message.headers:
            headers.add_header(hdr, val)
        request.headers = headers
        request.META = self.get_meta(request, self.transport)
        request.GET = self.get_get_params(request)

        response = yield from self.get_response(request)
        response.force_close()
        response.attach_transport(self.transport, request)
        if response.content:
            # FIXME: other encodings?
            response.write(bytearray(response.content, "utf-8"))
        response.write_eof()

    def get_meta(self, request, transport):
        meta = dict()
        for key, value in request.headers.items():
            meta_key = key.upper().replace('-', '_')
            meta[meta_key] = value
        meta['REMOTE_ADDR'] = transport._extra['peername'][0]
        return meta

    def get_get_params(self, request):
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


class ChildProcess:

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

    def __init__(self, args):
        self.loop = asyncio.get_event_loop()
        self.args = args
        self.workers = []

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
        self.loop.run_forever()

    def prefork(self):
        # FIXME: демонизация тута
        pass

