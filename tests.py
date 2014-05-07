# coding: utf-8

# $Id: $
import copy
import json
import os
from aiohttp.protocol import HttpMessage
from unittest import mock

os.environ.setdefault("DVASYA_SETTINGS_MODULE", 'testapp.settings')

from dvasya.response import HttpResponse
from dvasya.test_utils import DvasyaTestCase

from testapp.views import patched_function_view


class UrlResolverTestCase(DvasyaTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.__expected = {
            "request":
                {"POST": {},
                 "GET": {},
                 "DATA": None,
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

    @property
    def expected(self):
        return copy.copy(self.__expected)

    def assertFunctionViewOK(self, expected, result, view_patcher):
        self.assertTrue(view_patcher.called)
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

    @mock.patch('testapp.views.patched_function_view',
                side_effect=patched_function_view)
    def testFunctionView(self, view_patcher):
        url = "/function/"
        result = self.client.get(url)
        expected = self.expected
        self.assertFunctionViewOK(expected, result, view_patcher)

    @mock.patch('testapp.views.patched_function_view',
                side_effect=patched_function_view)
    def testReverseWithQuery(self, view_patcher):
        url = "/function/?arg1=val1"
        result = self.client.get(url)
        expected = self.expected
        expected['request']['GET'] = {"arg1": 'val1'}
        self.assertFunctionViewOK(expected, result, view_patcher)

    @mock.patch('testapp.views.patched_function_view',
                side_effect=patched_function_view)
    def testReverseWithEOLRegex(self, view_patcher):
        url = "/function/other/"
        result = self.client.get(url)
        self.assertNoMatch(result)

    @mock.patch('testapp.views.patched_function_view',
                side_effect=patched_function_view)
    def testSimpleIncluded(self, view_patcher):
        url = "/include/test_include/"
        result = self.client.get(url)
        expected = self.expected
        self.assertFunctionViewOK(expected, result, view_patcher)

    @mock.patch('testapp.views.patched_function_view',
                side_effect=patched_function_view)
    def testIncludedArgsKwargs(self, view_patcher):
        url = "/include/test_args/123/kw1_val/"
        result = self.client.get(url)
        expected = self.expected
        expected['args'] = ['123']
        expected['kwargs'] = {'kwarg': 'kw1_val'}
        self.assertFunctionViewOK(expected, result, view_patcher)


class DvasyaServerTestCase(DvasyaTestCase):

    def testSimpleGet404(self):
        result = self.client.get('/')
        self.assertNoMatch(result)

    def testSimplePost404(self):
        result = self.client.post('/', data={'a': 1})
        self.assertNoMatch(result)
