"""
Some loader utilities shared between both Jinja2 and Django loaders.
"""

import os
import typing as t
from pathlib import Path


def walk(path: t.Union[str, Path]) -> t.Generator[Path, None, None]:
    """
    Walk the directory tree and yield sub directories and files.

    :param path: The path to walk
    :param prefix: A path prefix to add onto the returned paths
    :yield: The sub directories and files at and below the given path,
        the paths will be relative to the given path
    """
    for root, dirs, files in os.walk(path):
        prefix = Path(root).relative_to(path)
        for directory in dirs:
            yield prefix / directory if prefix else Path(directory)
        for file in files:
            yield prefix / file if prefix else Path(file)
