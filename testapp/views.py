# coding: utf-8

# $Id: $
import json
import asyncio
from aiohttp.web import Response
from dvasya.views import View
from dvasya.response import JSONResponse


class DefaultView(View):
    """ And example of simple class-based view."""
    def get(self, request, *args, **kwargs):
        body = u"<h1>{} {} HTTP/{}.{}</h1>".format(
            request.method,
            request.path,
            request.version[0],
            request.version[1]
        )
        return Response(body=body, status=200)


def dump_args_view(request, *args, **kwargs):
    body = u"<h3>Arguments: {}</h3><h3>Keywords: {}</h3>".format(args, kwargs)
    return Response(body=body, status=200)


def function_view(*args, **kwargs):
    return patched_function_view(*args, **kwargs)


def json_view(request, *args, **kwargs):
    return JSONResponse(status=request.GET.get('status', 200),
                        data={"ok": True})


def cookie_view(request, *args, **kwargs):
    new_cookies = {}
    seen_cookies = {}
    for key, value in request.GET.items():
        if key.startswith('cookie_'):
            new_cookies[key[7:]] = value
    for key, value in request.COOKIES.items():
        seen_cookies[key] = value
    response = JSONResponse(status=200, data=seen_cookies)
    for key, value in new_cookies.items():
        response.set_cookie(key, value)
    return response


def mvdict_to_listdict(mvdict):
    result = {}
    for k, v in mvdict.items():
        if k in result:
            value = result[k]
            if not isinstance(value, list):
                value = result[k] = [value]
            value.append(v)
        else:
            result[k] = v
    return result


def dump_params(request, *args, **kwargs):
    data = yield from request.post()
    if not data:
        data = yield from request.read()

    if hasattr(data, 'file'):
        f = data.file
        data = f.read()

    if isinstance(data, bytes):
        data = data.decode('utf-8')

    post = {}
    files = {}
    for k, v in request.POST.items():
        if isinstance(v, str):
            post[k] = v
        elif isinstance(v, bytes):
            post[k] = v.decode("utf-8")
        else:
            raise ValueError(v)
    for k, v in request.FILES.items():
        files[k] = v.file.read().decode("utf-8")
    meta = {}
    for k, v in request.META.items():
        meta[k] = v

    result = {
        'request': {
            'GET': mvdict_to_listdict(request.GET),
            'POST': post,
            'FILES': files,
            'META': meta,
            'DATA': data if not post and not files else None
        },
        'args': args,
        'kwargs': kwargs
    }
    body = json.dumps(result)
    response = Response(text=body, status=200, content_type="application/json")
    return response


@asyncio.coroutine
def patched_function_view(request, *args, **kwargs):
    return dump_params(request, *args, **kwargs)


class ClassBasedView(View):

    def any_method(self, request, *args, **kwargs):
        return dump_params(request, *args, **kwargs)

    get = any_method
    head = any_method
    delete = any_method
    post = any_method
    put = any_method

class TestView(View):
    def get(self, request, *args, **kwargs):
        agent = request.headers.get('user-agent', '')
        return Response(text="<H2>Agent: {}</H2>".format(agent))

    @asyncio.coroutine
    def post(self, request, *args, **kwargs):
        post = request.POST
        files = request.FILES
        return Response(text="<H2>POST: </H2>\n{}\n<H2>FILES: </H2>\n{}\n".format(post, files))
