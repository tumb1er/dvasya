# coding: utf-8

# $Id: $

# django-style url resolver
#
# @see https://docs.djangoproject.com/en/dev/topics/http/urls/
#
# supports root-level urls and include() function

import asyncio
import re
from dvasya.conf import settings
from dvasya.utils import import_object


def patterns(prefix, *pattern_list):
    """ Django compatibility method."""
    # prefix not supported
    # don't know what for it could be applied :)
    return pattern_list


def include(patterns_or_path):
    """ Returns a subtree for patterns_or_path.

    @param patterns_or_path: class path for other urlconf or list of patterns
    """
    if isinstance(patterns_or_path, str):
        patterns_or_path = import_object(patterns_or_path)
    return patterns_or_path


class UrlPattern:
    """ URL pattern matcher."""
    def __init__(self, pattern, view_func, name=None):
        self._regex = pattern
        self.view_func = view_func
        self.name = name
        self.rx = None

    def compile(self):
        self.rx = re.compile(self._regex)

    def _match(self, path):
        if self.rx is None:
            self.compile()
        match = self.rx.match(path)
        return match

    def resolve(self, path):
        match = self._match(path)
        if not match:
            return None
        kwargs = match.groupdict()
        if kwargs:
            args = ()
        else:
            args = match.groups()
        return self.view_func, args, kwargs


class LocalUrlPattern(UrlPattern):
    """ Url pattern matcher for 'include' case."""
    def __init__(self, pattern, pattern_list, name=None):
        super(LocalUrlPattern, self).__init__(pattern, None)
        self.local_patterns = pattern_list

    def compile(self):
        super(LocalUrlPattern, self).compile()
        for p in self.local_patterns:
            p.compile()

    def resolve(self, path):
        match = self._match(path)
        if not match:
            return None
        matched_part = match.group(0)
        rest_path = path[len(matched_part):]
        for pattern in self.local_patterns:
            match = pattern.resolve(rest_path)
            if match:
                return match
        raise NoMatch(path, [self._regex + ' ' + p.pattern
                             for p in self.local_patterns])


def url(rx, view_or_patterns, name=None):
    """ Constructs url pattern matcher from url definition.
    @see https://docs.djangoproject.com/en/dev/topics/http/urls/#example

    @param rx: url regular expression
    @type rx: str

    @param view_or_patterns: view function or include(...) result
    @type view_or_patterns: (function|tuple|list)

    @return pattern matcher
    @rtype UrlPattern
    """
    if isinstance(view_or_patterns, (tuple, list)):
        return LocalUrlPattern(rx, view_or_patterns)
    return UrlPattern(rx, view_or_patterns, name=name)


class NoMatch(Exception):
    """ No match found for request path."""
    pass


class UrlResolver:
    """ Global URL resolver class."""
    resolver = None

    @classmethod
    def autodiscover(cls):
        if not cls.resolver:
            cls.resolver = UrlResolver()
        return cls.resolver

    def __init__(self):
        urlconf_module = settings.ROOT_URLCONF
        urlconf = __import__(urlconf_module, fromlist='urlpatterns')
        self.patterns = self.compile_patterns(urlconf.urlpatterns)

    @asyncio.coroutine
    def dispatch(self, request, transport=None):
        """Dispatches a request to a view

        @param request: http request object
        @type request: aiohttp.HttpRequest

        @param transport: http transport for current request
        @type transport: asyncio.transports.Transport

        @return: http response
        @rtype: dvasya.response.HttpResponse
        """
        request_path = request.path.lstrip('/')
        for pattern in self.patterns:
            try:
                match = pattern.resolve(request_path)
            except:
                continue
            if not match:
                continue
            return self.call_view(request, *match, transport=transport)
        raise NoMatch(request_path, [p._regex for p in self.patterns])

    @asyncio.coroutine
    def call_view(self, request, view, args, kwargs, transport=None):
        """ Calls a view function for request."""
        # FIXME: transport to class-based view
        return view(request, *args, **kwargs)

    @staticmethod
    def compile_patterns(urlpatterns):
        """Compiles url patterns

        @type urlpatterns: tuple | list
        @param urlpatterns: list of url patterns

        @return: list of compiled url patterns
        @rtype: list
        """
        result = []
        for url in urlpatterns:
            result.append(url)
        return result
