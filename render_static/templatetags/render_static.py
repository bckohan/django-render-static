# pylint: disable=C0114

import inspect
import itertools
import json
import re
from importlib import import_module
from types import ModuleType
from typing import Dict, Iterable, Optional, Tuple, Type, Union

from django import template
from django.conf import settings
from django.urls import URLPattern, URLResolver, reverse
from django.urls.exceptions import NoReverseMatch
from django.urls.resolvers import RegexPattern, RoutePattern
from django.utils.module_loading import import_string
from django.utils.safestring import SafeString
from render_static.exceptions import PlaceholderNotFound, URLGenerationFailed
from render_static.placeholders import (
    resolve_placeholders,
    resolve_unnamed_placeholders,
)

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
        url_conf: Optional[Union[ModuleType, str]] = None,
        indent: str = '\t',
        depth: int = 0,
        include: Optional[Iterable[str]] = None,
        exclude: Optional[Iterable[str]] = None,
        es5: bool = False
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


    .. todo::
        Linters appropriately flag this function for complexity violations. A useful refactor
        would break the components apart and implement a pluggable visitor pattern for code
        generation.

    :param url_conf: The root url module to dump urls from, default: settings.ROOT_URLCONF
    :param indent: string to use for indentation in javascript, default: '  '
    :param depth: the starting indentation depth, default: 0
    :param include: A list of path names to include, namespaces without path names will be treated
        as every path under the namespace. Default: include everything
    :param exclude: A list of path names to exclude, namespaces without path names will be treated
        as every path under the namespace. Default: exclude nothing
    :param es5: if True, dump es5 valid javascript, if False javascript will be es6
    :return: A javascript object containing functions that generate urls with and without parameters
    """

    nl = '\n' if indent else ''  # pylint: disable=C0103

    if url_conf is None:
        url_conf = settings.ROOT_URLCONF

    if isinstance(url_conf, str):
        url_conf = import_module(url_conf)

    def normalize_ns(namespaces: str) -> Iterable[str]:
        return ':'.join([nmsp for nmsp in namespaces.split(':') if nmsp])

    includes = []
    excludes = []
    if include:
        includes = [normalize_ns(incl) for incl in include]
    if exclude:
        excludes = [normalize_ns(excl) for excl in exclude]

    patterns = getattr(url_conf, 'urlpatterns', None)
    if patterns is None:
        raise AttributeError(f'{url_conf} has no attribute urlpatterns!')

    def build_tree(
            nodes: Iterable[URLPattern],
            included: bool,
            branch: Tuple[Dict, Dict, Optional[str]],
            namespace: Optional[str] = None,
            qname: str = '',
            app_name: Optional[str] = None
    ) -> Tuple[Dict, Dict, Optional[str]]:
        """
        Recursively Walk the urlpatterns and generate a tree where the branches are namespaces and
        the leaves are collections of URLs registered against fully qualified reversible names.

        The tree structure will look like this:

        ..code-block::

            [
                { # first dict contains child branches
                    'namespace1': [{...}, {...}, 'incl_app_name1'],
                    'namespace2': [{...}, {...}, None] # no app_name specified for this include
                },
                {
                    'url_name1': [URLPattern, URLPattern, ...] #URLPatterns for this qname
                    'url_name2': [URLPattern, ...]
                },
                None # no root app_name
            ]

        :param nodes: The urls that are leaves of this branch
        :param included: True if this branch has been implicitly included, by includes higher up the
            tree
        :param branch: The branch to build
        :param namespace: the namespace of this branch (if any)
        :param qname: the fully qualified name of the parent branch
        :param app_name: app_name for the branch if any
        :return:
        """

        if namespace:
            branch[0].setdefault(namespace, [{}, {}, app_name])
            branch = branch[0][namespace]

        for pattern in nodes:
            if isinstance(pattern, URLPattern):
                name = getattr(pattern, 'name', None)
                if name is None:
                    continue

                url_qname = f"{f'{qname}:' if qname else ''}{pattern.name}"

                # if we aren't implicitly included we must be explicitly included and not explicitly
                # excluded - note if we were implicitly excluded - we wouldnt get this far
                if (not included and url_qname not in includes or
                        (excludes and url_qname in excludes)):
                    continue

                branch[1].setdefault(pattern.name, []).append(pattern)

            elif isinstance(pattern, URLResolver):
                ns_qname = qname
                if pattern.namespace:
                    ns_qname += f"{':' if qname else ''}{pattern.namespace}"

                if excludes and ns_qname in excludes:
                    continue

                build_tree(
                    pattern.url_patterns,
                    included or (not includes or ns_qname in includes),
                    branch,
                    namespace=pattern.namespace,
                    qname=ns_qname,
                    app_name=pattern.app_name
                )

        return branch

    def prune_tree(
            tree: Tuple[Dict, Dict, Optional[str]]
    ) -> Tuple[Tuple[Dict, Dict, Optional[str]], int]:
        """
        Remove any branches that don't have any URLs under them.
        :param tree: branch to prune
        :return: A 2-tuple containing (the pruned branch, number of urls below)
        """

        num_urls = 0
        for named_nodes in tree[1]:
            num_urls += len(named_nodes[1])

        if tree[0]:
            to_delete = []
            for nmsp, branch in tree[0].items():
                branch, branch_urls = prune_tree(branch)
                if branch_urls == 0:
                    to_delete.append(nmsp)
                num_urls += branch_urls
            for nmsp in to_delete:
                del tree[0][nmsp]

        return tree, num_urls

    def nodes_to_js(
            nodes: Iterable[URLPattern],
            qname: str,
            app_name: Optional[str] = None
    ) -> str:
        """
        Convert a list of URLPatterns all corresponding to the same qualified name to javascript.

        :param nodes: The list of URLPattern objects
        :param qname: The fully qualified name of all the URLs
        :param app_name: The app_name the URLs belong to, if any
        :return: A javascript function that reverses the URLs based on kwarg or arg inputs
        """

        dpth = depth + qname.count(':') + 1

        if es5:
            p_js = f'{indent * dpth}"{qname.split(":")[-1]}": function(kwargs, args) {{{nl}'
            p_js += f'{indent * (dpth+1)}kwargs = kwargs || {{}};{nl}'
            p_js += f'{indent * (dpth+1)}args = args || [];{nl}'
        else:
            p_js = f'{indent * dpth}"{qname.split(":")[-1]}": function(kwargs={{}}, args=[]) {{{nl}'

        def reversible(endpoint: URLPattern) -> bool:
            """
            Not every valid Django URL is reversible, For instance Django doesnt allow mixing
            unnamed and named parameters when reversing a url

            :param endpoint: The URLPattern to test for reversibility
            :return: True if reversible, false otherwise
            """
            num_named = len(endpoint.pattern.regex.groupindex)
            if num_named and num_named != endpoint.pattern.regex.groups:
                return False
            return True

        def add_pattern(endpoint: URLPattern) -> str:  # pylint: disable=R0914,R0912
            """
            Generate code for a URLPattern to be added to the javascript reverse function that
            corresponds to its qualified name.

            :param endpoint: The URLPattern to add
            :return: Javascript code that returns the URL with any arguments substituted if the
                arguments correspond to the URLPattern
            """
            if not reversible(endpoint):
                return f'{indent*(dpth+1)}/* this path is not reversible */'
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
                raise URLGenerationFailed(f'Unrecognized pattern type: {type(endpoint.pattern)}')

            unnamed = endpoint.pattern.regex.groups > 0 and not params
            if params or unnamed:  # pylint: disable=R1702
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
                                mtch = re.search(
                                    endpoint.pattern.regex.pattern.lstrip('^'),
                                    placeholder_url.lstrip('/')
                                )

                            if not mtch:
                                continue  # pragma: no cover - hopefully impossible to get here!
                            url = ''
                            # there might be group matches that aren't part of our kwargs, we go
                            # through this extra work to make sure we aren't subbing spans that
                            # aren't kwargs
                            grp_mp = {
                                idx: var for var, idx in endpoint.pattern.regex.groupindex.items()
                            }
                            replacements = []
                            for idx, value in enumerate(  # pylint: disable=W0612
                                    mtch.groups(),
                                    start=1
                            ):
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
                                elif (
                                        idx in grp_mp and
                                        grp_mp[idx] in kwargs
                                ):  # pragma: no cover - should be impossible for this to eval as F
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
                            if url_idx < len(placeholder_url):
                                url += placeholder_url[url_idx:]
                            opts_str = ",".join([f"'{param}'" for param in kwargs.keys()])
                            if unnamed:
                                quote = '"' if es5 else '`'
                                return (
                                        f'{indent * (dpth + 1)}if (args.length === '
                                        f'{len(placeholders)}){nl}'
                                        f'{indent * (dpth + 2)}'
                                        f'return {quote}/{url.lstrip("/")}{quote};{nl}'
                                )
                            if es5:
                                return (
                                        f'{indent * (dpth + 1)}if (Object.keys(kwargs).length '
                                        f'=== {len(kwargs)} && [{opts_str}].every('
                                        f'function(value) {{ '
                                        f'return kwargs.hasOwnProperty(value);}})){nl}'
                                        f'{indent * (dpth + 2)}return "/{url.lstrip("/")}";{nl}'
                                )
                            return (
                                    f'{indent * (dpth + 1)}if (Object.keys(kwargs).length '
                                    f'=== {len(kwargs)} && '
                                    f'[{opts_str}].every('
                                    f'value => kwargs.hasOwnProperty(value))){nl}'
                                    f'{indent * (dpth + 2)}return `/{url.lstrip("/")}`;{nl}'
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
                    f'args.length === 0){nl}'
                    f'{indent * (dpth + 2)}return "/{reverse(qname).lstrip("/")}";{nl}'
                )
            raise URLGenerationFailed(
                f'Unable to generate url for {qname} with kwargs: '
                f'{params.keys()} using pattern {endpoint}!'
            )

        for pattern in nodes:
            p_js += add_pattern(pattern)

        return (
            f'{p_js}'
            f'{indent*(dpth+1)}throw new TypeError('
            f'"No reversal available for parameters at path: {qname}");{nl}'
            f'{indent*dpth}}},{nl}'
        )

    def write_javascript(
            tree: Tuple[Dict, Dict, Optional[str]],
            namespace: Optional[str] = None,
            parent_qname: str = '',
    ) -> str:
        """
        Walk the tree, writing javascript for URLs indexed by their nested namespaces.

        :param tree: The tree, or branch to build javascript from
        :param namespace: The namespace of this branch
        :param parent_qname: The parent qualified name of the parent of this branch. Can be thought
            of as the path in the tree.
        :return: javascript object containing functions for URLs and objects for namespaces at and
            below this tree (branch)
        """

        j_scrpt = ''

        if namespace:
            parent_qname += f"{':' if parent_qname else ''}{namespace}"

        for name, nodes in tree[1].items():
            j_scrpt += nodes_to_js(
                nodes,
                f"{f'{parent_qname}:' if parent_qname else ''}{name}",
                tree[2]
            )

        if tree[0]:
            for nmsp, branch in tree[0].items():
                dpth = depth + (
                    parent_qname + f':{nmsp}' if parent_qname else ''
                ).count(':') + 1
                j_scrpt += f'{indent*dpth}"{nmsp}": {{{nl}'
                j_scrpt += write_javascript(branch, nmsp, parent_qname)
                j_scrpt += f'{indent*dpth}}},{nl}'

        return j_scrpt

    return SafeString(
        write_javascript(
            prune_tree(
                build_tree(
                    patterns,
                    not includes or '' in includes,
                    ({}, {}, getattr(url_conf, 'app_name', None))
                )
            )[0],
            ''
        )
    )
