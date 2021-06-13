"""
Utilities for loading contexts from multiple types of sources including json files, python files,
pickle files either as files on disk, or as packaged resources contained within installed python
packages.
"""

import json
import pickle
import re
from pathlib import Path
from typing import Callable, Dict, Optional, Sequence, Tuple, Union

from django.utils.module_loading import import_string
from render_static.exceptions import InvalidContext

try:
    from yaml import FullLoader
    from yaml import load as yaml_load
except ImportError:  # pragma: no cover
    def yaml_load(*args, **kwargs):  # type: ignore
        """
        YAML is an optional dependency - lazy fail if its use is attempted without it being
        present on the python path.
        """
        raise ImportError('Install PyYAML to load contexts from YAML files.')
    FullLoader = None  # type: ignore

__all__ = ['resolve_context']

_import_regex = re.compile(r'^[\w]+([.][\w]+)*$')


def resolve_context(context: Optional[Union[Dict, str, Path, Callable]]) -> Dict:
    """
    Resolve the context specifier into a context dictionary. Context specifier may be a packaged
    resource, a path-like object or a string path to a json file, a pickled dictionary or a python
    file on disk. The context specifier may itself be a dictionary context.

    .. note::
        Render static should never be part of operational execution flows, so its ok if it takes a
        little extra time to resolve things for convenience.

    :param context: The context specifier
    :return: The dictionary context the specifier resolved to
    :raises InvalidContext: if there is a failure to produce a dictionary from the context specifier
    """
    if context is None:
        return {}
    if callable(context):
        context = context()
    if isinstance(context, dict):
        return context
    if getattr(context, 'module_not_found', False):
        raise InvalidContext('Unable to locate resource context!')
    context = str(context)
    for try_load, can_load in _loader_try_order(context):
        try:
            ctx = try_load(context, can_load)
            if ctx:
                return ctx
        except Exception as err:
            raise InvalidContext(f'Unable to load context from {context}!') from err
    raise InvalidContext(f"Unable to resolve context '{context}' to a dictionary type.")


def _from_json(file_path: str, throw: bool = True) -> Optional[Dict]:
    """
    Attempt to load context as a json file.
    :param file_path: The path to the json file
    :param throw: If true, let any exceptions propagate out
    :return: A dictionary or None if the context was not a json file.
    """
    try:
        with open(file_path, 'r') as ctx_f:
            return json.load(ctx_f)
    except Exception as err:  # pylint: disable=W0703
        if throw:
            raise err
    return None


def _from_yaml(file_path: str, throw: bool = True) -> Optional[Dict]:
    """
    Attempt to load context as a YAML file.
    :param file_path: The path to the yaml file
    :param throw: If true, let any exceptions propagate out
    :return: A dictionary or None if the context was not a yaml file.
    """
    try:
        with open(file_path, 'r') as ctx_f:
            return yaml_load(ctx_f, Loader=FullLoader)
    except Exception as err:  # pylint: disable=W0703
        if throw:
            raise err
    return None


def _from_pickle(file_path: str, throw: bool = True) -> Optional[Dict]:
    """
    Attempt to load context as from a pickled dictionary.
    :param file_path: The path to the pickled file
    :param throw: If true, let any exceptions propagate out
    :return: A dictionary or None if the context was not a pickled dictionary.
    """
    try:
        with open(file_path, 'rb') as ctx_f:
            ctx = pickle.load(ctx_f)
            if isinstance(ctx, dict):
                return ctx
    except Exception as err:  # pylint: disable=W0703
        if throw:
            raise err
    return None


def _from_python(file_path: str, throw: bool = True) -> Optional[Dict]:
    """
    Attempt to load context as from a pickled dictionary.

    :param file_path: The path to the pickled file
    :param throw: If true, let any exceptions propagate out
    :return: A dictionary or None if the context was not a pickled dictionary.
    """
    ctx: dict = {}
    try:
        with open(file_path, 'rb') as ctx_f:
            compiled_code = compile(ctx_f.read(), file_path, 'exec')
            exec(compiled_code, {}, ctx)  # pylint: disable=W0122
            return ctx
    except Exception as err:  # pylint: disable=W0703
        if throw:
            raise err
    return None


def _from_import(import_path: str, throw: bool = True) -> Optional[Dict]:
    """
    Attempt to load context as from an import string.

    :param file_path: The path to the pickled file
    :param throw: If true, let any exceptions propagate out
    :return: A dictionary or None if the context was not a pickled dictionary.
    """
    try:
        context = import_string(import_path)
        if callable(context):
            context = context()
        if isinstance(context, dict):
            return context
    except Exception as err:  # pylint: disable=W0703
        if throw:
            raise err
    return None


loaders = [
    (lambda ctx: ctx.lower().endswith('json'), _from_json),
    (lambda ctx: ctx.lower().endswith('yaml'), _from_yaml),
    (lambda ctx: ctx.lower().endswith('pickle'), _from_pickle),
    (lambda ctx: ctx.lower().endswith('py'), _from_python),
    (lambda ctx: bool(_import_regex.match(ctx)), _from_import)
]


def _loader_try_order(ctx: str) -> Sequence[Tuple[Callable[[str, bool], Optional[Dict]], bool]]:
    """
    Prioritize the loaders in order of most likely to succeed first based on the context
    string.

    :param ctx: string context, could be file path or import
    :return: List of loaders to try in order, each element of the list is a 2-tuple where the first
        element is the loader and the second is a boolean set to true if this loader was flagged as
        a priority, or false if it is a backup
    """
    priority = []
    backup = []
    for loader in loaders:
        can_load: Callable[[str], bool] = loader[0]
        if can_load(ctx):
            priority.append((loader[1], True))
        else:
            backup.append((loader[1], False))
    return priority + backup
