# coding: utf-8

# $Id: $



def default_view(request):
    status = 200
    body = u"<h1>{} {} HTTP/{}.{}</h1>".format(
        request.method,
        request.path,
        request.version[0],
        request.version[1]
    )
    return status, body


def agrs_view(request, *args, **kwargs):
    status = 200
    body = u"<h2>A: {}</h2><h2>KW: {}</h2>".format(args, kwargs)
    return status, body
