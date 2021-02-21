from typing import Any, Dict, Generator, List, Type, Optional

from django.urls import converters
from static_templates.exceptions import PlaceholderNotFound

__all__ = [
    'register_converter_placeholder',
    'register_variable_placeholder',
    'resolve_placeholders'
]

converter_placeholders: Dict[Type, List] = {
    converters.IntConverter: [0],
    converters.PathConverter: ['a'],
    converters.SlugConverter: ['a'],
    converters.StringConverter: ['a'],
    converters.UUIDConverter: ['aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa']
}

app_variable_placeholders: Dict[str, Dict[str, List]] = {}

variable_placeholders: Dict[str, List] = {}


def register_converter_placeholder(
        converter_type: Type,
        placeholder: Any
) -> None:
    if not isinstance(converter_type, type):
        raise ValueError(f'converter_type should be of type `type`, got {type(converter_type)}!')

    placeholders = converter_placeholders.setdefault(converter_type, [])
    if placeholder not in placeholders:
        placeholders.append(placeholder)


def register_variable_placeholder(
        var_name: str,
        placeholder: Any,
        app_name: Optional[str] = None
) -> None:
    placeholders = variable_placeholders.setdefault(var_name, [])
    if placeholder not in placeholders:
        placeholders.append(placeholder)
    if app_name:
        placeholders = app_variable_placeholders.setdefault(app_name, {}).setdefault(var_name, [])
        if placeholder not in placeholders:
            placeholders.append(placeholder)


def resolve_placeholders(
        var_name: str,
        app_name: Optional[str] = None,
        converter: Optional[Type] = None
) -> Generator[Any, None, None]:

    placeholders = [] if not converter else (
        [converter.placeholder] if hasattr(converter, 'placeholder') else []
    )
    if converter:
        placeholders.extend(converter_placeholders.get(converter, []))
    if app_name:
        placeholders.extend(app_variable_placeholders.get(app_name, {}).get(var_name, []))
    placeholders.extend(variable_placeholders.get(var_name, []))

    if not placeholders:
        lookup = {
            'parameter': var_name,
            'converter': str(converter),
            'app_name': app_name
        }
        raise PlaceholderNotFound(
            f'No placeholders are registered for any of the lookup parameters: {lookup}'
        )

    for placeholder in placeholders:
        yield placeholder
