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
import os
import signal
import socket
import time
import sys
import atexit
import asyncio

import aiohttp.server
from aiohttp import websocket, web
from dvasya.logging import getLogger
from dvasya.middleware import load_middlewares
from dvasya.urls import load_resolver


class ChildProcess:
    """ Worker process for http server."""
    logger = getLogger('dvasya.worker')

    middlewares = load_middlewares()

    resolver_class = load_resolver()

    def __init__(self, up_read, down_write, args, sock):
        self.up_read = up_read
        self.down_write = down_write
        self.args = args
        self.sock = sock

    @property
    def protocol_factory(self):
        app = web.Application(router=self.resolver_class(),
                              loop=self.loop,
                              middlewares=self.middlewares,
                              logger=self.logger)
        return app.make_handler(access_log=getLogger('dvasya.request'))

    def before_loop(self):
        # heartbeat
        asyncio.async(self.heartbeat())

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
        self.logger.info('Starting srv worker process {} on {}'.format(
            os.getpid(), x.getsockname()))

        self.before_loop()

        asyncio.get_event_loop().run_forever()
        os._exit(0)

    @asyncio.coroutine
    def heartbeat(self):
        # setup pipes
        read_transport, read_proto = yield from self.loop.connect_read_pipe(
            aiohttp.StreamProtocol, os.fdopen(self.up_read, 'rb'))
        write_transport, _ = yield from self.loop.connect_write_pipe(
            aiohttp.StreamProtocol, os.fdopen(self.down_write, 'wb'))

        reader = read_proto.reader.set_parser(websocket.WebSocketParser)
        writer = websocket.WebSocketWriter(write_transport)

        while True:
            try:
                msg = yield from reader.read()
            except aiohttp.EofStream:
                self.logger.error(
                    'Supervisor is dead, {} stopping...'.format(os.getpid()))
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
    child_kill_signal = signal.SIGKILL
    child_process_class = ChildProcess
    logger = getLogger('dvasya.worker')

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
            process = self.child_process_class(up_read, down_write, args, sock)
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
                self.logger.error(
                    'Worker process {} became unresponsive'.format(
                        self.pid))
                if force_kill:
                    self.logger.info("Restarting process: {}".format(self.pid))
                    self.kill()
                    self.start()
                return

    @asyncio.coroutine
    def chat(self, reader):
        while True:
            try:
                msg = yield from reader.read()
            except aiohttp.EofStream:
                self.logger.info(
                    'Restart unresponsive worker process: {}'.format(
                        self.pid))
                self.kill()
                self.start()
                return

            if msg.tp == websocket.MSG_PONG:
                self.ping = time.monotonic()

    @asyncio.coroutine
    def connect(self, pid, up_write, down_read):
        self.logger.info("connecting to pid %s" % pid)
        # setup pipes
        read_transport, proto = yield from self.loop.connect_read_pipe(
            aiohttp.StreamProtocol, os.fdopen(down_read, 'rb'))
        write_transport, _ = yield from self.loop.connect_write_pipe(
            aiohttp.StreamProtocol, os.fdopen(up_write, 'wb'))
        # websocket protocol
        reader = proto.reader.set_parser(websocket.WebSocketParser)
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
        os.kill(self.pid, self.child_kill_signal)


class Supervisor:
    """ Master process for http server."""
    worker_class = Worker
    logger = getLogger('dvasya.supervisor')
    _terminating = False

    def __init__(self, args):
        self.args = args
        self.workers = []
        self.pidfile = os.path.join(os.getcwd(), self.args.pidfile)

    def open_socket(self):
        # bind socket
        sock = self.sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.args.host, self.args.port))
        sock.listen(1024)
        sock.setblocking(False)
        return sock

    def add_signal_handlers(self):
        self.loop.add_signal_handler(signal.SIGINT, self.stop)
        self.loop.add_signal_handler(signal.SIGTERM, self.stop)
        self.loop.add_signal_handler(signal.SIGCHLD, self.waitpid)

    @asyncio.coroutine
    def wait_for_children(self):
        while self.workers:
            self.logger.debug("waiting for children")
            yield from asyncio.sleep(1, loop=self.loop)
        self.loop.stop()

    def stop(self):
        self.logger.info("stopping workers...")
        self._terminating = True
        for worker in self.workers:
            self.logger.debug("kill %s " % worker.pid)
            worker.kill()
        asyncio.Task(self.wait_for_children())

    def start(self):
        sock = self.open_socket()
        self.prefork()
        self.logger.info("starting workers...")
        # start processes
        for idx in range(self.args.workers):
            self.workers.append(self.worker_class(self.loop, self.args, sock))

        self.add_signal_handlers()
        self.loop.run_forever()
        if not self.args.no_daemon:
            self.delpid()

    def waitpid(self):
        child = True
        while child:
            try:
                child, exitcode = os.waitpid(-1, os.P_NOWAIT)
                if child:
                    self.logger.info(
                        "Child process %s exited with return code %s"
                        % (child, exitcode))
                    if self._terminating:
                        self.remove_worker(child)
                    else:
                        self.restart_worker(child)
            except:
                break

    def remove_worker(self, pid):
        worker = None
        for worker in self.workers:
            if worker.pid == pid:
                break
        if not worker:
            self.logger.error("unregistered worker found, exiting")
            self.loop.stop()
            return
        self.logger.debug("removing worker %s" % pid)
        self.workers.remove(worker)

    def restart_worker(self, pid):
        worker = None
        for worker in self.workers:
            if worker.pid == pid:
                break
        if not worker:
            self.logger.error("unregistered worker found, exiting")
            self.loop.stop()
            return
        self.logger.debug("restarting worker %s" % pid)
        try:
            worker.kill()
        except Exception as err:
            self.logger.exception(
                "Error while restarting worker (%s)" % err,
                extra={"worker_pid": pid},
            )
        worker.start()

    def prefork(self):
        if not self.args.no_daemon:
            self.daemonize()
        self.loop = asyncio.get_event_loop()

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

        si = open('/dev/null', 'r')
        os.dup2(si.fileno(), sys.stdin.fileno())

        if not self.args.stderr:
            so = open('/dev/null', 'a+')
            se = open('/dev/null', 'a+')
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
        try:
            os.remove(self.pidfile)
        except IOError:
            pass
