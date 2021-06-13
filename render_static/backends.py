"""
Extensions of the standard Django template backends that add a few more configuration
parameters and functionality necessary for the static engine. These backends should be
used instead of the standard backends!
"""
from os.path import normpath
from pathlib import Path
from typing import Dict, List, Tuple

from django.apps import apps
from django.apps.config import AppConfig
from django.template.backends.django import (
    DjangoTemplates,
    TemplateDoesNotExist,
)
from django.template.backends.jinja2 import Jinja2, Template
from render_static.loaders.jinja2 import StaticFileSystemBatchLoader
from render_static.origin import AppOrigin

__all__ = ['StaticDjangoTemplates', 'StaticJinja2Templates']


class StaticDjangoTemplates(DjangoTemplates):
    """
    Extend the standard ``django.template.backends.django.DjangoTemplates`` backend to add options
    and change the default loaders.

    By default this backend will search for templates in application directories named
    ``static_templates``. The ``app_dir`` option is added to the standard options to allow users to
    override this location.

    :param params: The parameters as passed into the ``STATIC_TEMPLATES`` configuration for this
        backend.
    """

    app_dirname = 'static_templates'

    def __init__(self, params: Dict) -> None:
        params = params.copy()
        options = params.pop('OPTIONS').copy()
        loaders = options.get('loaders', None)
        self.app_dirname = options.pop('app_dir', self.app_dirname)
        if loaders is None:
            loaders = ['render_static.loaders.StaticFilesystemLoader']
            if params.get('APP_DIRS', False):
                loaders += ['render_static.loaders.StaticAppDirectoriesLoader']
                # base class with throw if this isn't present - and it must be false
                params['APP_DIRS'] = False
            options['loaders'] = loaders
        params['OPTIONS'] = options
        super().__init__(params)
        self.engine.app_dirname = self.app_dirname

    def select_templates(
            self,
            selector: str,
            first_loader: bool = False,
            first_preference: bool = False
    ) -> List[str]:
        """
        Resolves a template selector into a list of template names from the loaders configured on
        this backend engine.

        :param selector: The template selector
        :param first_loader: If True, return only the set of template names from the first loader
            that matches any part of the selector. By default (False) any template name that matches
            the selector from any loader will be returned.
        :param first_preference: If true, return only the templates that match the first preference
            for each loader. When combined with first_loader will return only the first
            preference(s) of the first loader. Preferences are loader specific and documented on the
            loader.
        :return: The list of resolved template names
        """
        template_names = set()
        for loader in self.engine.template_loaders:
            try:
                if callable(getattr(loader, 'select_templates', None)):
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
            f'Template selector {selector} did not resolve to any template names.'
        )


class StaticJinja2Templates(Jinja2):
    """
    Extend the standard ``django.template.backends.jinja2.Jinja2`` backend to add options. Unlike
    with the standard backend, the loaders used for this backend remain unchanged.

    By default this backend will search for templates in application directories named
    ``static_jinja2``. The ``app_dir`` option is added to the standard option to allow users to
    override this location.

    :param params: The parameters as passed into the ``STATIC_TEMPLATES`` configuration for this
        backend.
    """

    app_dirname = 'static_jinja2'
    app_directories: List[Tuple[Path, AppConfig]] = []

    def __init__(self, params: Dict) -> None:
        params = params.copy()
        self.dirs = list(params.get('DIRS', []))
        self.app_dirs = params.get('APP_DIRS', False)
        options = params.pop('OPTIONS').copy()
        self.app_dirname = options.pop('app_dir', self.app_dirname)

        if 'loader' not in options:
            options['loader'] = StaticFileSystemBatchLoader(self.template_dirs)

        params['OPTIONS'] = options

        self.app_directories = [
            (Path(app_config.path) / self.app_dirname, app_config)
            for app_config in apps.get_app_configs()
            if app_config.path and (Path(app_config.path) / self.app_dirname).is_dir()
        ]

        super().__init__(params)

    def get_template(self, template_name: str) -> Template:
        """
        We override the Jinja2 get_template method so we can monkey patch in the AppConfig of the
        origin if this template was from an app directory. This information is used later down the
        line when deciding where to write rendered templates. For the django template backend we
        modified the loaders but modifying the Jinja2 loaders would be much more invasive.
        """
        template = super().get_template(template_name)

        for app_dir, app in self.app_directories:
            if normpath(template.origin.name).startswith(normpath(app_dir)):
                template.origin = AppOrigin(
                    name=template.origin.name,
                    template_name=template.origin.template_name,
                    app=app
                )
                break
        return template

    def select_templates(
            self,
            selector: str,
            first_loader: bool = False,
            first_preference: bool = False
    ) -> List[str]:
        """
        Resolves a template selector into a list of template names from the loader configured on
        this backend engine.

        :param selector: The template selector
        :param first_loader: This is ignored for the Jinja2 engine. The Jinja2 engine only has one
            loader.
        :param first_preference: If true, return only the templates that match the first preference
            for the loader. Preferences are loader specific and documented on the loader.
        :return: The list of resolved template names
        """

        template_names = set()
        if callable(getattr(self.env.loader, 'select_templates', None)):
            for templates in self.env.loader.select_templates(selector):
                if templates:
                    for tmpl in templates:
                        template_names.add(tmpl)
                    if first_preference:
                        break
        else:
            self.get_template(selector)
            template_names.add(selector)
        if first_loader and template_names:
            return list(template_names)

        if template_names:
            return list(template_names)
        raise TemplateDoesNotExist(
            f'Template selector {selector} did not resolve to any template names.'
        )
