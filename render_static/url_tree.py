from django.urls import URLPattern, URLResolver
from abc import (
    ABCMeta,
    abstractmethod
)
from django.conf import settings

import itertools
import re
from importlib import import_module
from types import ModuleType
from typing import Dict, Iterable, Optional, Tuple, Type, Union
from django.urls import URLPattern, reverse
from django.urls.exceptions import NoReverseMatch
from django.urls.resolvers import RegexPattern, RoutePattern
from render_static.exceptions import PlaceholderNotFound, URLGenerationFailed
from render_static.placeholders import (
    resolve_placeholders,
    resolve_unnamed_placeholders,
)


__all__ = ['build_tree', 'URLTreeVisitor', 'SimpleURLWriter', 'ClassURLWriter']


def normalize_ns(namespaces: str) -> Iterable[str]:
    return ':'.join([nmsp for nmsp in namespaces.split(':') if nmsp])


def build_tree(
        url_conf: Optional[Union[ModuleType, str]] = None,
        include: Optional[Iterable[str]] = None,
        exclude: Optional[Iterable[str]] = None
) -> Tuple[Tuple[Dict, Dict, Optional[str]], int]:
    """
    Generate a tree from the url configuration where the branches are namespaces and the leaves are
    collections of URLs registered against fully qualified reversible names.

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

    :param url_conf: The root url module to dump urls from, default: settings.ROOT_URLCONF
    :param include: A list of path names to include, namespaces without path names will be treated
        as every path under the namespace. Default: include everything
    :param exclude: A list of path names to exclude, namespaces without path names will be treated
        as every path under the namespace. Default: exclude nothing
    :return: A tree structure containing the configured URLs
    """

    if url_conf is None:
        url_conf = settings.ROOT_URLCONF

    if isinstance(url_conf, str):
        url_conf = import_module(url_conf)

    patterns = getattr(url_conf, 'urlpatterns', None)
    if patterns is None:
        raise AttributeError(f'{url_conf} has no attribute urlpatterns!')

    includes = []
    excludes = []
    if include:
        includes = [normalize_ns(incl) for incl in include]
    if exclude:
        excludes = [normalize_ns(excl) for excl in exclude]

    return __prune_tree__(
        __build_branch__(
            patterns,
            not includes or '' in includes,
            ({}, {}, getattr(url_conf, 'app_name', None)),
            includes,
            excludes
        )
    )


