# pylint: disable=C0114

import inspect
import json
from types import ModuleType
from typing import Iterable, Type

from django import template

register = template.Library()

__all__ = ['classes_to_js', 'modules_to_js']


def to_js(classes: dict, indent: str = ''):
    """
    Convert python class defines to javascript.

    :param classes: A dictionary of class types mapped to a list of members that should be
        translated into javascript
    :param indent: An indent sequence that will be prepended to all lines except the first one
    :return: The classes represented in javascript
    """
    j_script = ''
    first = True
    for cls, defines in classes.items():
        if defines:
            j_script += f"{indent if not first else ''}{cls.__name__}: {{ \n"
            first = False

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

    return j_script


@register.filter(name='classes_to_js')
def classes_to_js(classes: Iterable[Type], indent: str = '') -> str:
    """
    Convert a list of classes to javascript. Only upper case, non-callable members will be
    translated.

    :param classes: An iterable of class types to convert
    :param indent: A sequence that will be prepended to all output lines
    :return: The translated javascript
    """
    clss = {}
    for cls in classes:
        if inspect.isclass(cls):
            clss[cls] = {n: getattr(cls, n) for n in dir(cls) if n.isupper()}
        else:
            raise ValueError(f'Expected class type, got {type(cls)}')
    return to_js(clss, indent)


@register.filter(name='modules_to_js')
def modules_to_js(modules: Iterable[ModuleType], indent: str = '') -> str:
    """
    Convert a list of python modules to javascript. Only upper case, non-callable class members will
    be translated. If a class has no qualifying members it will not be included.

    :param modules: An iterable of python modules to convert
    :param indent: A sequence that will be prepended to all output lines
    :return: The translated javascript
    """
    classes = {}
    for module in modules:
        for key in dir(module):
            cls = getattr(module, key)
            if inspect.isclass(cls):
                classes[cls] = {n: getattr(cls, n) for n in dir(cls) if n.isupper()}

    return to_js(classes, indent)
