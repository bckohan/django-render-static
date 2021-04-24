"""
The `url_to_js` tag avoids error prone string processing by using Django's `reverse` mechanism to
generate the URLs to embed in the javascript. To do the reversal it needs temporary placeholder
values to feed in as kwargs or args. There aren't reliable or license friendly libraries available
to generate the placeholders directly from the regular expressions so users are relied upon to
supply them. This module provides facilities for registering and resolving those placeholders. It
also contains some predefined placeholders for the admin module.

Users are strongly encouraged to use paths instead of re_paths and to supply custom converters when
needed to avoid the need for re_paths. This should make the placeholder registration process as
painless as possible. All of the builtin converters already have placeholders registered for them.
Custom converters can simply add a `placeholder` class attribute that will be used without requiring
an explicit registration.

    .. note::
        Many placeholders may be registered for a variable name/app_name. They'll be tried until one
        is found to work, and prioritized in the order of most specific registration. This means
        a placeholder registered against app1 and variable name var1 will be tried before the
        placeholder registered against var1. Converters are the most specific registration info.
"""

from typing import Any, Dict, Iterable, List, Optional, Type

from django.urls import converters

__all__ = [
    'register_converter_placeholder',
    'register_variable_placeholder',
    'register_unnamed_placeholders',
    'resolve_placeholders',
    'resolve_unnamed_placeholders'
]

# DO NOT EXPAND THIS LIST LIGHTLY - for URLs with large numbers of arguments, say 5 where all these
# defaults are tried that would be an O(n^5) operation, where n is the number of defaults.
# URLs with large numbers of arguments should be rare - but there is a complexity check that will
# throw an exception when a maximum number of tries is reached
ALWAYS_TRY_THESE = [0, 'a', 1, 'A', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa']

converter_placeholders: Dict[Type, List] = {
    converters.IntConverter: [0],
    converters.PathConverter: ['a'],
    converters.SlugConverter: ['a'],
    converters.StringConverter: ['a'],
    converters.UUIDConverter: ['aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa']
}

app_variable_placeholders: Dict[str, Dict[str, List]] = {}
variable_placeholders: Dict[str, List] = {}
app_unnamed_placeholders: Dict[str, Dict[str, List]] = {}
unnamed_placeholders: Dict[str, List] = {}


def register_converter_placeholder(
        converter_type: Type,
        placeholder: Any
) -> None:
    """
    Register a placeholder for the given converter type. This registry function is intended to allow
    placeholders to be registered for converters outside the control of the calling code base. For
    converters under your control you should add a placeholder attribute to the converter class
    instead.

    :param converter_type: The type of the converter
    :param placeholder: A valid placeholder to use for the converter
    """
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
    """
    Register a placeholder for a specific variable name and also optionally an app_name.

    :param var_name: The variable name to use this placeholder for
    :param placeholder: The placeholder to use
    :param app_name: The optional app_name.
    :return:
    """
    placeholders = variable_placeholders.setdefault(var_name, [])
    if placeholder not in placeholders:
        placeholders.append(placeholder)
    if app_name:
        placeholders = app_variable_placeholders.setdefault(app_name, {}).setdefault(var_name, [])
        if placeholder not in placeholders:
            placeholders.append(placeholder)


def register_unnamed_placeholders(
    url_name: str,
    placeholders: List,
    app_name: Optional[str] = None
) -> None:
    """
    Register a list of placeholders for a url_name and optionally an app_name that takes unnamed
    arguments. The list indices should correspond to the argument order as passed to reverse.

    :param url_name: The name of the url path to register the placeholders for
    :param placeholders: The list of placeholders to use
    :param app_name: The optional app_name
    """
    placeholder_lists = unnamed_placeholders.setdefault(url_name, [])
    if placeholders not in placeholder_lists:
        placeholder_lists.append(placeholders)
    if app_name:
        placeholder_lists = app_unnamed_placeholders.setdefault(
            app_name, {}
        ).setdefault(
            url_name, []
        )
        if placeholders not in placeholder_lists:
            placeholder_lists.append(placeholders)


def resolve_placeholders(
        var_name: str,
        app_name: Optional[str] = None,
        converter: Optional[Type] = None
) -> Iterable:
    """
    Resolve placeholders for named variables that match the given lookup parameters.

    :param var_name: The variable name to search for
    :param app_name: The optional app_name to search for
    :param converter: The optional converter type to search for
    :return: A list of placeholders to try
    """

    placeholders = [] if not converter else (
        [converter.placeholder] if hasattr(converter, 'placeholder') else []
    )
    if converter:
        placeholders.extend(converter_placeholders.get(converter, []))
    if app_name:
        placeholders.extend(app_variable_placeholders.get(app_name, {}).get(var_name, []))
    placeholders.extend(variable_placeholders.get(var_name, []))
    return placeholders + [always for always in ALWAYS_TRY_THESE if always not in placeholders]


def resolve_unnamed_placeholders(
        url_name: str,
        nargs: int,
        app_name: Optional[str] = None,
) -> Iterable:
    """
    Resolve placeholders to use for a url with unnamed parameters based on the url name and
    optionally the app_name.

    :param url_name: The name of the URL to search for
    :param nargs: The number of arguments for this url
    :param app_name: The optional app_name to search for
    :return: A list of lists of placeholders to try, where the outer list is indexed by argument
        index
    """

    placeholders: List[List[object]] = [[] for arg in range(0, nargs)]

    def add_candidates(candidates: List[List[object]]) -> None:
        for candidate in candidates:
            if len(candidate) == nargs:
                for idx, arg in enumerate(candidate):
                    placeholders[idx].append(arg)
    if app_name:
        add_candidates(app_unnamed_placeholders.get(app_name, {}).get(url_name, []))
    add_candidates(unnamed_placeholders.get(url_name, []))

    for arg in placeholders:
        arg.extend([always for always in ALWAYS_TRY_THESE if always not in arg])

    return placeholders


register_variable_placeholder('app_label', 'site', app_name='admin')
register_variable_placeholder('app_label', 'auth', app_name='admin')
