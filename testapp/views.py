# coding: utf-8

# $Id: $
import json
import asyncio

from rest_framework.response import Response
from rest_framework.views import APIView

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

def function_view(*args, **kwargs):
    return patched_function_view(*args, **kwargs)


def dump_params(request, *args, **kwargs):
    data = yield from request.post()
    if not data:
        data = yield from request.read()
    #data = request.DATA
    if hasattr(data, 'file'):
        f = data.file
        data = f.read()
    if not isinstance(data, str) and data is not None:
        data = data.decode('utf-8')
    files = getattr(request, 'FILES', {})
    for k, v in files.items():
        if hasattr(v, 'file'):
            files[k] = v.file.read().decode('utf-8')
    post = request.POST
    for k, v in post.items():
        if not isinstance(v, str):
            post[k] = v.decode('utf-8')
    result = {
        'request': {
            'GET': request.GET,
            'POST': request.POST,
            'FILES': files,
            'META': request.META,
            'DATA': data
        },
        'args': args,
        'kwargs': kwargs
    }
    body = json.dumps(result)
    response = HttpResponse(body, 200, content_type="application/json")
    return response


@asyncio.coroutine
def patched_function_view(request, *args, **kwargs):
    yield from request.parse_payload()
    return dump_params(request, *args, **kwargs)


class ClassBasedView(View):

    def any_method(self, request, *args, **kwargs):
        return dump_params(request, *args, **kwargs)

    get = any_method
    head = any_method
    delete = any_method
    post = any_method
    patch = any_method
    put = any_method

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

class SampleView(APIView):
    def get(self, request, *args, **kwargs):
        return Response({"ok": True})