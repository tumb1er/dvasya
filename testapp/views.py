# coding: utf-8

# $Id: $
from dvasya.response import HttpResponse


def default_view(request):
    body = u"<h1>{} {} HTTP/{}.{}</h1>".format(
        request.method,
        request.path,
        request.version[0],
        request.version[1]
    )
    return HttpResponse(body, 200)


def args(request, *args, **kwargs):
    body = u"<h2>A: {}</h2><h2>KW: {}</h2>".format(args, kwargs)
    return HttpResponse(body, 200)
