# coding: utf-8

# $Id: $
import re
from tempfile import NamedTemporaryFile
from urllib.parse import parse_qsl
import aiohttp
import asyncio
from aiohttp.web import Request
from dvasya.conf import settings
from dvasya.utils import qsl_to_dict


class LazyPost:


    def __init__(self):
        self.data = None

    def __get__(self, instance, owner):
        if self.data is None:
            raise asyncio.InvalidStateError("http body not parsed yet")
        return self.data

    def __set__(self, instance, value):
        self.data = value


class DvasyaRequest(aiohttp.Request):
    max_memory_body = 10

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__payload = None
        self.body = b''

    @property
    def payload(self) -> aiohttp.streams.DataQueue:
        return self.__payload

    @payload.setter
    def payload(self, value: aiohttp.streams.DataQueue):
        self.__payload = value

    def create_parser(self):
        content_type = self.headers['CONTENT-TYPE'] or ''
        if content_type.startswith('multipart/form-data'):
            _, boundary_field = content_type.split('; ')
            boundary = boundary_field.split('=')[1]
            return MultipartBodyParser(self.__payload, boundary)
        elif content_type.startswith('application/x-www-form-urlencoded'):
            return FormUrlEncodedBodyMemoryParser(self.__payload)
        else:
            return RawBodyFileParser(self.__payload)

    def parse_payload(self, parser=None):
        parser = parser or self.create_parser()
        data, files = yield from parser.parse_payload(self)
        self.POST = data
        self.FILES = files
        return (data, files)

    POST = LazyPost()
    FILES = LazyPost()

    @property
    def DATA(self):
        return self.body

    def _close_request_fields(self, attr):
        try:
            fields = getattr(self, attr)
            if isinstance(fields, dict):
                for v in fields.values():
                    if hasattr(v, 'file'):
                        v.close()
        except asyncio.InvalidStateError:
            pass

    def close(self):
        self._close_request_fields('POST')
        self._close_request_fields('FILES')


class FormUrlEncodedBodyMemoryParser:

    def __init__(self, payload):
        self.payload = payload
        self.__data = {}
        self.__files = {}

    @asyncio.coroutine
    def parse_payload(self, request):
        request.body = bytearray()
        chunks = 0
        while True:
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
        return header.lower().strip(), {}
    ctype, tail = header.split(';', 1)
    options = options or {}
    for match in _re_option.finditer(tail):
        key = match.group(1).lower()
        value = header_unquote(match.group(2), key == 'filename')
        options[key] = value
    return ctype, options


class MultipartBodyParser:
    header_len = 300
    data_buffer_size = 100000
    temp_dir = settings.FILE_UPLOAD_TEMP_DIR

    def __init__(self, payload, boundary):
        self.payload = payload
        self.boundary = bytes('--' + boundary, encoding='utf-8')
        self.boundary_len = len(self.boundary)
        self.buffer = aiohttp.parsers.StreamParser()
        self.__data = {}
        self.__files = {}

    def parse_payload(self, request):
        request.body = None
        while True:
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

    def process_field_data(self, data):
        if not self.filename:
            self.__data.setdefault(self.field_name, b'')
            self.__data[self.field_name] += data
        else:
            self.__files.setdefault(self.field_name, NamedTemporaryFile(dir=self.temp_dir))
            self.__files[self.field_name].write(data)

    def __call__(self, out, input):
        yield from input.readuntil(self.boundary, limit=self.boundary_len)
        while True:
            yield from input.readuntil(b'\r\n', limit=2)

            while True:
                header_line = yield from input.readuntil(b'\r\n', limit=self.header_len)
                if header_line == b'\r\n':
                    break
                self.parse_header_line(header_line)
            while True:
                try:
                    data = yield from input.readuntil(self.boundary, limit=self.boundary_len + self.data_buffer_size)
                except ValueError:
                    data = yield from input.read(self.data_buffer_size)
                    self.process_field_data(data)
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

    def __getattr__(self, item):
        try:
            return getattr(self.__request, item)
        except AttributeError:
            return super().__getattribute__(item)

    @property
    def COOKIES(self):
        return self.__request.cookies