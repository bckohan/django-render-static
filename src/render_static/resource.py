"""
Convenience function for accessing packaged resource like so:

    .. code-block::

        resource('package.module', 'resource.file')
"""

import contextlib
import types
from importlib.resources import as_file, files
from typing import Optional, Union

__all__ = ["resource"]


def resource(package: Union[str, types.ModuleType], filename: str) -> str:
    """
    Open a packaged resource as a file.

    :param package: the package as either an imported module, or a string
    :param filename: the filename of the resource to include.
    :return: New instance of :class:`_Resource`.
    """
    return _Resource(package, filename)


class _Resource(str):  # noqa: WPS600
    """
    Wrap an included package resource as a str.
    Resource includes may also be wrapped as Optional and record if the
    package was found or not.
    """

    module_not_found = False
    package: str
    filename: str

    # If resources are located in archives, importlib will create temporary
    # files to access them contained within contexts
    file_manager: Optional[contextlib.ExitStack] = None

    def __new__(
        cls,
        package: Union[str, types.ModuleType],
        filename: str,
    ) -> "_Resource":
        # the type ignores workaround a known mypy issue
        # https://github.com/python/mypy/issues/1021
        try:
            ref = files(package) / filename
        except ModuleNotFoundError:
            rsrc = super().__new__(cls, f"{package}: {filename}")
            rsrc.module_not_found = True
            return rsrc

        file_manager = contextlib.ExitStack()
        rsrc = super().__new__(
            cls,
            file_manager.enter_context(as_file(ref)),
        )
        rsrc.file_manager = file_manager
        return rsrc

    def __init__(
        self,
        package: Union[str, types.ModuleType],
        filename: str,
    ) -> None:
        super().__init__()
        if isinstance(package, types.ModuleType):
            self.package = package.__name__
        else:
            self.package = package
        self.filename = filename

    def __del__(self):
        if self.file_manager:
            self.file_manager.close()
