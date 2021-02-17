# pylint: disable=C0114

import inspect
import json
from types import ModuleType
from typing import Iterable, Type, Union, Optional
from django.utils.module_loading import import_string
from importlib import import_module
from django.utils.safestring import SafeString
from django.urls.converters import (
    IntConverter,
)
from django import template
from django.conf import settings
from django.urls import (
    reverse,
    URLPattern,
    URLResolver
)

register = template.Library()

__all__ = ['classes_to_js', 'modules_to_js', 'urls_to_js']


def to_js(classes: dict, indent: str = ''):
    """
    Convert python class defines to javascript.

    :param classes: A dictionary of class types mapped to a list of members that should be
        translated into javascript
    :param indent: An indent sequence that will be prepended to all lines
    :return: The classes represented in javascript
    """
    j_script = ''
    for cls, defines in classes.items():
        if defines:
            j_script += f"{indent}{cls.__name__}: {{ \n"

            for ancestor in cls.__mro__:
                if ancestor != cls and ancestor in classes:
                    idx = 1
                    for key, val in classes[ancestor].items():
                        j_script += f'{indent}     {key}: {json.dumps(val)},\n'
                        idx += 1

            idx = 1
            for key, val in defines.items():
                j_script += f"{indent}     {key}: " \
                            f"{json.dumps(val)}{',' if idx < len(defines) else ''}\n"
                idx += 1

            j_script += f'{indent}}},\n\n'

    return SafeString(j_script)


@register.filter(name='classes_to_js')
def classes_to_js(classes: Iterable[Union[Type, str]], indent: str = '') -> str:
    """
    Convert a list of classes to javascript. Only upper case, non-callable members will be
    translated.

    .. code-block::

        {{ classes|classes_to_js:"  " }}

    :param classes: An iterable of class types, or class string paths to convert
    :param indent: A sequence that will be prepended to all output lines
    :return: The translated javascript
    """
    clss = {}
    for cls in classes:
        if isinstance(cls, str):
            cls = import_string(cls)
        if inspect.isclass(cls):
            clss[cls] = {n: getattr(cls, n) for n in dir(cls) if n.isupper()}
        else:
            raise ValueError(f'Expected class type, got {type(cls)}')
    return to_js(clss, indent)


@register.filter(name='modules_to_js')
def modules_to_js(modules: Iterable[Union[ModuleType, str]], indent: str = '') -> str:
    """
    Convert a list of python modules to javascript. Only upper case, non-callable class members will
    be translated. If a class has no qualifying members it will not be included.

    .. code-block::

        {{ modules|modules_to_js:"  " }}

    :param modules: An iterable of python modules or string paths of modules to convert
    :param indent: A sequence that will be prepended to all output lines
    :return: The translated javascript
    """
    classes = {}
    for module in modules:
        if isinstance(module, str):
            module = import_module(module)
        for key in dir(module):
            cls = getattr(module, key)
            if inspect.isclass(cls):
                classes[cls] = {n: getattr(cls, n) for n in dir(cls) if n.isupper()}

    return to_js(classes, indent)


def url_pattern_to_js(
        url_pattern: URLPattern,
        namespace: Optional[str] = None,
        indent: str = '',
        depth: int = 1
):
    ns = ''
    if namespace:
        ns = f'{namespace}:'
    return (
                f'{indent*depth}{url_pattern.name}: function() {{\n'
                f'{indent*(depth+1)}return "{reverse(f"{ns}{url_pattern.name}")}";\n'
                f'{indent*(depth)}}},\n'
    )


def url_resolver_to_js(url_resolver, namespace=None, indent='', depth=1):
    ns = ''
    if namespace:
        ns = f'{namespace}:'
    return ''


@register.simple_tag
def urls_to_js(url_conf: Optional[Union[ModuleType, str]] = None, indent: str = '') -> str:
    """
    """
    url_js = ''
    if url_conf is None:
        url_conf = settings.ROOT_URLCONF

    if isinstance(url_conf, str):
        url_conf = import_module(url_conf)

    for pattern in url_conf.urlpatterns:
        if isinstance(pattern, URLPattern) and getattr(pattern, 'name', None):
            url_js += f'{url_pattern_to_js(pattern, indent=indent)}'
        #elif isinstance(pattern, URLResolver):
        #    url_js += f'{url_resolver_to_js(pattern, indent=indent)}'

    return SafeString(url_js)
