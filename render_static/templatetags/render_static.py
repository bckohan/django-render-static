"""
Template tags and filters available when the render_static app is installed.
"""

from enum import Enum
from types import ModuleType
from typing import Collection, Iterable, List, Optional, Type, Union
from warnings import warn

from django import template
from django.utils.module_loading import import_string
from django.utils.safestring import SafeString
from render_static.transpilers.classes_to_js import (
    DefaultClassWriter,
    PythonClassVisitor,
)
from render_static.transpilers.enums_to_js import EnumClassWriter
from render_static.transpilers.modules_to_js import (
    DefaultModuleWriter,
    PythonModuleVisitor,
)
from render_static.transpilers.urls_to_js import ClassURLWriter, URLTreeVisitor

register = template.Library()

__all__ = [
    'split',
    'classes_to_js',
    'modules_to_js',
    'urls_to_js',
    'enum_to_js'
]


@register.filter(name='split')
def split(to_split: str, sep: Optional[str] = None) -> List[str]:
    """
    Django template for python's standard split function. Splits a string into
    a list of strings around a separator.

    :param to_split: The string to split
    :param sep: The separator characters to use as split markers.
    :return: A list of strings
    """
    if sep:
        return to_split.split(sep)
    return to_split.split()


@register.simple_tag
def classes_to_js(
        classes: Union[Collection[Union[Type, str]], Type, str],
        indent: str = '\t',
        transpiler: Union[Type[PythonClassVisitor], str] = DefaultClassWriter,
        **kwargs
) -> str:
    """
    Convert a list of classes to javascript. Only upper case, non-callable
    members will be translated.

    .. code-block::

        {{ classes_to_js classes=classes indent="  " %}

    :param classes: An iterable of class types, or class string paths to
        convert
    :param indent: A sequence that will be prepended to all output lines,
        default: \t
    :param transpiler: The transpiler class or import string to the transpiler
        class to use
    :return: The translated javascript
    """
    if isinstance(transpiler, str):
        # mypy doesn't pick up this switch from str to class, import_string
        # probably untyped
        transpiler = import_string(transpiler)

    return SafeString(
        transpiler(indent=indent, **kwargs).generate(classes)  # type: ignore
    )


@register.simple_tag
def modules_to_js(
        modules: Union[Collection[Union[ModuleType, str]], ModuleType, str],
        indent: str = '\t',
        transpiler: Union[
            Type[PythonModuleVisitor],
            str
        ] = DefaultModuleWriter,
        class_transpiler: Union[
            Type[PythonClassVisitor],
            str
        ] = DefaultClassWriter,
        **kwargs
) -> str:
    """
    Convert a list of python modules to javascript. Only upper case,
    non-callable class members will be translated. If a class has no
    qualifying members it will not be included.

    .. code-block::

        {% modules_to_js modules=modules indent="  " %}

    :param modules: An iterable of python modules or string paths of modules
        to convert
    :param indent: A sequence that will be prepended to all output lines,
        default: \t
    :param transpiler: The transpiler class or import string to the transpiler
        class to use
    :param class_transpiler: The class transpiler class or import string to the
        transpiler class to use
    :return: The translated javascript
    """
    if isinstance(transpiler, str):
        # mypy doesn't pick up this switch from str to class, import_string
        # probably untyped
        transpiler = import_string(transpiler)

    return SafeString(
        transpiler(  # type: ignore
            indent=indent,
            class_transpiler=class_transpiler,
            **kwargs
        ).generate(modules)
    )


