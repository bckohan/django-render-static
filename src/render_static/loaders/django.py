"""
Provide wrappers for the standard template loaders to adapt them for use by the
static engine. These loaders should be used instead of the standard ones, even
though some are just renamed. This will allow app user code to be updated
transparently if these loaders need to be adapted to work with Django Static
Templates in the future.
"""

from pathlib import Path
from typing import (
    Generator,
    List,
    Optional,
    Protocol,
    Tuple,
    Union,
    runtime_checkable,
)

from django.apps import apps
from django.apps.config import AppConfig
from django.core.exceptions import SuspiciousFileOperation
from django.template import Origin, Template, TemplateDoesNotExist
from django.template.loaders.app_directories import Loader as AppDirLoader
from django.template.loaders.filesystem import Loader as FilesystemLoader
from django.template.loaders.filesystem import safe_join  # type: ignore[attr-defined]
from django.template.loaders.locmem import Loader as LocMemLoader

from render_static.loaders.mixins import BatchLoaderMixin
from render_static.loaders.utils import walk
from render_static.origin import AppOrigin

__all__ = [
    "StaticFilesystemLoader",
    "StaticAppDirectoriesLoader",
    "StaticLocMemLoader",
    "StaticAppDirectoriesBatchLoader",
    "StaticFilesystemBatchLoader",
]


@runtime_checkable
class SearchableLoader(Protocol):
    """
    Loaders should implement this protocol to support shell tab-completion.
    """

    def search(self, selector: str) -> Generator[Template, None, None]:
        """
        Search for templates matching the selector pattern.

        :param selector: A glob pattern, or file name
        """
        ...  # pragma: no cover


class DirectorySupport(FilesystemLoader):
    """
    A mixin that allows directories to be templates. The templates resolved
    when this mixin is used that are directories will have an is_dir
    attribute that is set to True.
    """

    is_dir = False

    def get_template(
        self, template_name: str, skip: Optional[List[Origin]] = None
    ) -> Template:
        """
        Wrap the super class's get_template method and set our is_dir
        flag depending on if get_contents raises an IsADirectoryError.

        :param template_name: The name of the template to load
        :param skip: A container of origins to skip
        :return: The loaded template
        :raises TemplateDoesNotExist: If the template does not exist
        """
        self.is_dir = False
        template = super().get_template(template_name, skip=skip)
        setattr(template, "is_dir", self.is_dir)
        return template

    def get_contents(self, origin: Origin) -> str:
        """
        We wrap the super class's get_contents implementation and
        set the is_dir flag if the origin is a directory. This is
        alight touch approach that avoids touching any of the loader
        internals and should be robust to future changes.

        :param origin: The origin of the template to load
        :return: The contents of the template
        :raises TemplateDoesNotExist: If the template does not
            exist
        """
        try:
            return super().get_contents(origin)
        except IsADirectoryError:
            self.is_dir = True
            return ""
        except PermissionError:
            if Path(origin.name).is_dir():
                self.is_dir = True
                return ""
            raise  # pragma: no cover

    def search(self, prefix: str) -> Generator[Template, None, None]:
        """
        Return all Template objects at paths that start with the given path
        prefix.

        :param prefix: A partial template name to search for.
        :yield: All Template objects that have names that start with the prefix
        """
        prefix = str(Path(prefix)) if prefix else ""  # normalize!
        for template_dir in self.get_dirs():
            for path in walk(Path(template_dir)):
                if not str(path).startswith(prefix):
                    continue
                try:
                    yield self.get_template(str(path))
                except TemplateDoesNotExist:  # pragma: no cover
                    continue


class StaticFilesystemLoader(DirectorySupport):
    """
    Simple extension of :class:`django.template.loaders.filesystem.Loader`
    """


class StaticFilesystemBatchLoader(StaticFilesystemLoader, BatchLoaderMixin):
    """
    A loader that enables glob pattern selectors to load batches of templates
    from the file system.

    Yields batches of template names in order of preference, where preference
    is defined by the order directories are listed in.
    """


class StaticLocMemLoader(LocMemLoader):
    """
    Simple extension of :class:`django.template.loaders.locmem.Loader`
    """

    def search(self, prefix: str) -> Generator[Template, None, None]:
        """
        Search for templates matching the selector pattern.

        :param prefix: A partial template name to search for.
        :yield: All Template objects that have names that start with the prefix
        """
        for name in self.templates_dict.keys():
            if name.startswith(prefix):
                yield self.get_template(name)


class StaticAppDirectoriesLoader(DirectorySupport, AppDirLoader):
    """
    Extension of :class:`django.template.loaders.app_directories.Loader`

    Searches application directories based on the engine's configured app
    directory name. This loader extends the standard AppDirLoader to provide an
    extended Origin type that contains the AppConfig of the app where the
    template was found. This information may be used later to determine where
    the template should be rendered to disk.
    """

    def get_dirs(self) -> List[Union[str, Path]]:
        return [pth for pth, _ in self.get_app_dirs()]

    def get_app_dirs(self) -> List[Tuple[Union[str, Path], AppConfig]]:
        """
        Fetch the directories
        :return:
        """
        template_dirs = [
            (Path(app_config.path) / getattr(self.engine, "app_dirname"), app_config)
            for app_config in apps.get_app_configs()
            if (
                app_config.path
                and (
                    Path(app_config.path) / getattr(self.engine, "app_dirname")
                ).is_dir()
            )
        ]
        return template_dirs

    def get_template_sources(self, template_name: str) -> Generator[Origin, None, None]:
        """
        Yield the origins of all the templates from apps that match the given
        template name.

        :param template_name: The name of the template to resolve
        :return: Yielded AppOrigins for the found templates.
        """
        for template_dir, app_config in self.get_app_dirs():
            try:
                name = safe_join(template_dir, template_name)
            except SuspiciousFileOperation:
                # The joined path was located outside of this template_dir
                # (it might be inside another one, so this isn't fatal).
                continue

            yield AppOrigin(
                name=name, template_name=template_name, loader=self, app=app_config
            )


class StaticAppDirectoriesBatchLoader(StaticAppDirectoriesLoader, BatchLoaderMixin):
    """
    A loader that enables glob pattern selectors to load batches of templates
    from app directories.

    Yields batches of template names in order of preference, where preference
    is defined by the precedence of Django apps.
    """
