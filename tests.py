# coding: utf-8

# $Id: $
from collections import OrderedDict
import copy
import json
import os
from unittest import mock
from urllib import parse

from aiohttp.protocol import HttpMessage


os.environ.setdefault("DVASYA_SETTINGS_MODULE", 'testapp.settings')

from dvasya.response import HttpResponse
from dvasya.test_utils import DvasyaTestCase

from testapp import views


class DvasyaServerTestCaseBase(DvasyaTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.__expected = {
            "request":
                {"POST": {},
                 "GET": {},
                 "DATA": '',
                 "FILES": {},
                 "META": {
                     "USER_AGENT": HttpMessage.SERVER_SOFTWARE,
                     "CONTENT_LENGTH": "0",
                     "HOST": "localhost",
                     "CONNECTION": "keep-alive",
                     "ACCEPT": "*/*",
                     "ACCEPT_ENCODING": "gzip, deflate",
                     "REMOTE_PORT": "12345",
                     "REMOTE_ADDR": "127.0.0.1"
                 }
                },
            "args": [],
            "kwargs": {}
        }

    def setUp(self):
        super().setUp()
        self.view_patcher = mock.patch('testapp.views.dump_params',
                                       side_effect=views.dump_params)
        self.mock = self.view_patcher.start()

    def tearDown(self):
        self.view_patcher.stop()
        super().tearDown()

    @property
    def expected(self):
        return copy.deepcopy(self.__expected)

    def assertFunctionViewOK(self, expected, result):
        self.assertTrue(self.mock.called)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, "application/json")
        content = json.loads(result.content)
        for key in ('request', 'kwargs'):
            self.assertDictEqual(content[key], expected[key])
        self.assertListEqual(content['args'], expected['args'])

    def assertNoMatch(self, result):
        self.assertIsInstance(result, HttpResponse)
        self.assertEqual(result.status_code, 404)
        self.assertIn("No match for path", result.content)
        self.assertEqual(result.content_type, "text/html")


class UrlResolverTestCase(DvasyaServerTestCaseBase):
    def testFunctionView(self):
        url = "/function/"
        result = self.client.get(url)
        expected = self.expected
        self.assertFunctionViewOK(expected, result)

    def testReverseWithQuery(self):
        url = "/function/?arg1=val1"
        result = self.client.get(url)
        expected = self.expected
        expected['request']['GET'] = {"arg1": 'val1'}
        self.assertFunctionViewOK(expected, result)

    def testReverseWithEOLRegex(self):
        url = "/function/other/"
        result = self.client.get(url)
        self.assertNoMatch(result)

    def testSimpleIncluded(self):
        url = "/include/test_include/"
        result = self.client.get(url)
        expected = self.expected
        self.assertFunctionViewOK(expected, result)

    def testIncludedArgsKwargs(self):
        url = "/include/test_args_kwargs/123/kw1_val/"
        result = self.client.get(url)
        expected = self.expected
        # as in Django, args are hidden if kwargs present
        expected['args'] = []
        expected['kwargs'] = {'kwarg': 'kw1_val'}
        self.assertFunctionViewOK(expected, result)

    def testIncludedArgs(self):
        url = "/include/test_args/123/val/"
        result = self.client.get(url)
        expected = self.expected
        # as in Django, args are hidden if kwargs present
        expected['args'] = ['123', 'val']
        self.assertFunctionViewOK(expected, result)

    def testClassBasedView(self):
        url = "/class/not_used/"
        result = self.client.get(url)
        expected = self.expected
        self.assertFunctionViewOK(expected, result)


class DvasyaRequestParserTestCase(DvasyaServerTestCaseBase):
    def testSimpleGet(self):
        url = '/class/?arg1=val1&arg2=val2?&arg2=val3#hashtag'
        expected = self.expected
        expected['request']['GET'] = {
            'arg1': 'val1',
            'arg2': ['val2?', 'val3']
        }
        result = self.client.get(url)
        self.assertFunctionViewOK(expected, result)
        result = self.client.head(url)
        self.assertFunctionViewOK(expected, result)
        result = self.client.delete(url)
        self.assertFunctionViewOK(expected, result)

    def testUrlEncodedPost(self):
        url = '/function/?arg1=val1'
        data = OrderedDict((
            ('arg1', 'val1'),
            ('arg2', 'val2')
        ))
        body = parse.urlencode(data)

        expected = self.expected
        expected['request'].update({
            'GET': {'arg1': 'val1'},
            'DATA': body,
            'POST': {
                'arg1': 'val1',
                'arg2': 'val2',
            }
        })
        expected['request']['META'].update({
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'CONTENT_LENGTH': str(len(body))
        })
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        result = self.client.post(url, data=data, headers=headers)
        self.assertFunctionViewOK(expected, result)
        result = self.client.patch(url, data=data, headers=headers)
        self.assertFunctionViewOK(expected, result)
        result = self.client.put(url, data=data, headers=headers)
        self.assertFunctionViewOK(expected, result)

    def testPlainTextPost(self):
        url = '/function/?arg1=val1'
        body = "just some text"
        headers = {
            'Content-Type': 'text/plain'
        }
        expected = self.expected
        expected['request'].update({
            'GET': {'arg1': 'val1'},
            'DATA': body,
            'POST': {}
        })
        expected['request']['META'].update({
            'CONTENT_TYPE': 'text/plain',
            'CONTENT_LENGTH': str(len(body))
        })
        result = self.client.post(url, body=body, headers=headers)
        self.assertFunctionViewOK(expected, result)

    def testMultipartPost(self):
        url = '/function/?arg1=val1'
        boundary = 'Asrf456BGe4h'
        delimiter = '--%s' % boundary
        terminator = '--%s--' % boundary
        f1content = 'file_one_content\r\nwith_second_line'
        f2content = 'second_file_content'
        body = '\r\n'.join((
            delimiter,
            'Content-Disposition: form-data; name="arg1"',
            '',
            'val1',
            delimiter,
            'Content-Disposition: form-data; name="arg2"',
            '',
            'val2',
            delimiter,
            'Content-Disposition: form-data; name="f1"; filename="fn1.txt"',
            'Content-Type: text/plain',
            '',
            f1content,
            delimiter,
            'Content-Disposition: form-data; name="f2"; filename="fn2.txt"',
            'Content-Type: text/plain',
            '',
            f2content,
            terminator
        ))
        headers = {
            'Content-Type': 'multipart/form-data; boundary=%s' % boundary
        }
        expected = self.expected
        expected['request'].update({
            'GET': {'arg1': 'val1'},
            'DATA': None,
            'POST': {
                'arg1': 'val1',
                'arg2': 'val2'
            },
            'FILES': {
                'f1': f1content,
                'f2': f2content
            }
        })
        expected['request']['META'].update({
            'CONTENT_TYPE': ('multipart/form-data; boundary=%s' % boundary),
            'CONTENT_LENGTH': str(len(body))
        })
        result = self.client.post(url, body=body, headers=headers)
        self.assertFunctionViewOK(expected, result)


class TODOTestCase(DvasyaTestCase):

    def testCookieSupport(self):
        self.skipTest("FIXME")

    def test500ErrorHandling(self):
        self.skipTest("FIXME")

    def test405NotAllowed(self):
        self.skipTest("FIXME")

    def testJSONResponse(self):
        self.skipTest("FIXME")