@register.simple_tag
def urls_to_js(  # pylint: disable=R0913,R0915
        transpiler: Union[Type[URLTreeVisitor], str] = ClassURLWriter,
        url_conf: Optional[Union[ModuleType, str]] = None,
        indent: str = '\t',
        depth: int = 0,
        include: Optional[Iterable[str]] = None,
        exclude: Optional[Iterable[str]] = None,
        es5: bool = False,
        **kwargs
) -> str:
    """
    Dump reversible URLs to javascript. The javascript generated provides
    functions for each fully qualified URL name that perform the same service
    as Django's URL `reverse` function. The javascript output by this tag
    isn't standalone. It is up to the caller to embed it in another object.
    For instance, given the following urls.py:

    .. code-block::

        from django.urls import include, path
        from views import MyView

        urlpatterns = [
            path('my/url/', MyView.as_view(), name='my_url'),
            path('url/with/arg/<int:arg1>', MyView.as_view(), name='my_url'),
            path('sub/', include('other_app.urls', namespace='sub')),
        ]

    And the other app's urls.py:

    .. code-block::

        from django.urls import path
        from views import MyView

        urlpatterns = [
            path('detail/<uuid:id>', MyView.as_view(), name='detail'),
        ]

    And the following template:

    .. code-block::

        var urls =  {
            {% urls_to_js %}
        };

    The generated javascript would look like (without the log statements):

    .. code-block::

        var urls = {
            "my_url": function(kwargs={}, args=[]) {
                if (Object.keys(kwargs).length === 0)
                    return "/my/url/";
                if (Object.keys(kwargs).length === 1 && ['arg1'].every(
                    value => kwargs.hasOwnProperty(value))
                )
                    return `/url/with/arg/${kwargs["arg1"]}`;
                throw new TypeError(
                    "No reversal available for parameters at path: "
                    "other:detail"
                );
            },
            "other": {
                "detail": function(kwargs={}, args=[]) {
                    if (Object.keys(kwargs).length === 1 && ['id'].every(
                        value => kwargs.hasOwnProperty(value))
                    )
                        return `/sub/detail/${kwargs["id"]}`;
                    throw new TypeError(
                        "No reversal available for parameters at path: "
                        "other:detail"
                    );
                },
            },
        };


        # /my/url/
        console.log(urls.my_url());

        # /url/with/arg/143
        console.log(urls.my_url({'arg1': 143}));

        # /sub/detail/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa
        console.log(urls.other.detail(
            {'id': 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'})
        );


    .. note::
        Care has been taken to harden this process to changes to the Django url
        resolution source and to ensure that it just works with minimal
        intervention.

        The general strategy of this process is two staged. First a tree
        structure is generated by walking the urlpatterns structure that
        contains the url patterns and resolves all their fully qualified names
        including all parent namespaces. URLs and namespaces are included and
        excluded at this stage based on the include/exclude parameters. The
        branches of the tree are namespaces and the leaves are fully qualified
        URL names containing lists of corresponding URLPatterns.

        The second stage recursively walks the tree, writing javascript as it
        enters namespaces and encounters URLPatterns. Multiple URLs may be
        registered against the same fully qualified name, but may be
        distinguished by the named parameters they accept. One javascript
        function is generated for each fully qualified URL name, that will
        select the correct URL reversal based on the names of the parameters
        passed in and map those parameter values to the correct
        placeholders in the URL. To ensure the outputs of the javascript match
        Django's `reverse` the strategy is to use the results of the `reverse`
        call for the fully qualified name. Placeholder values are passed into
        `reverse` and then overwritten with javascript substitution code based
        on the regex grouping information. This strategy avoids as much error
        prone regex/string processing as possible. The concession here is that
        placeholder values must be supplied by the user wherever we cant infer
        them. When using path instead of re_path we can use default
        placeholders for all the known converters. When using re_path or custom
        path converters users must register placeholders by parameter name,
        converter type, or app_name. Libraries exist for generating string
        patterns that match regex's but none seem reliable or stable enough to
        include as a dependency.

    :param transpiler: The transpiler class that will generate the JavaScript,
        as either a class or an import string. May be one of the built-ins or a
        user defined transpiler.
    :param url_conf: The root url module to dump urls from,
        default: settings.ROOT_URLCONF
    :param indent: string to use for indentation in javascript, default: '  '
    :param depth: the starting indentation depth, default: 0
    :param include: A list of path names to include, namespaces without path
        names will be treated as every path under the namespace.
        Default: include everything
    :param exclude: A list of path names to exclude, namespaces without path
        names will be treated as every path under the namespace.
        Default: exclude nothing
    :param es5: if True, dump es5 valid javascript, if False javascript will
        be es6
    :param kwargs: Extra kwargs that will be passed to the visitor class on
        construction. All visitors are passed indent, depth, and es5.
    :return: A javascript object containing functions that generate urls with
        and without parameters
    """

    kwargs['depth'] = depth
    kwargs['indent'] = indent
    kwargs['es5'] = es5
    kwargs['include'] = include
    kwargs['exclude'] = exclude

    if 'visitor' in kwargs:
        warn(
            '`visitor` argument is deprecated, change to `transpiler`.',
            DeprecationWarning
        )

    transpiler = kwargs.pop('visitor', transpiler)
    if isinstance(transpiler, str):
        # mypy doesn't pick up this switch from str to class, import_string
        # probably untyped
        transpiler = import_string(transpiler)

    if not issubclass(transpiler, URLTreeVisitor):  # type: ignore
        raise ValueError(
            f'{transpiler.__class__.__name__} must be of type '
            f'`URLTreeVisitor`!'
        )

    return SafeString(
        transpiler(**kwargs).generate(  # type: ignore
            url_conf
        )
    )


@register.simple_tag
def enum_to_js(
        enum: Union[Type[Enum], str, Collection[Union[Type[Enum], str]]],
        transpiler: Union[Type[EnumClassWriter], str] = EnumClassWriter,
        indent: str = '\t',
        depth: int = 0,
        **kwargs
) -> str:
    """
    Transpile the given enumeration(s).

    :param enum: An enum class or import string or a list of either to
        transpile.
    :param transpiler: A transpiler class or import string of the transpiler
        class to use for the transpilation.
    :param indent: The indent string to use
    :param depth: The depth of the initial indent
    :param kwargs: Any other parameters to pass to the configured transpiler.
        See transpiler docs for details.
    :return: SafeString of rendered transpiled code.
    """

    if isinstance(transpiler, str):
        # mypy doesn't pick up this switch from str to class, import_string
        # probably untyped
        transpiler = import_string(transpiler)

    return SafeString(
        transpiler(  # type: ignore
            indent=indent,
            depth=depth,
            **kwargs
        ).generate(enum)  # type: ignore
    )
