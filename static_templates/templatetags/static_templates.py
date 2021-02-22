# pylint: disable=C0114

import inspect
import itertools
import json
import re
from importlib import import_module
from types import ModuleType
from typing import Dict, Iterable, Optional, Type, Union, Tuple

from django import template
from django.conf import settings
from django.urls import URLPattern, URLResolver, reverse
from django.urls.exceptions import NoReverseMatch
from django.urls.resolvers import RegexPattern, RoutePattern
from django.utils.module_loading import import_string
from django.utils.safestring import SafeString
from static_templates.exceptions import URLGenerationFailed, PlaceholderNotFound
from static_templates.placeholders import resolve_placeholders, resolve_unnamed_placeholders

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


@register.simple_tag
def urls_to_js(  # pylint: disable=R0913
        url_conf: Optional[Union[ModuleType, str]] = None,
        indent: str = '  ',
        depth: int = 0,
        include: Optional[Iterable[str]] = None,
        exclude: Optional[Iterable[str]] = None,
        es5: bool = False
) -> str:
    """
    Dump reversable URLs to javascript. The javascript generated provides functions for each fully
    qualified URL name that perform the same service as Django's URL `reverse` function. The
    javascript output by this tag isn't standalone. It is up to the caller to embed it in another
    object. For instance, given the following urls.py:

    ..code-block::

        from django.urls import include, path
        from views import MyView

        urlpatterns = [
            path('my/url/', MyView.as_view(), name='my_url'),
            path('url/with/arg/<int:arg1>', MyView.as_view(), name='my_url'),
            path('sub/', include('other_app.urls', namespace='sub')),
        ]

    And the other app's urls.py:

    ..code-block::

        from django.urls import path
        from views import MyView

        urlpatterns = [
            path('detail/<uuid:id>', MyView.as_view(), name='detail'),
        ]

    And the following template:

    ..code-block::

        var urls =  {
            {% urls_to_js %}
        };

    The generated javascript would look like:

    ..code-block::

        var urls = {
            "my_url": function(kwargs={}, args=[]) {
                if (Object.keys(kwargs).length === 0)
                    return "/my/url/";
                if (Object.keys(kwargs).length === 1 && ['arg1'].every(
                    value => kwargs.hasOwnProperty(value))
                )
                return `/url/with/arg/${kwargs["arg1"]}`;
            },
            "other": {
                "detail": function(kwargs={}, args=[]) {
                    if (Object.keys(kwargs).length === 1 && ['id'].every(
                        value => kwargs.hasOwnProperty(value))
                    )
                        return `/sub/detail/${kwargs["id"]}`;
                },
            },
        };


        # /my/url/
        console.log(urls.my_url());

        # /url/with/arg/143
        console.log(urls.my_url({'arg1': 143}));

        # /sub/detail/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa
        console.log(urls.other.detail({'id': 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'}));


    ..note::
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


    :param url_conf: The root url module to dump urls from, default: settings.ROOT_URLCONF
    :param indent: string to use for indentation in javascript, default: '  '
    :param depth: the starting indentation depth, default: 0
    :param include: A list of url names to include, namespaces without url names will be treated as
        every url under the namespace. Default: include everything
    :param exclude: A list of url names to exclude, namespaces without url names will be treated as
        every url under the namespace. Default: exclude nothing
    :param es5: if True, dump es5 valid javascript, if False javascript will be es6
    :return: A javascript object containing functions that generate urls with and without parameters
    """
    if url_conf is None:
        url_conf = settings.ROOT_URLCONF

    if isinstance(url_conf, str):
        url_conf = import_module(url_conf)

    def normalize_ns(namespaces: str) -> Iterable[str]:
        return ':'.join([ns for ns in namespaces.split(':') if ns])

    includes = []
    excludes = []
    if include:
        includes = [normalize_ns(incl) for incl in include]
    elif exclude:
        excludes = [normalize_ns(excl) for excl in exclude]

    patterns = getattr(url_conf, 'urlpatterns', None)
    if patterns is None:
        raise AttributeError(f'{url_conf} has no attribute urlpatterns!')

    def build_tree(
            nodes: Iterable[URLPattern],
            branch: Tuple[Dict, Dict, Optional[str]],
            namespace: Optional[str] = None,
            qname: str = '',
            app_name: Optional[str] = None
    ) -> Tuple[Dict, Dict, Optional[str]]:

        if namespace:
            qname += f"{':' if qname else ''}{namespace}"

        if includes and qname not in includes:
            return branch
        if excludes and qname in excludes:
            return branch

        if namespace:
            branch[0].setdefault(namespace, [{}, {}, app_name])
            branch = branch[0][namespace]

        for pattern in nodes:
            if isinstance(pattern, URLPattern):
                name = getattr(pattern, 'name', None)
                if name is None:
                    continue

                qname_wild = f"{qname}{':' if qname else ''}{'*'}"
                qname += f"{':' if qname else ''}{name}"
                if includes and qname not in includes and qname_wild not in includes:
                    continue
                if excludes and (qname in excludes or qname_wild in excludes):
                    continue
                branch[1].setdefault(pattern.name, []).append(pattern)

            elif isinstance(pattern, URLResolver):
                build_tree(
                    pattern.url_patterns,
                    branch,
                    namespace=pattern.namespace,
                    qname=qname,
                    app_name=pattern.app_name
                )

        return branch

    def nodes_to_js(
            nodes: Iterable[URLPattern],
            qname: str,
            dpth: int,
            app_name: Optional[str] = None
    ) -> str:

        if es5:
            p_js = f'{indent * dpth}"{qname.split(":")[-1]}": function(kwargs, args) {{\n'
            p_js += f'{indent * (dpth+1)}kwargs = kwargs || {{}};\n'
            p_js += f'{indent * (dpth+1)}args = args || [];\n'
        else:
            p_js = f'{indent * dpth}"{qname.split(":")[-1]}": function(kwargs={{}}, args=[]) {{\n'

        def reversable(endpoint):
            # django doesnt allow mixing unnamed and named parameters when reversing a url
            num_named = len(endpoint.pattern.regex.groupindex)
            if num_named and num_named != endpoint.pattern.regex.groups:
                return False
            return True

        def add_pattern(endpoint: URLPattern):
            if not reversable(endpoint):
                return ''
            if isinstance(endpoint.pattern, RoutePattern):
                params = {
                    var: {
                        'converter': converter.__class__,
                        'app_name': app_name
                    } for var, converter in endpoint.pattern.converters.items()
                }
            elif isinstance(endpoint.pattern, RegexPattern):
                params = {
                    var: {
                        'app_name': app_name
                    } for var in endpoint.pattern.regex.groupindex.keys()
                }
            else:
                raise URLGenerationFailed(f'Unrecognized URLPattern type: {type(endpoint)}')

            unnamed = endpoint.pattern.regex.groups > 0 and not params
            if params or unnamed:
                try:
                    if unnamed:
                        resolved_placeholders = resolve_unnamed_placeholders(
                            url_name=endpoint.name,
                            app_name=app_name
                        )
                    else:
                        resolved_placeholders = itertools.product(*[
                            resolve_placeholders(
                                param,
                                **lookup
                            ) for param, lookup in params.items()
                        ])
                    for placeholders in resolved_placeholders:
                        kwargs = {
                            param: placeholders[idx] for idx, param in enumerate(params.keys())
                        }
                        try:
                            if unnamed:
                                placeholder_url = reverse(qname, args=placeholders)
                            else:
                                placeholder_url = reverse(qname, kwargs=kwargs)
                            # it must match! The URLPattern tree complicates things by often times
                            # having ^ present at the start of each regex snippet - no way around
                            # removing it because we're matching against full url strings
                            mtch = endpoint.pattern.regex.search(placeholder_url.lstrip('/'))
                            if not mtch:
                                endpoint.pattern.regex.search(placeholder_url)
                            if not mtch:
                                mtch = re.search(
                                    endpoint.pattern.regex.pattern.lstrip('^'),
                                    placeholder_url.lstrip('/')
                                )
                            if not mtch:
                                mtch = re.search(
                                    endpoint.pattern.regex.pattern.lstrip('^'),
                                    placeholder_url
                                )
                            if not mtch:
                                continue  # try another placeholder
                            url = ''
                            # there might be group matches that aren't part of our kwargs, we go
                            # through this extra work to make sure we aren't subbing spans that
                            # aren't kwargs
                            grp_mp = {
                                idx: var for var, idx in endpoint.pattern.regex.groupindex.items()
                            }
                            replacements = []
                            for idx, value in enumerate(mtch.groups(), start=1):
                                if unnamed:
                                    replacements.append(
                                        (
                                            mtch.span(idx),
                                            (
                                                f'"+args[{idx-1}].toString()+"' if es5
                                                else
                                                f'${{args[{idx-1}]}}'
                                            )
                                        )
                                    )
                                elif idx in grp_mp and grp_mp[idx] in kwargs:
                                    replacements.append(
                                        (
                                            mtch.span(idx),
                                            (
                                                f'"+kwargs["{grp_mp[idx]}"].toString()+"' if es5
                                                else
                                                f'${{kwargs["{grp_mp[idx]}"]}}'
                                            )
                                        )
                                    )
                            url_idx = 0
                            for rpl in replacements:
                                while url_idx <= rpl[0][0]:
                                    url += placeholder_url[url_idx]
                                    url_idx += 1
                                url += rpl[1]
                                url_idx += (rpl[0][1]-rpl[0][0])
                            opts_str = ",".join([f"'{param}'" for param in kwargs.keys()])
                            if unnamed:
                                qt = '"' if es5 else '`'
                                return (
                                        f'{indent * (dpth + 1)}if (args.length === '
                                        f'{len(placeholders)})\n'
                                        f'{indent * (dpth + 2)}'
                                        f'return {qt}/{url.lstrip("/")}{qt};\n'
                                )
                            else:
                                if es5:
                                    return (
                                            f'{indent * (dpth + 1)}if (Object.keys(kwargs).length '
                                            f'=== {len(kwargs)} && [{opts_str}].every('
                                            f'function(value) {{ '
                                            f'return kwargs.hasOwnProperty(value);}}))\n'
                                            f'{indent * (dpth + 2)}return "/{url.lstrip("/")}";\n'
                                    )
                                else:
                                    return (
                                            f'{indent * (dpth + 1)}if (Object.keys(kwargs).length '
                                            f'=== {len(kwargs)} && '
                                            f'[{opts_str}].every('
                                            f'value => kwargs.hasOwnProperty(value)))\n'
                                            f'{indent * (dpth + 2)}return `/{url.lstrip("/")}`;\n'
                                    )

                        except NoReverseMatch:
                            continue
                except PlaceholderNotFound as pnf:
                    raise URLGenerationFailed(
                        f'Unable to generate url for {qname} using pattern {endpoint} '
                        f'because: {pnf}'
                    ) from pnf
            else:
                return (
                    f'{indent * (dpth + 1)}if (Object.keys(kwargs).length === 0 && '
                    f'args.length === 0)\n'
                    f'{indent * (dpth + 2)}return "/{reverse(qname).lstrip("/")}";\n'
                )
            raise URLGenerationFailed(
                f'Unable to generate url for {qname} with kwargs: '
                f'{params.keys()} using pattern {endpoint}!'
            )

        for pattern in nodes:
            p_js += add_pattern(pattern)

        return f'{p_js}\n{indent*dpth}}},\n'

    def write_javascript(
            tree: Tuple[Dict, Dict, Optional[str]],
            namespace: Optional[str] = None,
            dpth: int = 1,
            qname: str = '',
    ) -> str:

        js = ''

        if namespace:
            qname += f"{':' if qname else ''}{namespace}"

        for name, nodes in tree[1].items():
            js += nodes_to_js(nodes, f"{f'{qname}:' if qname else ''}{name}", dpth+1, tree[2])

        if tree[0]:
            for ns, branch in tree[0].items():
                js += f'{indent*dpth}"{ns}": {{\n'
                js += write_javascript(branch, ns, dpth+1, qname)
                js += f'{indent*dpth}}},\n'

        return js

    return SafeString(
        write_javascript(
            build_tree(
                patterns,
                ({}, {}, getattr(url_conf, 'app_name', None))
            ),
            '',
            dpth=depth+1
        )
    )
