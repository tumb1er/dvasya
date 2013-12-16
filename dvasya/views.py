# coding: utf-8

# $Id: $

# Django-style class-based views
#
# partially ported from django
#
# @see https://docs.djangoproject.com/en/dev/topics/class-based-views/


from functools import update_wrapper
import asyncio
from dvasya.response import HttpResponseNotAllowed, HttpResponse


class View(object):
    """
    Intentionally simple parent class for all views. Only implements
    dispatch-by-method and simple sanity checking.
    """
    __inited__ = False

    http_method_names = ['get', 'post', 'put', 'delete', 'head', 'options', 'trace']

    def __init__(self, **kwargs):
        """
        Constructor. Called in the URLconf; can contain helpful extra
        keyword arguments, and other things.
        """
        # Go through keyword arguments, and either save their values to our
        # instance, or raise an error.
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def as_view(cls, **init_kwargs):
        """
        Main entry point for a request-response process.
        """
        # sanitize keyword arguments
        for key in init_kwargs:
            if key in cls.http_method_names:
                raise TypeError("You tried to pass in the %s method name as a "
                                "keyword argument to %s(). Don't do that."
                                % (key, cls.__name__))
            if not hasattr(cls, key):
                raise TypeError("%s() received an invalid keyword %r. as_view "
                                "only accepts arguments that are already "
                                "attributes of the class." % (cls.__name__, key))

        def view(request, *args, **kwargs):
            self = cls(**init_kwargs)
            if hasattr(self, 'get') and not hasattr(self, 'head'):
                self.head = self.get
            self.request = request
            self.args = args
            self.kwargs = kwargs
            return self.dispatch(request, *args, **kwargs)

        # take name and docstring from class
        update_wrapper(view, cls, updated=())

        # and possible attributes set by decorators
        # like csrf_exempt from dispatch
        update_wrapper(view, cls.dispatch, assigned=())
        return view

    @asyncio.coroutine
    def dispatch(self, request, *args, **kwargs):
        """ Asynchronous request dispatcher.

        Calls class initializer if necessary and dispatches request
        to a corresponding handler by HTTP method name.
        """
        # Try to dispatch to the right method; if a method doesn't exist,
        # defer to the error handler. Also defer to the error handler if the
        # request method isn't on the approved list.
        self.request = request
        self.args = args
        self.kwargs = kwargs
        if request.method.lower() in self.http_method_names:
            handler = getattr(self, request.method.lower(),
                              self.http_method_not_allowed)
        else:
            handler = self.http_method_not_allowed
        result = handler(request, *args, **kwargs)
        if asyncio.tasks.iscoroutine(result):
            result = yield from result
        return result

    def http_method_not_allowed(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(self._allowed_methods())

    def options(self, request, *args, **kwargs):
        """
        Handles responding to requests for the OPTIONS HTTP verb.
        """
        response = HttpResponse()
        response.add_header('Allow', ', '.join(self._allowed_methods()))
        response.add_header('Content-Length', '0')
        return response

    def _allowed_methods(self):
        return [m.upper() for m in self.http_method_names if hasattr(self, m)]
