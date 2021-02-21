# pylint: disable=C0114

import inspect
import itertools
import json
import re
from importlib import import_module
from types import ModuleType
from typing import Dict, Iterable, List, Optional, Type, Union, Tuple

from django import template
from django.conf import settings
from django.urls import URLPattern, URLResolver, reverse
from django.urls.exceptions import NoReverseMatch
from django.urls.resolvers import RegexPattern, RoutePattern
from django.utils.module_loading import import_string
from django.utils.safestring import SafeString
from static_templates.exceptions import PlaceholderGenerationFailed
from static_templates.placeholders import resolve_placeholders

register = template.Library()

__all__ = ['classes_to_js', 'modules_to_js', 'urls_to_js']

MAX_PLACEHOLDER_TRIES = 32


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
            p_js = f'{indent * dpth}"{qname.split(":")[-1]}": function(options) {{\n'
            p_js += f'{indent * (dpth+1)}options = options || {{}};\n'
        else:
            p_js = f'{indent * dpth}"{qname.split(":")[-1]}": function(options={{}}) {{\n'

        def add_pattern(endpoint: URLPattern):
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
                raise PlaceholderGenerationFailed(f'Unrecognized URLPattern type: {type(endpoint)}')

            if params:
                for placeholders in itertools.product(*[
                    resolve_placeholders(param, **lookup) for param, lookup in params.items()
                ]):
                    kwargs = {param: placeholders[idx] for idx, param in enumerate(params.keys())}
                    try:
                        placeholder_url = reverse(qname, kwargs=kwargs)
                        # it must match! The URLPattern tree complicates things by often times
                        # having ^ present at the start of each regex snippet. We know that this
                        # regex must match the end of the placeholder_url but it might not match
                        # the beginning depending on its placement in the tree - so we spoof
                        # the match beginning behavior by prepending newline and running in
                        # MULTILINE mode
                        mtch = endpoint.pattern.regex.search(placeholder_url.lstrip('/'))
                        if not mtch:
                            endpoint.pattern.regex.search(placeholder_url)
                        if not mtch:
                            mtch = re.search(
                                endpoint.pattern.regex.pattern.lstrip('^'),
                                placeholder_url.lstrip('/'),
                                flags=re.MULTILINE
                            )
                        if not mtch:
                            mtch = re.search(
                                endpoint.pattern.regex.pattern.lstrip('^'),
                                placeholder_url,
                                flags=re.MULTILINE
                            )
                        if not mtch:
                            continue  # TODO is this possible?
                        url = ''
                        # there might be group matches that aren't part of our kwargs, we go through
                        # this extra work to make sure we aren't subbing spans that aren't kwargs
                        grp_mp = {
                            idx: var for var, idx in endpoint.pattern.regex.groupindex.items()
                        }
                        replacements = []
                        for idx, value in enumerate(mtch.groups(), start=1):
                            if idx in grp_mp and grp_mp[idx] in kwargs:
                                replacements.append(
                                    (
                                        mtch.span(idx),
                                        (
                                            f'"+options["{grp_mp[idx]}"].toString()+"' if es5 else
                                            f'${{options["{grp_mp[idx]}"]}}'
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
                        if es5:
                            return (
                                    f'{indent * (dpth + 1)}if (Object.keys(options).length === '
                                    f'{len(kwargs)} && [{opts_str}].every(function(value) {{ '
                                    f'return options.hasOwnProperty(value);}}))\n'
                                    f'{indent * (dpth + 2)}return "/{url.lstrip("/")}";\n'
                            )
                        else:
                            return (
                                    f'{indent * (dpth + 1)}if (Object.keys(options).length === '
                                    f'{len(kwargs)} && '
                                    f'[{opts_str}].every(value => options.hasOwnProperty(value)))\n'
                                    f'{indent * (dpth + 2)}return `/{url.lstrip("/")}`;\n'
                            )

                    except NoReverseMatch:
                        continue
            else:
                return (
                    f'{indent * (dpth + 1)}if (Object.keys(options).length === 0)\n'
                    f'{indent * (dpth + 2)}return "/{reverse(qname).lstrip("/")}";\n'
                )

            raise PlaceholderGenerationFailed(
                f'Unable to generate placeholder for {qname} with options: '
                f'{params.keys()}!'
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
