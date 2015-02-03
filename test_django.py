# coding: utf-8

# $Id: $
from dvasya.test_utils import DvasyaTestCase


class DjangoTestCase(DvasyaTestCase):
    root_urlconf = 'testapp.django_compat.urls'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'testapp.settings')
        from dvasya.contrib.django import DjangoRequestProxyMiddleware

        cls.middlewares = [DjangoRequestProxyMiddleware.factory]

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
