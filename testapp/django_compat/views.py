# coding: utf-8

# $Id: $
from rest_framework.response import Response
from rest_framework.views import APIView


class SampleView(APIView):
    def get(self, request, *args, **kwargs):
        return Response({"ok": True})