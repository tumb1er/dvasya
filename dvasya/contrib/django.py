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
            response = HttpResponse(content=response.content,
                                    status=response.status_code,
                                    content_type=response.get('content-type'))
        return response