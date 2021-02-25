"""
Provide wrappers for the standard template loaders to adapt them for use by the static engine.
These loaders should be used instead of the standard ones, even though some are just renamed.
This will allow app user code to be updated transparently if these loaders need to be
adapted to work with Django Static Templates in the future.
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
from render_static.origin import AppOrigin

__all__ = ['StaticFilesystemLoader', 'StaticAppDirectoriesLoader', 'StaticLocMemLoader']


class StaticFilesystemLoader(FilesystemLoader):
    """
    Simple extension of ``django.template.loaders.filesystem.Loader``
    """


class StaticLocMemLoader(LocMemLoader):
    """
    Simple extension of ``django.template.loaders.locmem.Loader``
    """


class StaticAppDirectoriesLoader(AppDirLoader):
    """
    Extension of ``django.template.loaders.app_directories.Loader``

    Searches application directories based on the engine's configured app directory name.
    This loader extends the standard AppDirLoader to provide an extended Origin type that contains
    the AppConfig of the app where the template was found. This information may be used later to
    determine where the template should be rendered to disk.
    """

    def get_dirs(self) -> Tuple[Tuple[Path, AppConfig], ...]:
        """
        Fetch the directories
        :return:
        """
        template_dirs = [
            (Path(app_config.path) / self.engine.app_dirname, app_config)
            for app_config in apps.get_app_configs()
            if app_config.path and (Path(app_config.path) / self.engine.app_dirname).is_dir()
        ]
        return tuple(template_dirs)

    def get_template_sources(self, template_name: str) -> Generator[AppOrigin, None, None]:
        """
        Yield the origins of all the templates from apps that match the given template name.

        :param template_name: The name of the template to resolve
        :return: Yielded AppOrigins for the found templates.
        """
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
