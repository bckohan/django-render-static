from django.http import JsonResponse
from django.views import View


class TestView(View):

    def get(self, request, *args, **kwargs):
        query = {}
        for key, val in request.GET.items():
            if len(request.GET.getlist(key)) > 1:
                query[key] = request.GET.getlist(key)
            else:
                query[key] = val
        return JsonResponse({
            'request': request.path,
            'args': list(args),
            'kwargs': {**kwargs},
            'query': query
        })
