# coding: utf-8

# $Id: $
import re
from tempfile import NamedTemporaryFile
from urllib.parse import parse_qsl
import asyncio

import aiohttp
from aiohttp.multidict import MultiDict, MultiDictProxy
from aiohttp.web import Request, FileField

from dvasya.conf import settings
from dvasya.utils import qsl_to_dict


class FormUrlEncodedBodyMemoryParser:

    def __init__(self, payload):
        self.payload = payload
        self.__data = {}
        self.__files = {}

    @asyncio.coroutine
    def parse_payload(self, request):
        request.body = bytearray()
        chunks = 0
        while not self.payload.at_eof():
            try:
                buffer = yield from self.payload.read()
            except aiohttp.parsers.EofStream:
                break
            request.body += buffer
            chunks += 1
        self.__data = qsl_to_dict(parse_qsl(request.body.decode('utf-8')))
        return self.__data, self.__files


class RawBodyFileParser:
    temp_dir = settings.FILE_UPLOAD_TEMP_DIR

    def __init__(self, payload):
        self.payload = payload
        self.__data = {}
        self.__files = {}

    @asyncio.coroutine
    def parse_payload(self, request):
        out = NamedTemporaryFile(dir=self.temp_dir)
        chunks = 0
        loop = asyncio.get_event_loop()
        while True:
            try:
                buffer = yield from self.payload.read()
            except aiohttp.parsers.EofStream:
                break
            yield from loop.run_in_executor(None, out.write, buffer)
            chunks += 1
        out.seek(0)
        request.body = out
        return self.__data, self.__files

_special = re.escape('()<>@,;:\\"/[]?={} \t')
_re_special = re.compile('[%s]' % _special)
_qstr = '"(?:\\\\.|[^"])*"'  # Quoted string
_value = '(?:[^%s]+|%s)' % (_special, _qstr)  # Save or quoted string
_option = '(?:;|^)\s*([^%s]+)\s*=\s*(%s)' % (_special, _value)

_re_option = re.compile(_option)  # key=val part of an Content-Type like header

def header_unquote(val, filename=False):
    if val and val[0] == val[-1] == '"':
        val = val[1:-1]
        if val[1:3] == ':\\' or val[:2] == '\\\\':
            val = val.split('\\')[-1]  # fix ie6 bug: full path --> filename
        if val and val[0] == '/':
            val = val.split('/')[-1]
        return val.replace('\\\\', '\\').replace('\\"', '"')

    return val


def parse_options_header(header, options=None):
    header = header.decode('utf-8')
    if ';' not in header:
        header, value = header.strip().split(": ", 1)
        return header.lower(), value
    ctype, tail = header.split(';', 1)
    options = options or {}
    for match in _re_option.finditer(tail):
        key = match.group(1).lower()
        value = header_unquote(match.group(2), key == 'filename')
        options[key] = value
    return ctype, options


class MultipartBodyParser:
    header_len = 300
    data_buffer_size = 50000000
    temp_dir = settings.FILE_UPLOAD_TEMP_DIR

    def __init__(self, payload, boundary):
        self.payload = payload
        self.boundary = bytes('--' + boundary, encoding='utf-8')
        self.boundary_len = len(self.boundary)
        self.buffer = aiohttp.parsers.StreamParser()
        self.__data = {}
        self.__files = {}

    @asyncio.coroutine
    def parse_payload(self, request):
        request.body = None
        while not self.payload.at_eof():
            try:
                buffer = yield from self.payload.read()
                try:
                    self.buffer.feed_data(buffer)
                    if not self.buffer._parser:
                        self.buffer.set_parser(self)
                except ValueError as e:
                    print(e)
                    pass

            except aiohttp.parsers.EofStream:
                break
        for k, v in self.__files.items():
            v.file.seek(0)
        return self.__data, self.__files

    def parse_header_line(self, header_line):
        header, options = parse_options_header(header_line)
        if header.lower().startswith('content-disposition'):
            self.field_name = options.get('name')
            self.filename = options.get('filename')
        elif header.lower() == 'content-type':
            self.content_type = header

    def process_field_data(self, data):
        if not self.filename:
            self.__data.setdefault(self.field_name, b'')
            self.__data[self.field_name] += data
        else:
            field = self.__files.get(self.field_name)
            if not field:
                file = NamedTemporaryFile(dir=self.temp_dir)
                field = FileField(name=self.field_name, filename=self.filename,
                                  content_type=self.content_type, file=file)
                self.__files[self.field_name] = field
            field.file.write(data)

    def __call__(self, out, input):
        yield from input.readuntil(self.boundary, limit=self.boundary_len)
        while True:
            yield from input.readuntil(b'\r\n', limit=2)

            while True:
                header_line = yield from input.readuntil(b'\r\n',
                                                         limit=self.header_len)
                if header_line == b'\r\n':
                    break
                self.parse_header_line(header_line)
            while True:
                try:
                    data = yield from input.waituntil(
                        self.boundary,
                        limit=self.boundary_len + self.data_buffer_size)
                    yield from input.skip(len(data))
                except aiohttp.errors.LineLimitExceededParserError:
                    data = yield from input.read(self.data_buffer_size)
                    self.process_field_data(data)
                    continue
                if data[-self.boundary_len - 2:] == b'\r\n' + self.boundary:
                    data = data[:-self.boundary_len - 2]
                    self.process_field_data(data)
                    break
            try:
                yield from input.readuntil(b'--\r\n\r\n', limit=6)
                break
            except aiohttp.errors.LineLimitExceededParserError:
                continue


class DvasyaRequestProxy(object):

    def __init__(self, request: Request):
        self.__request = request
        self.POST = {}
        self.FILES = {}
        self._meta = None

    def __getattr__(self, item):
        try:
            return getattr(self.__request, item)
        except AttributeError:
            return super().__getattribute__(item)

    @property
    def META(self):
        if self._meta:
            return self._meta
        transport = self.__request.transport
        remote_addr, remote_port = transport.get_extra_info("peername")
        self._meta = {
            'REMOTE_ADDR': remote_addr,
            "REMOTE_PORT": remote_port
        }
        for k, v in self.__request.headers.items():
            if '_' in k:
                continue
            key = k.upper().replace('-', '_')
            self._meta[key] = v
        return self._meta

    @property
    def COOKIES(self):
        return self.__request.cookies

    @asyncio.coroutine
    def post(self):
        request = self.__request
        if request._post is not None:
            return request._post
        if request.method not in ('POST', 'PUT', 'PATCH'):
            request._post = MultiDictProxy(MultiDict())
            return request._post

        content_type = request.content_type
        if (content_type not in ('',
                                 'application/x-www-form-urlencoded',
                                 'multipart/form-data')):
            request._post = MultiDictProxy(MultiDict())
            return request._post
        content_type = request.headers.get('CONTENT-TYPE', '')
        parser = self.create_parser(content_type, request.content)
        self.POST, self.FILES = yield from parser.parse_payload(request)
        out = MultiDict()
        for name, field in self.POST.items():
            out.add(name, field)
        for name, field in self.FILES.items():
            field.file.seek(0)
            out.add(name, field)

        self.__request._post = MultiDictProxy(out)
        return self.__request._post


    def create_parser(self, content_type, payload):
        if content_type.startswith('multipart/form-data'):
            _, boundary_field = content_type.split('; ')
            boundary = boundary_field.split('=')[1]
            return MultipartBodyParser(payload, boundary)
        elif content_type.startswith('application/x-www-form-urlencoded'):
            return FormUrlEncodedBodyMemoryParser(payload)
        else:
            return RawBodyFileParser(payload)
