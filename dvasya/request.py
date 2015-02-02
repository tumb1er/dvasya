# coding: utf-8

# $Id: $

from aiohttp.web import Request


class DvasyaRequestProxy(object):

    def __init__(self, request: Request):
        self.__request = request
        self.POST = {}
        self.FILES = {}
        self._meta = None

    def __getattr__(self, item):
        try:
            return getattr(self.__request, item)
        except AttributeError:
            return super().__getattribute__(item)

    @property
    def META(self):
        if self._meta:
            return self._meta
        transport = self.__request.transport
        remote_addr, remote_port = transport.get_extra_info("peername")
        self._meta = {
            'REMOTE_ADDR': remote_addr,
            "REMOTE_PORT": remote_port
        }
        for k, v in self.__request.headers.items():
            if '_' in k:
                continue
            key = k.upper().replace('-', '_')
            self._meta[key] = v
        return self._meta

    @property
    def COOKIES(self):
        return self.__request.cookies
