# coding: utf-8

# $Id: $
from inspect import isgenerator

from dvasya.response import HttpResponse


class GenericViewMixin:
    """ Прокси-миксин для django.views.generic.View

    Реализует преобразование django.http.HttpResponse в
    dvasya.response.HttpResponse, для дальнейшего использования в асинхронном
    http-сервере.
    """

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if isgenerator(response):
            response = yield from response
        if not isinstance(response, HttpResponse):
            dvasya_response = HttpResponse(content=response.content,
                                           status=response.status_code,
                                           content_type=response['Content-Type'])
            for header, value in response._headers.values():
                if header == "Content-Type":
                    continue
                dvasya_response.add_header(header, value)
            response = dvasya_response

        return response