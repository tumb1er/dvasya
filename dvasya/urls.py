# coding: utf-8

# $Id: $
import asyncio
import re
from dvasya.conf import settings


def patterns(prefix, *pattern_list):
    # prefix not supported
    # don't know what for it could be applied :)
    return pattern_list


def include(patterns_or_path):
    if isinstance(patterns_or_path, str):
        module, attr = patterns_or_path.rsplit('.', 1)
        print(module, attr)
        module = __import__(module, fromlist=[attr])
        patterns_or_path = getattr(module, attr)
    return patterns_or_path


class UrlPattern:
    def __init__(self, pattern, view_func, name=None):
        self.pattern = pattern
        self.view_func = view_func
        self.name = name
        self.rx = None

    def compile(self):
        self.rx = re.compile(self.pattern)

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
        return self.view_func, args, kwargs, self.name


class LocalUrlPattern(UrlPattern):
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
        raise NoMatch(path, [self.pattern + ' ' + p.pattern
                             for p in self.local_patterns])


def url(rx, view_or_patterns, name=None):
    if isinstance(view_or_patterns, (tuple, list)):
        return LocalUrlPattern(rx, view_or_patterns)
    return UrlPattern(rx, view_or_patterns, name=name)


class NoMatch(Exception):
    pass


class UrlResolver:
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
        """

        @rtype : L{HttpResponse}
        """
        request_path = request.path.lstrip('/')
        for pattern in self.patterns:
            match = pattern.resolve(request_path)
            if match:
                return self.call_view(request, *match, transport=transport)
        raise NoMatch(request_path, [p.pattern for p in self.patterns])

    @asyncio.coroutine
    def call_view(self, request, view, args, kwargs, name, transport=None):
        # FIXME: transport to class-based view
        return view(request, *args, **kwargs)

    def compile_patterns(self, urlpatterns):
        """
        @type urlpatterns: tuple | list
        @param urlpatterns: list of url patterns
        @return: list of compiled url patterns
        """
        result = []
        for url in urlpatterns:
            url.compile()
            result.append(url)
        return result
