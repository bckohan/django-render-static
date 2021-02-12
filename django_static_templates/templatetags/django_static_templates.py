from django import template
import json
from types import ModuleType
from typing import (
    Type,
    Iterable
)
import inspect

register = template.Library()

__all__ = ['classes_to_js', 'modules_to_js']


def to_js(classes: dict, indent: str = ''):
    js = ''
    first = True
    for cls, defines in classes.items():
        if defines:
            js += f"{indent if not first else ''}{cls.__name__}: {{ \n"
            first = False

            for ancestor in cls.__mro__:
                if ancestor != cls and ancestor in classes:
                    idx = 1
                    for key, val in classes[ancestor].items():
                        js += f'{indent}     {key}: {json.dumps(val)},\n'
                        idx += 1

            idx = 1
            for key, val in defines.items():
                js += f"{indent}     {key}: {json.dumps(val)}{',' if idx < len(defines) else ''}\n"
                idx += 1

            js += f'{indent}}},\n\n'

    return js


@register.filter(name='classes_to_js')
def classes_to_js(classes: Iterable[Type], indent: str = '') -> str:
    clss = {}
    for cls in classes:
        if inspect.isclass(cls):
            clss[cls] = {n: getattr(cls, n) for n in dir(cls) if n.isupper()}
        else:
            raise ValueError(f'Expected class type, got {type(cls)}')
    return to_js(clss, indent)


@register.filter(name='modules_to_js')
def modules_to_js(modules: Iterable[ModuleType], indent: str = '') -> str:
    classes = {}
    for module in modules:
        for key in dir(module):
            cls = getattr(module, key)
            if inspect.isclass(cls):
                classes[cls] = {n: getattr(cls, n) for n in dir(cls) if n.isupper()}

    return to_js(classes, indent)
