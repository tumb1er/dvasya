# coding: utf-8

# $Id: $

# HttpResponse class.
#
# Combines aiohttp.protocol.HttpResponse interface
# with a small part of Django HttpResponse interface
#
# @see https://docs.djangoproject.com/en/dev/ref/request-response/
import json
import traceback

from aiohttp.web import Response, HTTPInternalServerError, HTTPNotFound
from dvasya.conf import settings


class JSONResponse(Response):
    """ Special HTTPResponse class that dumps data to json format."""

    def __init__(self, *, data=None, status=200, reason=None, headers=None):
        if data and not isinstance(data, str):
            data = json.dumps(data)
        super().__init__(
            text=data,
            status=status,
            reason=reason,
            headers=headers,
            content_type="application/json")


class HttpResponseNotAllowed(Response):
    """ Method Not Allowed response class."""
    status_code = 405

    def __init__(self, permitted_methods):
        super(HttpResponseNotAllowed, self).__init__(status=self.status_code)
        self.headers['ALLOW'] = ', '.join(permitted_methods)


class HttpResponseNotFound(HTTPNotFound):
    """ Not Found response class.

    If DEBUG, and url resolver was not able to find resource,
    writes last visited urlconf dump.
    """
    status_code = 404

    def __init__(self, *, path=None, patterns=None):
        if not settings.DEBUG:
            content = ''
        else:
            content = (
                "<h2>No match for path</h2>"
                "<h4>{}</h4>"
                "<h3>URLConf</h3>".format(path))
            content += '<br/>'.join(str(p) for p in patterns)
        super().__init__(text=content, content_type="text/html")


class HttpInternalError(HTTPInternalServerError):
    def __init__(self, exc):
        if not settings.DEBUG:
            content = ''
        else:
            stack = traceback.format_exc()
            content = (
                "<h2>Internal Server Error</h2>"
                "<h4>{0}: {1}</h4>"
                "<h3>Traceback:</h3>"
                "<pre>{2}</pre>".format(exc.__class__.__name__, exc, stack))
        super().__init__(text=content, content_type="text/html")
