# coding: utf-8

# $Id: $
import os

os.environ.setdefault("DVASYA_SETTINGS_MODULE", 'testapp.settings')

from dvasya.response import HttpResponse
from dvasya.test_utils import DvasyaTestCase


class DvasyaServerTestCase(DvasyaTestCase):

    def testSimpleGet404(self):
        result = self.client.get('/')
        self.assertIsInstance(result, HttpResponse)
        self.assertEqual(result.status_code, 404)
        self.assertIn("No match for path", result.content)
        self.assertEqual(result.content_type, "text/html")
