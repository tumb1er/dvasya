# coding: utf-8

# $Id: $
import asyncio
import os

import django
from aiohttp.log import web_logger
from aiohttp import web


os.environ.setdefault("DVASYA_SETTINGS_MODULE", 'testapp.settings')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", 'testapp.settings')

django.setup()

from dvasya.contrib.django import DjangoCompatUrlResolver


class DvasyaApplication(web.Application):
    def __init__(self, *, logger=web_logger, loop=None, router=None,
                 handler_factory=web.RequestHandlerFactory, **kwargs):
        router = DjangoCompatUrlResolver()
        super().__init__(logger=logger, loop=loop, router=router,
                         handler_factory=handler_factory, **kwargs)


app = DvasyaApplication()


loop = asyncio.get_event_loop()
f = loop.create_server(app.make_handler(), '0.0.0.0', 8080)
srv = loop.run_until_complete(f)
print('serving on', srv.sockets[0].getsockname())
try:
    loop.run_forever()
except KeyboardInterrupt:
    pass