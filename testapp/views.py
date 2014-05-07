# coding: utf-8

# $Id: $
import shutil
import asyncio
from dvasya.response import HttpResponse
from dvasya.views import View


class DefaultView(View):
    """ And example of simple class-based view."""
    def get(self, request, *args, **kwargs):
        body = u"<h1>{} {} HTTP/{}.{}</h1>".format(
            request.method,
            request.path,
            request.version[0],
            request.version[1]
        )
        return HttpResponse(body, 200)


def dump_args_view(request, *args, **kwargs):
    body = u"<h3>Arguments: {}</h3><h3>Keywords: {}</h3>".format(args, kwargs)
    return HttpResponse(body, 200)


class TestView(View):
    def get(self, request, *args, **kwargs):
        agent = request.headers.get('user-agent', '')
        return HttpResponse("<H2>Agent: {}</H2>".format(agent))

    @asyncio.coroutine
    def post(self, request, *args, **kwargs):
        post = request.POST
        files = request.FILES
        return HttpResponse("<H2>POST: </H2>\n{}\n<H2>FILES: </H2>\n{}\n".format(post, files))

    def process_payload(self):
        if int(self.request.headers['Content-Length']) > 10000000:
            self.request.transport.close()
        return super().process_payload()

