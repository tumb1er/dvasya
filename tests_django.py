# coding: utf-8

# $Id: $
import json
import os

from unittest import mock

os.environ.setdefault("DVASYA_SETTINGS_MODULE", 'testapp.settings')

from dvasya.test_utils import DvasyaTestCase  # noqa


class DjangoTestCase(DvasyaTestCase):
    root_urlconf = 'testapp.django_compat.urls'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'testapp.settings')
        import django
        # configure django>=1.7
        setup = getattr(django, 'setup', None)
        if callable(setup):
            setup()
        from dvasya.contrib import django as django_contrib

        cls.middlewares = [django_contrib.DjangoRequestProxyMiddleware.factory]
        cls.resolver_class = django_contrib.DjangoUrlResolver

    def testRequestEncoding(self):
        url = '/rest/'
        headers = {
            'Content-Type': 'text/plain; charset=cp1251'
        }
        data = {"ok": True}
        from rest_framework.response import Response

        with mock.patch('testapp.django_compat.views.SampleView.get',
                        return_value=Response(data)) as p:
            response = self.client.get(url, headers=headers)
            self.assertEqual(response.text, json.dumps(data).replace(' ', ''))
        request = p.call_args[0][0]
        self.assertEqual(request.encoding, "cp1251")

    def testDjangoRestFrameworkPost(self):
        self.skipTest("FIXME")

    def testDjango404(self):
        response = self.client.get("/nonexistent")
        self.assertEqual(response.status, 404)

    def testMeta(self):
        url = '/rest/'
        response = self.client.get(url)
        self.assertEqual(response.status, 200)
        data = json.loads(response.text)
        meta = data['request']['META']
        peername = (meta['REMOTE_ADDR'], meta['REMOTE_PORT'])
        self.assertTupleEqual(peername, self.client.peername)

    def testCaseInsensitiveHeaders(self):
        url = '/rest/'
        headers = {
            'X-Real-IP': '127.0.0.2',
            'Remote-addr': "hacked_addr"
        }
        data = {"ok": True}
        from rest_framework.response import Response
        self.maxDiff = None

        with mock.patch('testapp.django_compat.views.SampleView.get',
                        return_value=Response(data)) as p:
            response = self.client.get(url, headers=headers)
            self.assertEqual(response.text, json.dumps(data).replace(' ', ''))
        request = p.call_args[0][0]
        self.assertEqual(request.META.get('X_REAL_IP'), '127.0.0.2')
        self.assertEqual(request.META.get('REMOTE_ADDR'), '127.0.0.1')
