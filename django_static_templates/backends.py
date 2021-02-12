from django.template.backends.django import DjangoTemplates
from django.template.backends.jinja2 import Jinja2
from django_static_templates.origin import AppOrigin
from django.template.backends.jinja2 import Template
from pathlib import Path
from os.path import normpath
from django.apps import apps
from django.apps.config import AppConfig
from typing import (
    Dict,
    List,
    Tuple
)


__all__ = ['StaticDjangoTemplates', 'StaticJinja2Templates']


class StaticDjangoTemplates(DjangoTemplates):

    app_dirname = 'static_templates'

    def __init__(self, params: Dict) -> None:
        params = params.copy()
        options = params.pop('OPTIONS').copy()
        loaders = options.get('loaders', None)
        self.app_dirname = options.pop('app_dir', self.app_dirname)
        if loaders is None:
            loaders = ['django_static_templates.loaders.StaticFilesystemLoader']
            if params.get('APP_DIRS', False):
                loaders += ['django_static_templates.loaders.StaticAppDirectoriesLoader']
                params['APP_DIRS'] = False  # base class with throw if this isn't present - and it must be false
            options['loaders'] = loaders
        params['OPTIONS'] = options
        super().__init__(params)
        self.engine.app_dirname = self.app_dirname


class StaticJinja2Templates(Jinja2):

    app_dirname = 'static_jinja2'
    app_directories: List[Tuple[Path, AppConfig]] = []

    def __init__(self, params: Dict) -> None:
        params = params.copy()
        options = params.pop('OPTIONS').copy()
        self.app_dirname = options.pop('app_dir', self.app_dirname)
        params['OPTIONS'] = options

        self.app_directories = [
            (Path(app_config.path) / self.app_dirname, app_config)
            for app_config in apps.get_app_configs()
            if app_config.path and (Path(app_config.path) / self.app_dirname).is_dir()
        ]

        super().__init__(params)

    def get_template(self, template_name: str) -> Template:
        """
        We override the Jinja2 get_template method so we can monkey patch in the AppConfig of the origin if this
        template was from an app directory. This information is used later down the line when deciding where to
        write rendered templates. For the django template backend we modified the loaders but modifying the Jinja2
        loaders would be much more invasive.
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
