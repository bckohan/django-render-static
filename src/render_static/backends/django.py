"""
Extensions of the standard Django template backends that add a few more
configuration parameters and functionality necessary for the static engine.
These backends should be used instead of the standard backends!
"""

from typing import Dict, Generator, List

from django.template import Template, TemplateDoesNotExist
from django.template.backends.django import DjangoTemplates

from render_static.loaders.django import SearchableLoader
from render_static.loaders.mixins import BatchLoaderMixin

from .base import StaticEngine

__all__ = ["StaticDjangoTemplates"]


class StaticDjangoTemplates(StaticEngine, DjangoTemplates):
    """
    Extend the standard :class:`django.template.backends.django.DjangoTemplates`
    backend to add options and change the default loaders.

    By default this backend will search for templates in application
    directories named ``static_templates``. The ``app_dir`` option is added to
    the standard options to allow users to override this location.
    """

    _app_dirname: str = "static_templates"

    @property
    def app_dirname(self) -> str:
        return self._app_dirname

    def __init__(self, params: Dict) -> None:
        """
        :param params: The parameters as passed into the :setting:`STATIC_TEMPLATES`
            configuration for this backend.
        """
        params = params.copy()
        options = params.pop("OPTIONS").copy()
        loaders = options.get("loaders", None)
        options.setdefault("builtins", ["render_static.templatetags.render_static"])
        self._app_dirname = options.pop("app_dir", self.app_dirname)
        if loaders is None:
            loaders = ["render_static.loaders.StaticFilesystemLoader"]
            if params.get("APP_DIRS", False):
                loaders += ["render_static.loaders.StaticAppDirectoriesLoader"]
                # base class with throw if this isn't present, it must be false
                params["APP_DIRS"] = False
            options["loaders"] = loaders
        params["OPTIONS"] = options
        super().__init__(params)
        setattr(self.engine, "app_dirname", self.app_dirname)

    def select_templates(
        self, selector: str, first_loader: bool = False, first_preference: bool = False
    ) -> List[str]:
        """
        Resolves a template selector into a list of template names from the
        loaders configured on this backend engine.

        :param selector: The template selector
        :param first_loader: If True, return only the set of template names
            from the first loader that matches any part of the selector. By
            default (False) any template name that matches the selector from
            any loader will be returned.
        :param first_preference: If true, return only the templates that match
            the first preference for each loader. When combined with
            first_loader will return only the first preference(s) of the first
            loader. Preferences are loader specific and documented on the
            loader.
        :return: The list of resolved template names
        """
        template_names = set()
        for loader in self.engine.template_loaders:
            try:
                if isinstance(loader, BatchLoaderMixin):
                    for templates in loader.select_templates(selector):
                        for tmpl in templates:
                            template_names.add(tmpl)
                        if templates and first_preference:
                            break
                else:
                    loader.get_template(selector)
                    template_names.add(selector)
                if first_loader and template_names:
                    return list(template_names)
            except TemplateDoesNotExist:
                continue
        if template_names:
            return list(template_names)
        raise TemplateDoesNotExist(
            f"Template selector {selector} did not resolve to any template names."
        )

    def search_templates(
        self, prefix: str, first_loader: bool = False
    ) -> Generator[Template, None, None]:
        """
        Resolves a partial template selector into a list of template names from the
        loaders configured on this backend engine.

        :param prefix: The template prefix to search for
        :param first_loader: Search only the first loader
        :return: The list of resolved template names
        """
        for loader in self.engine.template_loaders[: 1 if first_loader else None]:
            if isinstance(loader, SearchableLoader):
                yield from loader.search(prefix)
