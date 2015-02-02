# coding: utf-8

# $Id: $
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework import fields
from rest_framework.generics import GenericAPIView

class TestSerializer(Serializer):
    file = fields.FileField()
    param = fields.CharField()

class SampleView(GenericAPIView):
    serializer_class = TestSerializer

    def dispatch(self, request, *args, **kwargs):
        yield from request.post()
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return Response({"ok": True})

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            return Response({"posted": True})
        else:
            return Response({"error": True})