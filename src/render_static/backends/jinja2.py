from os.path import normpath
from pathlib import Path
from typing import Dict, Generator, List, Tuple

from django.apps import apps
from django.apps.config import AppConfig
from django.template import TemplateDoesNotExist
from django.template.backends.jinja2 import Jinja2, Template
from jinja2 import Environment

from render_static.loaders.jinja2 import SearchableLoader as SearchableJinja2Loader
from render_static.loaders.jinja2 import StaticFileSystemBatchLoader
from render_static.loaders.mixins import BatchLoaderMixin
from render_static.origin import AppOrigin
from render_static.templatetags import render_static

from .base import StaticEngine

__all__ = ["StaticJinja2Templates"]


def default_env(**options):
    """
    The default Jinja2 backend environment. This environment adds the tags
    and filters from render_static.

    :param options:
    :return:
    """
    env = Environment(**options)
    env.globals.update(render_static.register.filters)
    env.globals.update(
        {
            name: getattr(tag, "__wrapped__", tag)
            for name, tag in render_static.register.tags.items()
        }
    )
    return env


class StaticJinja2Templates(StaticEngine, Jinja2):
    """
    Extend the standard :class:`django.template.backends.jinja2.Jinja2` backend
    to add options. Unlike with the standard backend, the loaders used for
    this backend remain unchanged.

    By default this backend will search for templates in application
    directories named ``static_jinja2``. The ``app_dir`` option is added to
    the standard option to allow users to override this location.
    """

    _app_dirname = "static_jinja2"

    @property
    def app_dirname(self) -> str:
        return self._app_dirname

    app_directories: List[Tuple[Path, AppConfig]] = []

    def __init__(self, params: Dict) -> None:
        """
        :param params: The parameters as passed into the :setting:`STATIC_TEMPLATES`
            configuration for this backend.
        """
        params = params.copy()
        self.dirs = list(params.get("DIRS", []))
        self.app_dirs = params.get("APP_DIRS", False)
        options = params.pop("OPTIONS").copy()
        options.setdefault("environment", "render_static.backends.jinja2.default_env")
        self._app_dirname = options.pop("app_dir", self.app_dirname)

        if "loader" not in options:
            options["loader"] = StaticFileSystemBatchLoader(self.template_dirs)

        params["OPTIONS"] = options

        self.app_directories = [
            (Path(app_config.path) / self.app_dirname, app_config)
            for app_config in apps.get_app_configs()
            if app_config.path and (Path(app_config.path) / self.app_dirname).is_dir()
        ]

        super().__init__(params)

    def get_template(self, template_name: str) -> Template:
        """
        We override the Jinja2 get_template method so we can monkey patch
        in the AppConfig of the origin if this template was from an app
        directory. This information is used later down the line when
        deciding where to write rendered templates. For the django template
        backend we modified the loaders but modifying the Jinja2 loaders
        would be much more invasive.
        """
        template = super().get_template(template_name)

        for app_dir, app in self.app_directories:
            if normpath(template.origin.name).startswith(normpath(app_dir)):
                template.origin = AppOrigin(  # type: ignore
                    name=template.origin.name,
                    template_name=template.origin.template_name,
                    app=app,
                )
                break
        return template

    def select_templates(
        self,
        selector: str,
        first_loader: bool = False,
        first_preference: bool = False,
    ) -> List[str]:
        """
        Resolves a template selector into a list of template names from
        the loader configured on this backend engine.

        :param selector: The template selector
        :param first_loader: This is ignored for the Jinja2 engine. The
            Jinja2 engine only has one loader.
        :param first_preference: If true, return only the templates that
            match the first preference for the loader. Preferences are
            loader specific and documented on the loader.
        :return: The list of resolved template names
        """
        template_names = set()
        if isinstance(self.env.loader, BatchLoaderMixin):
            for templates in self.env.loader.select_templates(selector):
                if templates:
                    for tmpl in templates:
                        template_names.add(tmpl)
                    if first_preference:
                        break
        else:
            self.get_template(selector)
            template_names.add(selector)

        if template_names:
            return list(template_names)

        raise TemplateDoesNotExist(
            f"Template selector {selector} did not resolve to any template names."
        )

    def search_templates(  # type: ignore[override]
        self,
        prefix: str,
        first_loader: bool = False,
    ) -> Generator[Template, None, None]:
        """
        Resolves a partial template selector into a list of template names from the
        loaders configured on this backend engine.

        :param prefix: The template prefix to search for
        :param first_loader: This is ignored for the Jinja2 engine because there is
            only one loader
        :return: The list of resolved template names
        """
        if isinstance(self.env.loader, SearchableJinja2Loader):
            for tmpl in self.env.loader.search(self.env, prefix):
                yield Template(tmpl, self)
