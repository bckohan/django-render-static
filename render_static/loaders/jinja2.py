"""
Subclass the Jinja2 loaders. It is recommended that even for loaders that are simple empty
subclasses of the Jinja2 loaders, that these static redefinitions be used for static template
engines insteead. If in the future, changes to these loaders need to be made to keep code working
with renderstatic that will be transparent to users.

https://jinja.palletsprojects.com/en/3.0.x/api/#loaders
"""
from render_static.loaders.mixins import BatchLoaderMixin

try:
    from jinja2.loaders import (
        ChoiceLoader,
        DictLoader,
        FileSystemLoader,
        FunctionLoader,
        ModuleLoader,
        PackageLoader,
        PrefixLoader,
    )
except ImportError:  # pragma: no cover
    class Jinja2DependencyNeeded:  # pylint: disable=R0903
        """
        Jinja2 is an optional dependency - lazy fail if its use is attempted without it being
        present on the python path.
        """
        def __init__(self, *args, **kwargs):
            raise ImportError(
                'To use the Jinja2 backend you must install the Jinja2 python package.'
            )
    ChoiceLoader = Jinja2DependencyNeeded  # type: ignore
    DictLoader = Jinja2DependencyNeeded  # type: ignore
    FileSystemLoader = Jinja2DependencyNeeded  # type: ignore
    FunctionLoader = Jinja2DependencyNeeded  # type: ignore
    ModuleLoader = Jinja2DependencyNeeded  # type: ignore
    PackageLoader = Jinja2DependencyNeeded  # type: ignore
    PrefixLoader = Jinja2DependencyNeeded  # type: ignore

__all__ = [
    'StaticFileSystemLoader',
    'StaticFileSystemBatchLoader',
    'StaticPackageLoader',
    'StaticPrefixLoader',
    'StaticFunctionLoader',
    'StaticDictLoader',
    'StaticChoiceLoader',
    'StaticModuleLoader'
]


class StaticFileSystemLoader(FileSystemLoader):
    """
    https://jinja.palletsprojects.com/en/3.0.x/api/#jinja2.FileSystemLoader
    """


class StaticFileSystemBatchLoader(FileSystemLoader, BatchLoaderMixin):
    """
    This loader extends the basic StaticFileSystemLoader to work with batch selectors. Use this
    loader if you want to be able to use wildcards to load Jinja2 templates.

    .. note::
        This is the default loader used for the Jinja2 backend if no loader is specified.
    """

    def get_dirs(self):
        return self.searchpath


class StaticPackageLoader(PackageLoader):
    """
    https://jinja.palletsprojects.com/en/3.0.x/api/#jinja2.PackageLoader
    """


class StaticPrefixLoader(PrefixLoader):
    """
    https://jinja.palletsprojects.com/en/3.0.x/api/#jinja2.PrefixLoader
    """


class StaticFunctionLoader(FunctionLoader):
    """
    https://jinja.palletsprojects.com/en/3.0.x/api/#jinja2.FunctionLoader
    """


class StaticDictLoader(DictLoader):
    """
    https://jinja.palletsprojects.com/en/3.0.x/api/#jinja2.DictLoader
    """


class StaticChoiceLoader(ChoiceLoader):
    """
    https://jinja.palletsprojects.com/en/3.0.x/api/#jinja2.ChoiceLoader
    """


class StaticModuleLoader(ModuleLoader):
    """
    https://jinja.palletsprojects.com/en/3.0.x/api/#jinja2.ModuleLoader
    """
