from django.views.generic import TemplateView


class SPAIndex(TemplateView):
    template_name = "spa/index.html"

    def get_context_data(self, **kwargs):
        return {  # pragma: no cover
            **super().get_context_data(),
            "namespace": self.request.resolver_match.namespace,
        }
