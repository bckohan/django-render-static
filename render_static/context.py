"""
Utilities for loading contexts from multiple types of sources including json files, python files,
pickle files either as files on disk, or as packaged resources contained within installed python
packages.
"""

import json
import pickle
from pathlib import Path
from typing import Callable, Dict, Optional, Union

from django.utils.module_loading import import_string
from render_static.exceptions import InvalidContext

__all__ = ['resolve_context']


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
    for try_load in [_from_json, _from_import, _from_pickle, _from_python]:
        ctx = try_load(context)
        if ctx:
            return ctx
    raise InvalidContext(f"Unable to resolve context '{context}' to a dictionary type.")


def _from_json(file_path: str) -> Optional[Dict]:
    """
    Attempt to load context as a json file.
    :param file_path: The path to the json file
    :return: A dictionary or None if the context was not a json file.
    """
    try:
        with open(file_path, 'r') as ctx_f:
            return json.load(ctx_f)
    except Exception:  # pylint: disable=W0703
        pass
    return None


def _from_pickle(file_path: str) -> Optional[Dict]:
    """
    Attempt to load context as from a pickled dictionary.
    :param file_path: The path to the pickled file
    :return: A dictionary or None if the context was not a pickled dictionary.
    """
    try:
        with open(file_path, 'rb') as ctx_f:
            ctx = pickle.load(ctx_f)
            if isinstance(ctx, dict):
                return ctx
    except Exception:  # pylint: disable=W0703
        pass
    return None


def _from_python(file_path: str) -> Optional[Dict]:
    ctx: dict = {}
    try:
        with open(file_path, 'rb') as ctx_f:
            compiled_code = compile(ctx_f.read(), file_path, 'exec')
            exec(compiled_code, {}, ctx)  # pylint: disable=W0122
            return ctx
    except Exception:  # pylint: disable=W0703
        pass
    return None


def _from_import(import_path: str) -> Optional[Dict]:

    try:
        context = import_string(import_path)
        if callable(context):
            context = context()
        if isinstance(context, dict):
            return context
    except Exception:  # pylint: disable=W0703
        pass
    return None
