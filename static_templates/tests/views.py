from django.http import JsonResponse
from django.views import View


class TestView(View):

    def get(self, request, *args, **kwargs):
        return JsonResponse({
            'request': request.path,
            'args': list(args),
            'kwargs': {**kwargs}
        })
