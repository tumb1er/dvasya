# coding: utf-8

# $Id: $

# HttpResponse class.
#
# Combines aiohttp.protocol.HttpResponse interface
# with a small part of Django HttpResponse interface
#
# @see https://docs.djangoproject.com/en/dev/ref/request-response/
from collections import deque
import json

from wsgiref.handlers import format_date_time
from aiohttp.server import RESPONSES
from aiohttp.web import Response
import sys
import dvasya
from dvasya.conf import settings


class JSONResponse(Response):
    """ Special HTTPResponse class that dumps data to json format."""

    def __init__(self, *, data=None, status=None, reason=None, headers=None):
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


class HttpResponseNotFound(Response):
    """ Not Found response class.

    If DEBUG, and url resolver was not able to find resource,
    writes last visited urlconf dump.
    """
    status_code = 404

    def __init__(self, no_match_error=None):
        if not settings.DEBUG:
            content = ''
        elif no_match_error:
            content = ("<h2>No match for path</h2>"
                      "<h4>{}</h4>"
                      "<h3>URLConf</h3>".format(no_match_error.args[0]))
            content += '<br/>'.join(str(p) for p in no_match_error.args[1])
        else:
            content = "<h2>Not found</h2>"
        super().__init__(status=self.status_code, text=content)

