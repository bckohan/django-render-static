"""
Provide wrappers for the standard template loaders to adapt them for use by the static engine.
These loaders should be used instead of the standard ones, even though some are just renamed.
This will allow app user code to be updated transparently if these loaders need to be
adapted to work with Django Static Templates in the future.
"""

from glob import glob
from os.path import relpath
from pathlib import Path
from typing import Generator, List, Tuple, Union

from django.apps import apps
from django.apps.config import AppConfig
from django.core.exceptions import SuspiciousFileOperation
from django.template.loaders.app_directories import Loader as AppDirLoader
from django.template.loaders.filesystem import Loader as FilesystemLoader
from django.template.loaders.filesystem import safe_join
from django.template.loaders.locmem import Loader as LocMemLoader
from render_static.loaders.mixins import BatchLoaderMixin
from render_static.origin import AppOrigin

__all__ = [
    'StaticFilesystemLoader',
    'StaticAppDirectoriesLoader',
    'StaticLocMemLoader',
    'StaticAppDirectoriesBatchLoader',
    'StaticFilesystemBatchLoader'
]


class StaticFilesystemLoader(FilesystemLoader):
    """
    Simple extension of ``django.template.loaders.filesystem.Loader``
    """


class StaticFilesystemBatchLoader(StaticFilesystemLoader, BatchLoaderMixin):
    """
    A loader that enables glob pattern selectors to load batches of templates from the file system.

    Yields batches of template names in order of preference, where preference is defined by the
    order directories are listed in.
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

    def get_template_sources(
            self,
            template_name: str
    ) -> Generator[Union[AppOrigin, List[AppOrigin]], None, None]:
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


class StaticAppDirectoriesBatchLoader(StaticAppDirectoriesLoader):
    """
    A loader that enables glob pattern selectors to load batches of templates from app directories.

    Yields batches of template names in order of preference, where preference is defined by the
    precedence of Django apps.
    """
    def select_templates(self, selector: str) -> Generator[List[str], None, None]:
        """
        Yields template names matching the selector pattern.

        :param selector: A glob pattern, or file name
        """
        for template_dir, app_config in self.get_dirs():  # pylint: disable=W0612
            try:
                pattern = safe_join(template_dir, selector)
            except SuspiciousFileOperation:
                # The joined path was located outside of this template_dir
                # (it might be inside another one, so this isn't fatal).
                continue

            yield [relpath(str(file), str(template_dir)) for file in glob(pattern, recursive=True)]
