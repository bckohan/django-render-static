# pylint: disable=C0114

import inspect
import json
from importlib import import_module
from types import ModuleType
from typing import Iterable, Optional, Type, Union

from django import template
from django.utils.module_loading import import_string
from django.utils.safestring import SafeString
from render_static.url_tree import SimpleURLWriter, URLTreeVisitor, build_tree

register = template.Library()

__all__ = ['split', 'classes_to_js', 'modules_to_js', 'urls_to_js']


@register.filter(name='split')
def split(to_split: str, sep: Optional[str] = None) -> Iterable[str]:
    """
    Django template for python's standard split function. Splits a string into a list of strings
    around a separator.

    :param to_split: The string to split
    :param sep: The separator characters to use as split markers.
    :return: A list of strings
    """
    if sep:
        return to_split.split(sep)
    return to_split.split()


def to_js(classes: dict, indent: str = '\t'):
    """
    Convert python class defines to javascript.

    :param classes: A dictionary of class types mapped to a list of members that should be
        translated into javascript
    :param indent: An indent sequence that will be prepended to all lines, default: \t
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
def classes_to_js(classes: Iterable[Union[Type, str]], indent: str = '\t') -> str:
    """
    Convert a list of classes to javascript. Only upper case, non-callable members will be
    translated.

    .. code-block::

        {{ classes|classes_to_js:"  " }}

    :param classes: An iterable of class types, or class string paths to convert
    :param indent: A sequence that will be prepended to all output lines, default: \t
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
def modules_to_js(modules: Iterable[Union[ModuleType, str]], indent: str = '\t') -> str:
    """
    Convert a list of python modules to javascript. Only upper case, non-callable class members will
    be translated. If a class has no qualifying members it will not be included.

    .. code-block::

        {{ modules|modules_to_js:"  " }}

    :param modules: An iterable of python modules or string paths of modules to convert
    :param indent: A sequence that will be prepended to all output lines, default: \t
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


@register.simple_tag
def urls_to_js(  # pylint: disable=R0913,R0915
        visitor: Union[Type, str] = SimpleURLWriter,
        url_conf: Optional[Union[ModuleType, str]] = None,
        indent: str = '\t',
        depth: int = 0,
        include: Optional[Iterable[str]] = None,
        exclude: Optional[Iterable[str]] = None,
        es5: bool = False,
        **kwargs
) -> str:
    """
    Dump reversible URLs to javascript. The javascript generated provides functions for each fully
    qualified URL name that perform the same service as Django's URL `reverse` function. The
    javascript output by this tag isn't standalone. It is up to the caller to embed it in another
    object. For instance, given the following urls.py:

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
                    "No reversal available for parameters at path: other:detail"
                );
            },
            "other": {
                "detail": function(kwargs={}, args=[]) {
                    if (Object.keys(kwargs).length === 1 && ['id'].every(
                        value => kwargs.hasOwnProperty(value))
                    )
                        return `/sub/detail/${kwargs["id"]}`;
                    throw new TypeError(
                        "No reversal available for parameters at path: other:detail"
                    );
                },
            },
        };


        # /my/url/
        console.log(urls.my_url());

        # /url/with/arg/143
        console.log(urls.my_url({'arg1': 143}));

        # /sub/detail/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa
        console.log(urls.other.detail({'id': 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'}));


    .. note::
        Care has been taken to harden this process to changes to the Django url resolution
        source and to ensure that it just works with minimal intervention.

        The general strategy of this process is two staged. First a tree structure is generated
        by walking the urlpatterns structure that contains the url patterns and resolves all their
        fully qualified names including all parent namespaces. URLs and namespaces are included
        and excluded at this stage based on the include/exclude parameters. The branches of the tree
        are namespaces and the leaves are fully qualified URL names containing lists of
        corresponding URLPatterns.

        The second stage recursively walks the tree, writing javascript as it enters namespaces and
        encounters URLPatterns. Multiple URLs may be registered against the same fully qualified
        name, but may be distinguished by the named parameters they accept. One javascript function
        is generated for each fully qualified URL name, that will select the correct URL reversal
        based on the names of the parameters passed in and map those parameter values to the correct
        placeholders in the URL. To ensure the outputs of the javascript match Django's `reverse`
        the strategy is to use the results of the `reverse` call for the fully qualified name.
        Placeholder values are passed into `reverse` and then overwritten with javascript
        substitution code based on the regex grouping information. This strategy avoids as much
        error prone regex/string processing as possible. The concession here is that placeholder
        values must be supplied by the user wherever we cant infer them. When using path instead of
        re_path we can use default placeholders for all the known converters. When using re_path
        or custom path converters users must register placeholders by parameter name, converter
        type, or app_name. Libraries exist for generating string patterns that match regex's but
        none seem reliable or stable enough to include as a dependency.

    :param visitor: The visitor class that will generate the JavaScript, as either a class or an
        import string. May be one of the built-ins or a user defined visitor.
    :param url_conf: The root url module to dump urls from, default: settings.ROOT_URLCONF
    :param indent: string to use for indentation in javascript, default: '  '
    :param depth: the starting indentation depth, default: 0
    :param include: A list of path names to include, namespaces without path names will be treated
        as every path under the namespace. Default: include everything
    :param exclude: A list of path names to exclude, namespaces without path names will be treated
        as every path under the namespace. Default: exclude nothing
    :param es5: if True, dump es5 valid javascript, if False javascript will be es6
    :param kwargs: Extra kwargs that will be passed to the visitor class on construction. All
        visitors are passed indent, depth, and es5.
    :return: A javascript object containing functions that generate urls with and without parameters
    """

    kwargs['depth'] = depth
    kwargs['indent'] = indent
    kwargs['es5'] = es5

    if isinstance(visitor, str):
        # mypy doesnt pick up this switch from str to class, import_string probably untyped
        visitor = import_string(visitor)

    if not issubclass(visitor, URLTreeVisitor):  # type: ignore
        raise ValueError(f'{visitor.__class__.__name__} must be of type `URLTreeVisitor`!')

    return SafeString(
        visitor(**kwargs).generate(  # type: ignore
            build_tree(
                url_conf,
                include,
                exclude
            )[0]
        )
    )
