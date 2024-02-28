"""
Subclass the Jinja2 loaders. It is recommended that even for loaders that are
simple empty subclasses of the Jinja2 loaders, that these static redefinitions
be used for static template engines insteead. If in the future, changes to
these loaders need to be made to keep code working with renderstatic that will
be transparent to users.

https://jinja.palletsprojects.com/en/3.0.x/api/#loaders
"""
from os.path import normpath
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generator,
    MutableMapping,
    Optional,
    Tuple,
)

from render_static import Jinja2DependencyNeeded
from render_static.loaders.mixins import BatchLoaderMixin

try:
    from jinja2.exceptions import TemplateNotFound
    from jinja2.loaders import (
        BaseLoader,
        ChoiceLoader,
        DictLoader,
        FileSystemLoader,
        FunctionLoader,
        ModuleLoader,
        PackageLoader,
        PrefixLoader,
    )

    if TYPE_CHECKING:  # pragma: no cover
        from jinja2 import Environment, Template

except ImportError:
    ChoiceLoader = Jinja2DependencyNeeded  # type: ignore
    DictLoader = Jinja2DependencyNeeded  # type: ignore
    FileSystemLoader = Jinja2DependencyNeeded  # type: ignore
    FunctionLoader = Jinja2DependencyNeeded  # type: ignore
    ModuleLoader = Jinja2DependencyNeeded  # type: ignore
    PackageLoader = Jinja2DependencyNeeded  # type: ignore
    PrefixLoader = Jinja2DependencyNeeded  # type: ignore
    BaseLoader = Jinja2DependencyNeeded  # type: ignore

__all__ = [
    "StaticFileSystemLoader",
    "StaticFileSystemBatchLoader",
    "StaticPackageLoader",
    "StaticPrefixLoader",
    "StaticFunctionLoader",
    "StaticDictLoader",
    "StaticChoiceLoader",
    "StaticModuleLoader",
]


class SearchableLoader(BaseLoader):
    """
    Loaders should implement this protocol to support shell tab-completion.
    """

    def search(
        self, environment: "Environment", prefix: str
    ) -> Generator["Template", None, None]:
        """
        Search for templates matching the selector pattern.

        :param selector: A glob pattern, or file name
        :yield: Yields templates matching the incomplete selector prefix
        """
        try:
            for template in self.list_templates():
                if template.startswith(prefix):
                    try:
                        yield self.load(environment, template)
                    except TemplateNotFound:  # pragma: no cover
                        continue
        except (TypeError, AttributeError):  # pragma: no cover
            pass


class StaticFileSystemLoader(
    SearchableLoader, FileSystemLoader
):  # pylint: disable=R0903
    """
    https://jinja.palletsprojects.com/en/3.0.x/api/#jinja2.FileSystemLoader

    We adapt the base loader to support loading directories as templates.
    """

    is_dir: bool = False

    def load(
        self,
        environment: "Environment",
        name: str,
        globals: Optional[  # pylint: disable=redefined-builtin
            MutableMapping[str, Any]
        ] = None,
    ) -> "Template":
        """
        Wrap load so we can tag directory templates with is_dir.
        """
        tmpl = super().load(environment, name, globals)
        setattr(tmpl, "is_dir", self.is_dir)
        return tmpl

    def get_source(
        self, environment: "Environment", template: str
    ) -> Tuple[str, str, Callable[[], bool]]:
        """
        Wrap get_source and handle the case where the template is
        a directory.
        """
        try:
            self.is_dir = False
            return super().get_source(environment, template)
        except TemplateNotFound:
            for search_path in self.searchpath:
                pth = Path(search_path) / template
                if pth.is_dir():
                    self.is_dir = True
                    # code cov bug here, ignore it
                    return ("", normpath(pth), lambda: True)
            raise


class StaticFileSystemBatchLoader(StaticFileSystemLoader, BatchLoaderMixin):
    """
    This loader extends the basic StaticFileSystemLoader to work with batch
    selectors. Use this loader if you want to be able to use wildcards to load
    Jinja2 templates.

    .. note::
        This is the default loader used for the Jinja2 backend if no loader is
        specified.
    """

    def get_dirs(self):
        return self.searchpath


class StaticPackageLoader(SearchableLoader, PackageLoader):  # pylint: disable=R0903
    """
    https://jinja.palletsprojects.com/en/3.0.x/api/#jinja2.PackageLoader
    """


class StaticPrefixLoader(SearchableLoader, PrefixLoader):  # pylint: disable=R0903
    """
    https://jinja.palletsprojects.com/en/3.0.x/api/#jinja2.PrefixLoader
    """


class StaticFunctionLoader(FunctionLoader):  # pylint: disable=R0903
    """
    https://jinja.palletsprojects.com/en/3.0.x/api/#jinja2.FunctionLoader
    """


class StaticDictLoader(SearchableLoader, DictLoader):  # pylint: disable=R0903
    """
    https://jinja.palletsprojects.com/en/3.0.x/api/#jinja2.DictLoader
    """


class StaticChoiceLoader(SearchableLoader, ChoiceLoader):  # pylint: disable=R0903
    """
    https://jinja.palletsprojects.com/en/3.0.x/api/#jinja2.ChoiceLoader
    """


class StaticModuleLoader(ModuleLoader):  # pylint: disable=R0903
    """
    https://jinja.palletsprojects.com/en/3.0.x/api/#jinja2.ModuleLoader
    """
