# coding: utf-8

# $Id: $

# django-style url resolver
#
# @see https://docs.djangoproject.com/en/dev/topics/http/urls/
#
# supports root-level urls and include() function

import asyncio
import re
import aiohttp
import aiohttp.web
from aiohttp.abc import AbstractRouter, AbstractMatchInfo
from dvasya.conf import settings
from dvasya.response import HttpResponseNotFound
from dvasya.utils import import_object


# noinspection PyUnusedLocal
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

    @property
    def regex(self):
        return self._regex

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
    # noinspection PyUnusedLocal
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
        pattern_list = [self._regex + ' ' + p.pattern
                        for p in self.local_patterns]
        raise HttpResponseNotFound(path=path, patterns=pattern_list)


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


class RegexMatchInfo(AbstractMatchInfo):
    """"""

    def __init__(self, handler, args, kwargs):
        self._handler = handler
        self._args = args
        self._kwargs = kwargs

    @asyncio.coroutine
    def _wrapper(self, request):
        return self._handler(request, *self._args, **self._kwargs)

    @property
    def handler(self):
        return self._wrapper

    @property
    def route(self, *args, **kwargs):
        # FIXME: fast stub to prevent ABCMeta TypeError
        raise NotImplementedError()

    @property
    def expect_handler(self):
        return aiohttp.web_urldispatcher._defaultExpectHandler

    @property
    def http_exception(self):
        return None


class UrlResolver(AbstractRouter):
    """ Global URL resolver class."""
    resolver = None
    match_info_class = RegexMatchInfo

    @classmethod
    def autodiscover(cls):
        if not cls.resolver:
            cls.resolver = UrlResolver()
        return cls.resolver

    def __init__(self, root_urlconf=None):
        urlconf_module = root_urlconf or settings.ROOT_URLCONF
        urlconf = __import__(urlconf_module, fromlist='urlpatterns')
        self.patterns = self.compile_patterns(urlconf.urlpatterns)

    @asyncio.coroutine
    def resolve(self, request: aiohttp.web.Request) -> RegexMatchInfo:
        """Dispatches a request to a view

        @param request: http request object
        @type request: aiohttp.web.Request

        @return: aiohttp url match info
        @rtype: RegexMatchInfo
        """

        request_path = request.path.lstrip('/')
        request_path = request_path.split('?', 1)[0]
        for pattern in self.patterns:
            match = self.match_pattern(pattern, request_path)
            if not match:
                continue
            return self.match_info_class(*match)
        raise HttpResponseNotFound(path=request_path,
                                   patterns=[p.regex for p in self.patterns])

    @staticmethod
    def compile_patterns(urlpatterns):
        """Compiles url patterns

        @type urlpatterns: tuple | list
        @param urlpatterns: list of url patterns

        @return: list of compiled url patterns
        @rtype: list
        """
        result = []
        for pattern in urlpatterns:
            result.append(pattern)
        return result

    def match_pattern(self, pattern, request_path):
        return pattern.resolve(request_path)


def load_resolver():
    return import_object(settings.URL_RESOLVER_CLASS)