def __build_branch__(
        nodes: Iterable[URLPattern],
        included: bool,
        branch: Tuple[Dict, Dict, Optional[str]],
        includes: Optional[Iterable[str]],
        excludes: Optional[Iterable[str]],
        namespace: Optional[str] = None,
        qname: str = '',
        app_name: Optional[str] = None
) -> Tuple[Dict, Dict, Optional[str]]:
    """
    Recursively walk the branch and add it's subtree to the larger tree.

    :param nodes: The urls that are leaves of this branch
    :param included: True if this branch has been implicitly included, by includes higher up the
        tree
    :param branch: The branch to build
    :param namespace: the namespace of this branch (if any)
    :param qname: the fully qualified name of the parent branch
    :param app_name: app_name for the branch if any
    :param includes: A list of path names to include, namespaces without path names will be treated
        as every path under the namespace. Names should be normalized.
    :param excludes: A list of path names to exclude, namespaces without path names will be treated
        as every path under the namespace. Names should be normalized.
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

            __build_branch__(
                pattern.url_patterns,
                included or (not includes or ns_qname in includes),
                branch,
                includes,
                excludes,
                namespace=pattern.namespace,
                qname=ns_qname,
                app_name=pattern.app_name
            )

    return branch


def __prune_tree__(
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
            branch, branch_urls = __prune_tree__(branch)
            if branch_urls == 0:
                to_delete.append(nmsp)
            num_urls += branch_urls
        for nmsp in to_delete:
            del tree[0][nmsp]

    return tree, num_urls


class _Substitute:

    arg_ = None

    @property
    def arg(self):
        return self.arg_

    def __init__(self, arg_or_kwarg):
        self.arg_ = arg_or_kwarg


class URLTreeVisitor(metaclass=ABCMeta):

    rendered_ = ''
    level_ = 0
    indent_ = '\t'
    es5_ = False
    nl_ = '\n'

    def __init__(self, **kwargs):
        self.level_ = kwargs.pop('depth', self.level_)
        self.indent_ = kwargs.pop('indent', self.indent_)
        self.es5_ = kwargs.pop('es5', self.es5_)
        self.nl_ = self.nl_ if self.indent_ else ''  # pylint: disable=C0103

    def indent(self, incr=1):
        self.level_ += incr

    def outdent(self, decr=1):
        self.level_ -= decr
        self.level_ = max(0, self.level_)

    @staticmethod
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

    def start_visitation(self):
        yield None

    def end_visitation(self):
        yield None

    def enter_namespace(self, namespace):
        yield None

    def exit_namespace(self, namespace):
        yield None

    def visit_pattern(
            self,
            endpoint: URLPattern,
            qname: str,
            app_name: Optional[str]
    ) -> str:  # pylint: disable=R0914,R0912
        """
        Generate code for a URLPattern to be added to the javascript reverse function that
        corresponds to its qualified name.

        :param endpoint: The URLPattern to add
        :param qname: The fully qualified name of the URL
        :param app_name: The app_name the URLs belong to, if any
        :return: Javascript code that returns the URL with any arguments substituted if the
            arguments correspond to the URLPattern
        """
        if not self.reversible(endpoint):
            return '/* this path is not reversible */'

        # first, pull out any named or unnamed parameters that comprise this pattern
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
            raise URLGenerationFailed(
                f'Unrecognized pattern type: {type(endpoint.pattern)}')

        # does this url have unnamed or named params?
        unnamed = endpoint.pattern.regex.groups > 0 and not params

        # if we have parameters, resolve the placeholders for them
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

                # attempt to reverse the pattern with our list of potential placeholders
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

                        # there might be group matches that aren't part of our kwargs, we go
                        # through this extra work to make sure we aren't subbing spans that
                        # aren't kwargs
                        grp_mp = {
                            idx: var for var, idx in
                            endpoint.pattern.regex.groupindex.items()
                        }
                        replacements = []

                        for idx, value in enumerate(  # pylint: disable=W0612
                                mtch.groups(),
                                start=1
                        ):
                            if unnamed:
                                replacements.append((mtch.span(idx), _Substitute(idx-1)))
                            else:
                                assert(idx in grp_mp and grp_mp[idx] in kwargs)
                                replacements.append((mtch.span(idx), _Substitute(grp_mp[idx])))

                        url_idx = 0
                        path = []
                        for rpl in replacements:
                            while url_idx <= rpl[0][0]:
                                path.append(placeholder_url[url_idx])
                                url_idx += 1
                            path.append(rpl[1])
                            url_idx += (rpl[0][1] - rpl[0][0])
                        if url_idx < len(placeholder_url):
                            path.append(placeholder_url[url_idx:])

                        yield from self.visit_path(path, list(kwargs.keys()))
                        return None

                    except NoReverseMatch:
                        continue
            except PlaceholderNotFound as pnf:
                raise URLGenerationFailed(
                    f'Unable to generate url for {qname} using pattern {endpoint} '
                    f'because: {pnf}'
                ) from pnf
        else:
            # this is a simple url with no params
            yield from self.visit_path([reverse(qname)], [])
            return None

        raise URLGenerationFailed(
            f'Unable to generate url for {qname} with kwargs: '
            f'{params.keys()} using pattern {endpoint}!'
        )

    @abstractmethod
    def enter_path_group(self, qname):
        ...

    @abstractmethod
    def exit_path_group(self, qname):
        ...

    @abstractmethod
    def visit_path(self, path, kwargs):
        ...

    def visit_path_group(
        self,
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
        yield from self.enter_path_group(qname)
        for pattern in nodes:
            yield from self.visit_pattern(pattern, qname, app_name)
        yield from self.exit_path_group(qname)

    def visit_branch(
        self,
        branch: Tuple[Dict, Dict, Optional[str]],
        namespace: Optional[str] = None,
        parent_qname: str = ''
    ):
        """
        Walk the tree, writing javascript for URLs indexed by their nested namespaces.

        :param branch: The tree, or branch to build javascript from
        :param namespace: The namespace of this branch
        :param parent_qname: The parent qualified name of the parent of this branch. Can be thought
            of as the path in the tree.
        :return: javascript object containing functions for URLs and objects for namespaces at and
            below this tree (branch)
        """

        if namespace:
            parent_qname += f"{':' if parent_qname else ''}{namespace}"

        for name, nodes in branch[1].items():
            yield from self.visit_path_group(
                nodes,
                f"{f'{parent_qname}:' if parent_qname else ''}{name}",
                branch[2]
            )

        if branch[0]:
            for nmsp, branch in branch[0].items():
                yield from self.enter_namespace(nmsp)
                yield from self.visit_branch(branch, nmsp, parent_qname)
                yield from self.exit_namespace(nmsp)

    def visit(self, tree):
        for line in self.start_visitation():
            self.write_line(line)

        self.indent()
        for line in self.visit_branch(tree):
            self.write_line(line)
        self.outdent()

        for line in self.end_visitation():
            self.write_line(line)
        return self.rendered_

    def write_line(self, line):
        if line is not None:
            self.rendered_ += f'{self.indent_*self.level_}{line}{self.nl_}'

    def sub_to_str(self, sub):
        if isinstance(sub.arg, int):
            return (
                f'"+args[{sub.arg}].toString()+"' if self.es5_
                else f'${{args[{sub.arg}]}}'
            )
        else:
            return (
                f'"+kwargs["{sub.arg}"].toString()+"' if self.es5_
                else f'${{kwargs["{sub.arg}"]}}'
            )

    def path_join(self, path):
        return ''.join([comp if isinstance(comp, str) else self.sub_to_str(comp) for comp in path])


class SimpleURLWriter(URLTreeVisitor):

    def enter_namespace(self, namespace):
        yield f'"{namespace}": {{'
        self.indent()

    def exit_namespace(self, namespace):
        self.outdent()
        yield '},'

    def enter_path_group(self, qname):
        if self.es5_:
            yield f'"{qname.split(":")[-1]}": function(kwargs, args) {{'
            self.indent()
            yield 'kwargs = kwargs || {};'
            yield 'args = args || [];'
        else:
            yield f'"{qname.split(":")[-1]}": function(kwargs={{}}, args=[]) {{'
            self.indent()

    def exit_path_group(self, qname):
        yield f'throw new TypeError("No reversal available for parameters at path: {qname}");'
        self.outdent()
        yield '},'

    def visit_path(self, path, kwargs):
        """

        :param path: An iterable of the path components, alternating strings and _Substitute
            placeholders for argument substitution
        :param kwargs: The names of the named arguments, if any, for the path
        :return:
        """

        if len(path) == 1:
            yield f'if (Object.keys(kwargs).length === 0 && args.length === 0)'
            self.indent()
            yield f'return "/{path[0].lstrip("/")}";'
            self.outdent()
        elif len(kwargs) == 0:
            nargs = len([comp for comp in path if isinstance(comp, _Substitute)])
            quote = '"' if self.es5_ else '`'
            yield f'if (args.length === {nargs})'
            self.indent()
            yield f'return {quote}/{self.path_join(path).lstrip("/")}{quote};'
            self.outdent()
        else:
            opts_str = ",".join([f"'{param}'" for param in kwargs])
            if self.es5_:
                yield (
                    f'if (Object.keys(kwargs).length '
                    f'=== {len(kwargs)} && [{opts_str}].every('
                    'function(value) { return kwargs.hasOwnProperty(value);}))'
                )
                self.indent()
                yield f'return "/{self.path_join(path).lstrip("/")}";'
                self.outdent()
            else:
                yield (
                    f'if (Object.keys(kwargs).length === {len(kwargs)} && '
                    f'[{opts_str}].every(value => kwargs.hasOwnProperty(value)))'
                )
                self.indent()
                yield f'return `/{self.path_join(path).lstrip("/")}`;'
                self.outdent()


class ClassURLWriter(URLTreeVisitor):

    class_name_ = 'URLResolver'
    raise_on_not_found_ = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.class_name_ = kwargs.pop('class_name', self.class_name_)
        self.raise_on_not_found_ = kwargs.pop('raise_on_not_found', self.raise_on_not_found_)

    def start_visitation(self):
        if self.es5_:
            yield f'{self.class_name_} = function() {{}};'
            yield ''
            yield f'{self.class_name_}.prototype = {{'
            self.indent()
            yield 'match: function(kwargs, args, expected) {'
            self.indent()
            yield 'if (Array.isArray(expected))'
            self.indent()
            yield ('return (Object.keys(kwargs).length === expected.length && '
                   'expected.every(function(value) { return kwargs.hasOwnProperty(value); }))'
            )
            self.outdent()
            yield 'else if (expected)'
            self.indent()
            yield 'return args.length === expected;'
            self.outdent()
            yield 'else'
            self.indent()
            yield 'return Object.keys(kwargs).length === 0 && args.length === 0;'
            self.outdent(2)
            yield '},'
            yield 'reverse: function(qname, kwargs, args) {'
            self.indent()
            yield 'kwargs = kwargs || {};'
            yield 'args = args || [];'
            yield 'let url = this.urls;'
            yield "qname.split(':').forEach(function(ns) {"
            self.indent()
            yield 'if (ns && url) url = url.hasOwnProperty(ns) ? url[ns] : null;'
            self.outdent()
            yield '});'
            yield 'if (url) return url.call(this, kwargs, args);'
            if self.raise_on_not_found_:
                yield 'throw new TypeError("No reversal available for parameters at path: "+qname);'
            self.outdent()
            yield '},'
            yield 'urls: {'
        else:
            yield f'class {self.class_name_} {{'
            self.indent()
            yield ''
            yield 'match(kwargs, args, expected) {'
            self.indent()
            yield 'if (Array.isArray(expected))'
            self.indent()
            yield (
                'return Object.keys(kwargs).length === expected.length && '
                'expected.every(value => kwargs.hasOwnProperty(value));'
            )
            self.outdent()
            yield 'else if (expected)'
            self.indent()
            yield 'return args.length === expected;'
            self.outdent()
            yield 'else'
            self.indent()
            yield 'return Object.keys(kwargs).length === 0 && args.length === 0;'
            self.outdent(2)
            yield '}'
            yield ''
            yield 'reverse(qname, kwargs={}, args=[]) {'
            self.indent()
            yield 'let url = this.urls;'
            yield "for (const ns of qname.split(':')) {"
            self.indent()
            yield 'if (ns && url) url = url.hasOwnProperty(ns) ? url[ns] : null;'
            self.outdent()
            yield '}'
            yield 'if (url) return url(kwargs, args);'
            if self.raise_on_not_found_:
                yield ('throw new TypeError('
                       '`No reversal available for parameters at path: ${qname}`);'
                )
            self.outdent()
            yield '}'
            yield ''
            yield 'urls = {'

    def end_visitation(self):
        yield '}'
        self.outdent()
        yield '};'

    def enter_namespace(self, namespace):
        yield f'"{namespace}": {{'
        self.indent()

    def exit_namespace(self, namespace):
        self.outdent()
        yield '},'

    def enter_path_group(self, qname):
        if self.es5_:
            yield f'"{qname.split(":")[-1]}": function(kwargs, args) {{'
            self.indent()
            yield 'kwargs = kwargs || {};'
            yield 'args = args || [];'
        else:
            yield f'"{qname.split(":")[-1]}": (kwargs={{}}, args=[]) => {{'
            self.indent()

    def exit_path_group(self, qname):
        self.outdent()
        yield '},'

    def visit_path(self, path, kwargs):
        quote = '"' if self.es5_ else '`'
        if len(path) == 1:
            yield f'if (this.match(kwargs, args)) return "/{path[0].lstrip("/")}";'
        elif len(kwargs) == 0:
            nargs = len([comp for comp in path if isinstance(comp, _Substitute)])
            yield (
                f'if (this.match(kwargs, args, {nargs}))'
                f' return {quote}/{self.path_join(path).lstrip("/")}{quote};'
            )
        else:
            opts_str = ",".join([f"'{param}'" for param in kwargs])
            yield (
                f'if (this.match(kwargs, args, [{opts_str}]))'
                f' return {quote}/{self.path_join(path).lstrip("/")}{quote};'
            )
