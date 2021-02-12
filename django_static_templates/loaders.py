"""
Wrapper for loading templates from "templates" directories in INSTALLED_APPS
packages.
"""

from pathlib import Path
from typing import Generator, Tuple

from django.apps import apps
from django.apps.config import AppConfig
from django.core.exceptions import SuspiciousFileOperation
from django.template.loaders.app_directories import Loader as AppDirLoader
from django.template.loaders.filesystem import Loader as FilesystemLoader
from django.template.loaders.locmem import Loader as LocMemLoader
from django.utils._os import safe_join
from django_static_templates.origin import AppOrigin

__all__ = ['StaticFilesystemLoader', 'StaticAppDirectoriesLoader', 'StaticLocMemLoader']


class StaticFilesystemLoader(FilesystemLoader):
    pass


class StaticAppDirectoriesLoader(AppDirLoader):

    def get_dirs(self) -> Tuple[Tuple[Path, AppConfig], ...]:
        template_dirs = [
            (Path(app_config.path) / self.engine.app_dirname, app_config)
            for app_config in apps.get_app_configs()
            if app_config.path and (Path(app_config.path) / self.engine.app_dirname).is_dir()
        ]
        return tuple(template_dirs)

    def get_template_sources(self, template_name) -> Generator[AppOrigin, None, None]:
        for template_dir, app_config in self.get_dirs():
            try:
                name = safe_join(template_dir, template_name)
            except SuspiciousFileOperation:
                # The joined path was located outside of this template_dir
                # (it might be inside another one, so this isn't fatal).
                continue

            yield AppOrigin(
                name=name,
                template_name=template_name,
                loader=self,
                app=app_config
            )


class StaticLocMemLoader(LocMemLoader):
    pass

