# coding: utf-8

# $Id: $
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