# pylint: disable=C0302

"""
Utilities, functions and classes for generating JavaScript from Django's url
configuration files.
"""

import itertools
import json
import re
from abc import abstractmethod
from typing import Any, Dict, Generator, Iterable, List, Optional, Tuple, Union

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.template.context import Context
from django.urls import URLPattern, URLResolver, reverse
from django.urls.exceptions import NoReverseMatch
from django.urls.resolvers import LocalePrefixPattern, RegexPattern, RoutePattern

from render_static.exceptions import ReversalLimitHit, URLGenerationFailed
from render_static.placeholders import (
    resolve_placeholders,
    resolve_unnamed_placeholders,
)
from render_static.transpilers.base import ResolvedTranspilerTarget, Transpiler

__all__ = [
    "normalize_ns",
    "build_tree",
    "Substitute",
    "URLTreeVisitor",
    "SimpleURLWriter",
    "ClassURLWriter",
]


def normalize_ns(namespaces: str) -> str:
    """
    Normalizes url names by collapsing multiple `:` characters.
    :param namespaces: The namespace string to normalize
    :return: The normalized version of the url path name
    """
    return ":".join([nmsp for nmsp in namespaces.split(":") if nmsp])


def build_tree(
    patterns: Iterable[URLPattern],
    include: Optional[Iterable[str]] = None,
    exclude: Optional[Iterable[str]] = None,
    app_name: Optional[str] = None,
) -> Tuple[
    Tuple[Dict, Dict, Optional[str], Optional[Union[RegexPattern, RoutePattern]]], int
]:
    """
    Generate a tree from the url configuration where the branches are
    namespaces and the leaves are collections of URLs registered against fully
    qualified reversible names.

    The tree structure will look like this:

    .. code-block::

        [
            { # first dict contains child branches
                'namespace1': [{...}, {...}, 'incl_app_name1', route],
                # no app_name specified for this include
                'namespace2': [{...}, {...}, None, route]
            },
            {
                # URLPatterns for this qname
                'url_name1': [URLPattern, URLPattern, ...]
                'url_name2': [URLPattern, ...]
            },
            None, # no root app_name
            RegexPattern or RoutePattern # if one exists
        ]

    :param patterns: The list of URLPatterns to transpile into a javascript
        resolver
    :param include: A list of path names to include, namespaces without path
        names will be treated as every path under the namespace.
        Default: include everything
    :param exclude: A list of path names to exclude, namespaces without path
        names will be treated as every path under the namespace.
        Default: exclude nothing
    :param app_name: The app name (if any) of the provided patterns.
    :return: A tree structure containing the configured URLs
    """
    includes = []
    excludes = []
    if include:
        includes = [normalize_ns(incl) for incl in include]
    if exclude:
        excludes = [normalize_ns(excl) for excl in exclude]

    return _prune_tree(
        _build_branch(
            patterns,
            not includes or "" in includes,
            ({}, {}, app_name, None),
            includes,
            excludes,
        )
    )


def _build_branch(
    nodes: Iterable[Union[URLPattern, URLResolver]],
    included: bool,
    branch: Tuple[
        Dict, Dict, Optional[str], Optional[Union[RegexPattern, RoutePattern]]
    ],
    includes: Iterable[str],
    excludes: Iterable[str],
    namespace: Optional[str] = None,
    qname: str = "",
    app_name: Optional[str] = None,
    route_pattern: Optional[Union[RegexPattern, RoutePattern]] = None,
) -> Tuple[Dict, Dict, Optional[str], Optional[Union[RegexPattern, RoutePattern]]]:
    """
    Recursively walk the branch and add it's subtree to the larger tree.

    :param nodes: The urls that are leaves of this branch
    :param included: True if this branch has been implicitly included, by
        includes higher up the tree
    :param branch: The branch to build
    :param namespace: the namespace of this branch (if any)
    :param qname: the fully qualified name of the parent branch
    :param app_name: app_name for the branch if any
    :param includes: A list of path names to include, namespaces without path
        names will be treated as every path under the namespace. Names should
        be normalized.
    :param excludes: A list of path names to exclude, namespaces without path
        names will be treated as every path under the namespace. Names should
        be normalized.
    :return:
    """
    if namespace:
        branch[0].setdefault(namespace, [{}, {}, app_name, route_pattern])
        branch = branch[0][namespace]

    for pattern in nodes:
        if isinstance(pattern, URLPattern):
            name = getattr(pattern, "name", None)
            if name is None:
                continue

            url_qname = f"{f'{qname}:' if qname else ''}{pattern.name}"

            # if we aren't implicitly included we must be explicitly included
            # and not explicitly excluded - note if we were implicitly excluded
            # we wouldn't get this far
            if (
                not included
                and url_qname not in includes
                or (excludes and url_qname in excludes)
            ):
                continue

            branch[1].setdefault(pattern.name, []).append(pattern)

        elif isinstance(pattern, URLResolver):
            ns_qname = qname
            if pattern.namespace:
                ns_qname += f"{':' if qname else ''}{pattern.namespace}"

            if excludes and ns_qname in excludes:
                continue

            _build_branch(
                pattern.url_patterns,
                included or (not includes or ns_qname in includes),
                branch,
                includes,
                excludes,
                namespace=pattern.namespace,
                qname=ns_qname,
                app_name=pattern.app_name,
                route_pattern=(
                    pattern.pattern
                    if (isinstance(pattern.pattern, (RoutePattern, RegexPattern)))
                    else None
                ),
            )
        else:  # pragma: no cover
            raise NotImplementedError(f"Unknown pattern type: {type(pattern)}")

    return branch


def _prune_tree(
    tree: Tuple[Dict, Dict, Optional[str], Optional[Union[RegexPattern, RoutePattern]]],
) -> Tuple[
    Tuple[Dict, Dict, Optional[str], Optional[Union[RegexPattern, RoutePattern]]], int
]:
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
            branch, branch_urls = _prune_tree(branch)
            if branch_urls == 0:
                to_delete.append(nmsp)
            num_urls += branch_urls
        for nmsp in to_delete:
            del tree[0][nmsp]

    return tree, num_urls


class Substitute:
    """
    A placeholder representing a substitution, either by a positional argument
    or a named argument in a url path string.
    """

    arg_: Optional[Union[str, int]] = None

    @property
    def arg(self) -> Optional[Union[str, int]]:
        """
        :return: Either the position of the positional argument to substitute
            in, or the name of the named parameter
        """
        return self.arg_

    def __init__(self, arg_or_kwarg: Union[str, int]) -> None:
        """
        :param arg_or_kwarg: Either an integer index corresponding to the argument
            to substitute for this placeholder or the string name of the argument
            to substitute at this placeholder.
        """
        self.arg_ = arg_or_kwarg

    def to_str(self) -> str:
        """
        Converts a _Substitution object placeholder into JavaScript code that
        substitutes the positional or named arguments in the string.

        :return: The JavaScript as a string
        """
        if isinstance(self.arg, int):
            return f"${{args[{self.arg}]}}"
        return f'${{kwargs["{self.arg}"]}}'


class BaseURLTranspiler(Transpiler):
    """
    A base class for URL transpilers that includes targets with 'urlpatterns'
    attributes that contain a list of URLPattern and URLResolver objects.
    """

    def include_target(self, target: ResolvedTranspilerTarget) -> bool:
        """
        Only transpile artifacts that have url pattern/resolver lists in them.

        :param target:
        :return:
        """
        if hasattr(target, "urlpatterns"):
            for pattern in getattr(target, "urlpatterns"):
                if not isinstance(pattern, (URLResolver, URLPattern)):
                    return False
            return True
        return False

    @abstractmethod
    def visit(
        self, target: ResolvedTranspilerTarget, is_last: bool, is_final: bool
    ) -> Generator[Optional[str], None, None]:
        """
        Deriving url transpilers must implement this method.

        :param target: A transpiler target that has a 'urlpatterns' attribute
            containing an Iterable of URLPatterns.
        :param is_last: True if this is the last urlpattern list to transpile
            at this level.
        :param is_final: True if this is the last urlpattern that will be
            visited at all.
        :yield: JavaScript lines
        """


class URLTreeVisitor(BaseURLTranspiler):
    """
    An abstract base class for JavaScript generators of url reversal code.
    This class defines a visitation design pattern that deriving classes may
    extend.

    Most of the difficult work of walking the URL tree is handled by this base
    class. Deriving classes are free to focus on generating Javascript, but may
    override the tree walking and url reversal logic if they so desire.

    To use this class derive from it and implement its abstract visitation
    methods. Visitor methods should `yield` lines of JavaScript code and set
    the indentation levels by calling indent() and outdent(). Each yielded line
    is written by the base class using the configured indentation/newline
    options. When None is yielded or returned, nothing will be written. To
    write a newline and nothing else, simply yield or return an empty string.
    """

    include_: Optional[Iterable[str]] = None
    exclude_: Optional[Iterable[str]] = None

    @property
    def context(self) -> Dict[str, Any]:
        """
        The template render context passed to overrides. In addition to
        :attr:`render_static.transpilers.Transpiler.context`.
        This includes:

            - **include**: The list of include pattern strings
            - **exclude**: The list of exclude pattern strings
        """
        return {
            **BaseURLTranspiler.context.fget(self),  # type: ignore
            "include": self.include_,
            "exclude": self.exclude_,
        }

    def __init__(
        self,
        include: Optional[Iterable[str]] = include_,
        exclude: Optional[Iterable[str]] = exclude_,
        **kwargs,
    ):
        """
        :param include: A list of path names to include, namespaces without
            path names will be treated as every path under the namespace.
            Default: include everything
        :param exclude: A list of path names to exclude, namespaces without
            path names will be treated as every path under the namespace.
            Default: exclude nothing
        :param kwargs: Set of configuration parameters, see
            :class:`~render_static.transpilers.base.Transpiler` params
        """
        self.include_ = include
        self.exclude_ = exclude
        super().__init__(**kwargs)

    @abstractmethod
    def enter_namespace(self, namespace) -> Generator[Optional[str], None, None]:
        """
        Walking down the url tree, the visitor has entered the given namespace.
        Deriving visitors must implement.

        :param namespace: namespace string
        :yield: JavaScript, if any, that should be placed at namespace
            visitation start
        """

    @abstractmethod
    def exit_namespace(self, namespace) -> Generator[Optional[str], None, None]:
        """
        Walking down the url tree, the visitor has exited the given namespace.
        Deriving visitors must implement.

        :param namespace: namespace string
        :yield: JavaScript, if any, that should be placed at namespace
            visitation exit
        """

    def visit_pattern(
        self,
        endpoint: URLPattern,
        qname: str,
        app_name: Optional[str],
        route: List[RoutePattern],
        num_patterns: int,
    ) -> Generator[Optional[str], None, None]:
        """
        Visit a pattern. Translates the pattern into a path component string
        which may contain substitution objects. This function will call
        visit_path once the path components have been constructed.

        The JavaScript url reversal code guarantees that it will always return
        the same paths as Django's reversal calls. It does this by using those
        same calls to create the path components. The registered placeholders
        for the url pattern name are used for path reversal. This technique
        forms the bedrock of the reliability of the JavaScript url reversals.
        Do not change it lightly!

        :param endpoint: The :class:`django.urls.URLPattern` to add
        :param qname: The fully qualified name of the URL
        :param app_name: The app_name the URLs belong to, if any
        :param route: The list of RoutePatterns above this URL
        :yield: JavaScript LoC that reverse the pattern
        :return: JavaScript comment if non-reversible
        :except URLGenerationFailed: When no successful placeholders are found
            for the given pattern
        """

        # first, pull out any named or unnamed parameters that comprise this
        # pattern
        def get_params(
            pattern: Union[RoutePattern, RegexPattern, LocalePrefixPattern],
        ) -> Dict[str, Any]:
            if isinstance(pattern, (RoutePattern, LocalePrefixPattern)):
                return {
                    var: {"converter": converter.__class__, "app_name": app_name}
                    for var, converter in pattern.converters.items()
                }
            return {
                var: {"app_name": app_name} for var in pattern.regex.groupindex.keys()
            }

        params = get_params(endpoint.pattern)

        for rt_pattern in route:
            params = {**params, **get_params(rt_pattern)}

        # does this url have unnamed or named params?
        unnamed = 0
        if not params and endpoint.pattern.regex.groups > 0:
            unnamed = endpoint.pattern.regex.groups

        composite_regex = re.compile(
            "".join(
                [
                    pattern.regex.pattern.lstrip("^").rstrip("$")
                    for pattern in [*route, endpoint.pattern]
                ]
            )
        )

        # if we have parameters, resolve the placeholders for them
        if params or unnamed or endpoint.default_args:
            if unnamed:
                resolved_placeholders = itertools.product(
                    *resolve_unnamed_placeholders(
                        url_name=endpoint.name or "", nargs=unnamed, app_name=app_name
                    ),
                )
                non_capturing = str(endpoint.pattern.regex).count("(?:")
                if non_capturing > 0:
                    # handle the corner case where there might be some
                    # non-capturing groups driving up the number of expected
                    # args
                    resolved_placeholders = itertools.chain(  # type: ignore
                        resolved_placeholders,
                        *resolve_unnamed_placeholders(
                            url_name=endpoint.name or "",
                            nargs=unnamed - non_capturing,
                            app_name=app_name,
                        ),
                    )
            else:
                resolved_placeholders = itertools.product(
                    *[
                        resolve_placeholders(param, **lookup)
                        for param, lookup in params.items()
                    ]
                )

            # attempt to reverse the pattern with our list of potential
            # placeholders
            tries = 0
            limit = getattr(settings, "RENDER_STATIC_REVERSAL_LIMIT", 2**15)
            for placeholders in resolved_placeholders:
                # The downside of the guess and check mechanism is that its an
                # O(n^p) operation where n is the number of candidate
                # placeholders and p is the number of url arguments - we put an
                # explicit bound on the complexity of this loop here that
                # errors out and indicates to the user they should register
                # more specific placeholders. Placeholders are tried in order
                # of specificity so having specific placeholders registered
                # will ensure a quick and successful exit of this process
                if tries > limit:
                    raise ReversalLimitHit(
                        f"The maximum number of reversal attempts ({limit}) "
                        f"has been hit attempting to reverse pattern "
                        f"{endpoint}. Please register more specific "
                        f"placeholders."
                    )
                tries += 1
                kwargs = {
                    param: placeholders[idx] for idx, param in enumerate(params.keys())
                }
                try:
                    if unnamed:
                        placeholder_url = reverse(qname, args=placeholders)
                    else:
                        placeholder_url = reverse(
                            qname, kwargs={**kwargs, **(endpoint.default_args or {})}
                        )
                except (NoReverseMatch, TypeError, AttributeError, ValueError):
                    continue

                replacements = []

                mtch = composite_regex.search(placeholder_url.lstrip("/"))

                if mtch:
                    # there might be group matches that aren't part of
                    # our kwargs, we go through this extra work to
                    # make sure we aren't subbing spans that aren't
                    # kwargs
                    grp_mp = {
                        idx: var for var, idx in composite_regex.groupindex.items()
                    }

                    for idx, value in enumerate(mtch.groups(), start=1):
                        if unnamed:
                            replacements.append((mtch.span(idx), Substitute(idx - 1)))
                        else:
                            # if the regex has non-capturing groups we
                            # need to filter those out
                            if idx in grp_mp:
                                replacements.append(
                                    (mtch.span(idx), Substitute(grp_mp[idx]))
                                )

                    url_idx = 0
                    path: List[Union[str, Substitute]] = []
                    for rpl in replacements:
                        while url_idx <= rpl[0][0]:
                            path.append(placeholder_url[url_idx])
                            url_idx += 1
                        path.append(rpl[1])
                        url_idx += rpl[0][1] - rpl[0][0]
                    if url_idx < len(placeholder_url):
                        path.append(placeholder_url[url_idx:])

                    yield from self.visit_path(
                        path,
                        list(kwargs.keys()),
                        endpoint.default_args if num_patterns > 1 else None,
                    )

                else:
                    # if we're here it means this path was overridden
                    # further down the tree
                    yield (
                        f"/* Path {composite_regex.pattern} overruled "
                        "with: "
                        + (
                            f"args={unnamed} */"
                            if unnamed
                            else f"kwargs={list(params.keys())} */"
                        )
                    )
                return

        else:
            # this is a simple url with no params
            if not composite_regex.search(reverse(qname).lstrip("/")):
                yield f"/* Path '{composite_regex.pattern}' overruled */"
            else:
                yield from self.visit_path([reverse(qname)], [])
            return

        # Django is unable to reverse paths with named and unnamed arguments,
        # in those instances don't fail the entire reversal - just leave a
        # breadcrumb
        if unnamed != endpoint.pattern.regex.groups:
            unaccounted = endpoint.pattern.regex.groups - len(
                endpoint.pattern.regex.groupindex
            )
            if unaccounted > 0:
                if unaccounted - str(endpoint.pattern.regex).count("(?:") > 0:
                    yield "/* this path may not be reversible */"
                    return

        raise URLGenerationFailed(
            f"Unable to generate url for {qname} with {unnamed} arguments "
            if unnamed
            else f"Unable to generate url for {qname} with kwargs: "
            f"{params} using pattern {endpoint}! You may need to register "
            f"placeholders for this url's arguments"
        )

    @abstractmethod
    def init_visit(self) -> Generator[Optional[str], None, None]:
        """
        Called just before visit() is called on a target urlpattern collection.

        :yield: Code that should be placed at the start of each visitation.
        """

    @abstractmethod
    def close_visit(self) -> Generator[Optional[str], None, None]:
        """
        Called just after visit() is called on a target urlpattern collection.

        :yield: Code that should be placed at the end of each visitation.
        """

    @abstractmethod
    def enter_path_group(self, qname: str) -> Generator[Optional[str], None, None]:
        """
        Visit one or more path(s) all referred to by the same fully qualified
        name. Deriving classes must implement.

        :param qname: The fully qualified name of the path group
        :yield: JavaScript that should placed at the start of each path group.
        """

    @abstractmethod
    def exit_path_group(self, qname: str) -> Generator[Optional[str], None, None]:
        """
        End visitation to one or more path(s) all referred to by the same fully
        qualified name. Deriving classes must implement.

        :param qname: The fully qualified name of the path group
        :yield: JavaScript that should placed at the end of each path group.
        """

    @abstractmethod
    def visit_path(
        self,
        path: List[Union[Substitute, str]],
        kwargs: List[str],
        defaults: Optional[Dict[str, Any]] = None,
    ) -> Generator[Optional[str], None, None]:
        """
        Visit a singular realization of a path into components. This is called
        by visit_pattern and deriving classes must implement.

        :param path: The path components making up the URL. An iterable
            containing strings and placeholder substitution objects. The
            _Substitution objects represent the locations where either
            positional or named arguments should be swapped into the path.
            Strings and substitutions will always alternate.
        :param kwargs: The list of named arguments present in the path, if any
        :param defaults: Any default kwargs specified on the path definition
        :yield: JavaScript that should handle the realized path.
        """

    def visit_path_group(
        self,
        nodes: List[URLPattern],
        qname: str,
        app_name: Optional[str] = None,
        route: Optional[List[RoutePattern]] = None,
    ) -> Generator[Optional[str], None, None]:
        """
        Convert a list of URLPatterns all corresponding to the same qualified
        name to javascript.

        :param nodes: The list of URLPattern objects
        :param qname: The fully qualified name of all the URLs
        :param app_name: The app_name the URLs belong to, if any
        :param route: The list of RoutePatterns above this url
        :return: A javascript function that reverses the URLs based on kwarg or
            arg inputs
        """
        yield from self.enter_path_group(qname)

        def impl() -> Generator[Optional[str], None, None]:
            for pattern in reversed(nodes):
                yield from self.visit_pattern(
                    pattern, qname, app_name, route or [], num_patterns=len(nodes)
                )

        if qname in self.overrides_:
            yield from self.transpile_override(
                qname,
                impl(),
                {
                    "qname": qname,
                    "app_name": app_name,
                    "route": route,
                    "patterns": nodes,
                    "num_patterns": len(nodes),
                },
            )
        else:
            yield from impl()

        yield from self.exit_path_group(qname)

    def visit_branch(
        self,
        branch: Tuple[
            Dict, Dict, Optional[str], Optional[Union[RegexPattern, RoutePattern]]
        ],
        namespace: Optional[str] = None,
        parent_qname: str = "",
        route: Optional[List[RoutePattern]] = None,
    ) -> Generator[Optional[str], None, None]:
        """
        Walk the tree, writing javascript for URLs indexed by their nested
        namespaces.

        :param branch: The tree, or branch to build javascript from
        :param namespace: The namespace of this branch
        :param parent_qname: The parent qualified name of the parent of this
            branch. Can be thought of as the path in the tree.
        :param route: The list of RoutePatterns above this branch
        :return: javascript object containing functions for URLs and objects
            for namespaces at and below this tree (branch)
        """
        route = route or []
        if namespace:
            parent_qname += f"{':' if parent_qname else ''}{namespace}"

        for name in reversed(list(branch[1].keys())):
            nodes = branch[1][name]
            yield from self.visit_path_group(
                nodes,
                f"{f'{parent_qname}:' if parent_qname else ''}{name}",
                branch[2],
                route,
            )

        if branch[0]:
            for nmsp in reversed(list(branch[0].keys())):
                brch = branch[0][nmsp]
                yield from self.enter_namespace(nmsp)
                yield from self.visit_branch(
                    brch, nmsp, parent_qname, [*route, *([brch[3]] if brch[3] else [])]
                )
                yield from self.exit_namespace(nmsp)

    def visit(
        self, target: ResolvedTranspilerTarget, is_last: bool, is_final: bool
    ) -> Generator[Optional[str], None, None]:
        """
        Visit the nodes of the URL tree, yielding JavaScript where needed.

        :param target: A transpiler target that has a 'urlpatterns' attribute
            containing an Iterable of URLPatterns.
        :param is_last: True if this is the last urlpattern list to transpile
            at this level.
        :param is_final: True if this is the last urlpattern that will be
            visited at all.
        :yield: JavaScript lines
        """
        yield from self.init_visit()
        self.indent()
        yield from self.visit_branch(
            build_tree(
                patterns=getattr(target, "urlpatterns"),
                include=self.include_,
                exclude=self.exclude_,
                app_name=getattr(target, "app_name", None),
            )[0]
        )
        self.outdent()
        yield from self.close_visit()

    def path_join(self, path: List[Union[Substitute, str]]) -> str:
        """
        Combine a list of path components into a singular JavaScript
        substitution string.

        :param path: The path components to collapse
        :return: The JavaScript substitution code that will realize a path with
            its arguments
        """
        return "".join(
            [comp if isinstance(comp, str) else comp.to_str() for comp in path]
        )


class SimpleURLWriter(URLTreeVisitor):
    """
    A URLTreeVisitor that produces a JavaScript object where the keys are the
    path namespaces and names and the values are functions that accept
    positional and named arguments and return paths.

    This visitor accepts several additional parameters on top of the base
    parameters. To use this visitor you may call it like so:

    .. code-block:: js+django

        const urls = {
            {% urls_to_js raise_on_not_found=False %}
        };

    This will produce JavaScript you may invoke like so:

    ..code-block::

        urls.namespace.path_name({'arg1': 1, 'arg2': 'a'});

    In addition to the base parameters the configuration parameters that
    control the JavaScript output include:

        * *raise_on_not_found*
            Raise a TypeError if no reversal for a url pattern is found,
            default: True
    """

    raise_on_not_found_ = True

    @property
    def context(self) -> Dict[str, Any]:
        """
        The template render context passed to overrides. In addition to
        :attr:`render_static.transpilers.urls_to_js.URLTreeVisitor.context`.
        This includes:

            - **raise_on_not_found**: Boolean, True if an exception should be
              raised when no reversal is found, default: True
        """
        return {
            **URLTreeVisitor.context.fget(self),  # type: ignore
            "raise_on_not_found": self.raise_on_not_found_,
        }

    def __init__(self, **kwargs) -> None:
        """
        :param kwargs: Set of configuration parameters, see also
            :meth:`URLTreeVisitor <render_static.transpilers.urls_to_js.URLTreeVisitor.__init__>`
            params
        """
        super().__init__(**kwargs)
        self.raise_on_not_found_ = kwargs.pop(
            "raise_on_not_found", self.raise_on_not_found_
        )

    def init_visit(self) -> Generator[Optional[str], None, None]:
        """
        No header required.

        :yield: nothing
        """
        yield None

    def close_visit(self) -> Generator[Optional[str], None, None]:
        """
        No header required.

        :yield: nothing
        """
        for _, override in self.overrides_.items():
            yield from override.transpile(Context(self.context))

    def enter_namespace(self, namespace: str) -> Generator[Optional[str], None, None]:
        """
        Start the namespace object.

        :param namespace: The name of the current part of the namespace we're
            visiting.
        :yield: JavaScript starting the namespace object structure.
        """
        yield f'"{namespace}": {{'
        self.indent()

    def exit_namespace(self, namespace: str) -> Generator[Optional[str], None, None]:
        """
        End the namespace object.

        :param namespace: The name of the current part of the namespace we're
            visiting.
        :yield: JavaScript ending the namespace object structure.
        """
        self.outdent()
        yield "},"

    def enter_path_group(self, qname: str) -> Generator[Optional[str], None, None]:
        """
        Start of the reversal function for a collection of paths of the given
        qname.

        :param qname: The fully qualified path name being reversed
        :yield: LoC for the start out of the JavaScript reversal function
        """
        yield f'"{qname.split(":")[-1]}": (options={{}}, args=[]) => {{'
        self.indent()
        yield "const kwargs = ((options.kwargs || null) || options) || {};"
        yield "args = ((options.args || null) || args) || [];"

    def exit_path_group(self, qname: str) -> Generator[Optional[str], None, None]:
        """
        Close out the function for the given qname. If we're configured to
        throw an exception if no path reversal was found, we do that here
        because all options have already been exhausted.

        :param qname: The fully qualified path name being reversed
        :yield: LoC for the close out of the JavaScript reversal function
        """
        if self.raise_on_not_found_:
            yield (
                f'throw new TypeError("No reversal available for '
                f'parameters at path: {qname}");'
            )
        self.outdent()
        yield "},"

    def visit_path(
        self,
        path: List[Union[Substitute, str]],
        kwargs: List[str],
        defaults: Optional[Dict[str, Any]] = None,
    ) -> Generator[Optional[str], None, None]:
        """
        Convert a list of path components into JavaScript reverse function. The
        JS must determine if the passed named or positional arguments match
        this particular pattern and if so return the path with those arguments
        substituted.

        :param path: An iterable of the path components, alternating strings
            and Substitute placeholders for argument substitution
        :param kwargs: The names of the named arguments, if any, for the path
        :param defaults: Any default kwargs specified path definition
        :yield: The JavaScript lines of code
        """
        if len(path) == 1:
            yield "if (Object.keys(kwargs).length === 0 && args.length === 0)"
            self.indent()
            yield f'return "/{path[0].lstrip("/")}";'  # type: ignore
            self.outdent()
        elif len(kwargs) == 0:
            nargs = len([comp for comp in path if isinstance(comp, Substitute)])
            quote = "`"
            yield f"if (args.length === {nargs})"
            self.indent()
            yield f"return {quote}/{self.path_join(path).lstrip('/')}{quote};"
            self.outdent()
        else:
            opts_str = ",".join([self.to_javascript(param) for param in kwargs])
            yield (
                f"if (Object.keys(kwargs).length === {len(kwargs)} && "
                f"[{opts_str}].every(value => "
                f"kwargs.hasOwnProperty(value)))"
            )
            self.indent()
            yield f"return `/{self.path_join(path).lstrip('/')}`;"
            self.outdent()


class ClassURLWriter(URLTreeVisitor):
    """
    A visitor that produces a JavaScript class with a reverse() function
    directly analogous to Django's url :func:`django.urls.reverse` function.

    This is not the default visitor for the :templatetag:`urls_to_js` tag, but its
    probably the one you want. It accepts several additional parameters on top of the
    base parameters. To use this visitor you may call it like so:

    .. code-block:: js+django

        {% urls_to_js
            visitor="render_static.transpilers.ClassURLWriter"
            class_name='URLResolver'
            indent=' '
        %}

    This will produce JavaScript you may invoke like so:

    .. code-block::

        const urls = new URLResolver();
        urls.reverse('namespace:path_name', {'arg1': 1, 'arg2': 'a'});

    In addition to the base parameters the configuration parameters that
    control the JavaScript output include:

        * *class_name*
            The name of the JavaScript class to use: default: URLResolver
        * *raise_on_not_found*
            Raise a TypeError if no reversal for a url pattern is found,
            default: True
        * *export*
            The generated JavaScript file will include an export statement
            for the generated class.
            default: False
    """

    class_name_ = "URLResolver"
    raise_on_not_found_ = True
    export_ = False

    @property
    def context(self):
        """
        The template render context passed to overrides. In addition to
        :attr:`render_static.transpilers.urls_to_js.URLTreeVisitor.context`.
        This includes:

            - **class_name**: The name of the JavaScript class
            - **raise_on_not_found**: Boolean, True if an exception should be
              raised when no reversal is found, default: True
        """
        return {
            **URLTreeVisitor.context.fget(self),  # type: ignore
            "class_name": self.class_name_,
            "raise_on_not_found": self.raise_on_not_found_,
        }

    def __init__(self, **kwargs) -> None:
        """
        :param kwargs: Set of configuration parameters, see also
            :meth:`URLTreeVisitor.__init__` params
        """
        super().__init__(**kwargs)
        self.class_name_ = kwargs.pop("class_name", self.class_name_)
        self.raise_on_not_found_ = kwargs.pop(
            "raise_on_not_found", self.raise_on_not_found_
        )
        self.export_ = kwargs.pop("export", self.export_)

    def class_jdoc(self) -> Generator[Optional[str], None, None]:
        """
        The docstring for the class.
        :yield: The JavaScript jdoc comment lines
        """
        for comment_line in """
        /**
         * A url resolver class that provides an interface very similar to 
         * Django's reverse() function. This interface is nearly identical to 
         * reverse() with a few caveats:
         *
         *  - Python type coercion is not available, so care should be taken to
         *      pass in argument inputs that are in the expect string format.
         *  - Not all reversal behavior can be replicated but these are corner 
         *      cases that are not likely to be correct url specification to 
         *      begin with.
         *  - The reverse function also supports a query option to include url
         *      query parameters in the reversed url.
         *
         * @class
         */""".split("\n"):
            yield comment_line[8:]

    def constructor_jdoc(self) -> Generator[Optional[str], None, None]:
        """
        The docstring for the constructor.
        :yield: The JavaScript jdoc comment lines
        """
        for comment_line in """
        /**
         * Instantiate this url resolver.
         *
         * @param {Object} options - The options object.
         * @param {string} options.namespace - When provided, namespace will
         *     prefix all reversed paths with the given namespace.
         */""".split("\n"):
            yield comment_line[8:]

    def match_jdoc(self) -> Generator[Optional[str], None, None]:
        """
        The docstring for the match function.
        :yield: The JavaScript jdoc comment lines
        """
        for comment_line in """
        /**
         * Given a set of args and kwargs and an expected set of arguments and
         * a default mapping, return True if the inputs work for the given set.
         *
         * @param {Object} kwargs - The object holding the reversal named 
         *     arguments.
         * @param {string[]} args - The array holding the positional reversal 
         *     arguments.
         * @param {string[]} expected - An array of expected arguments.
         * @param {Object.<string, string>} defaults - An object mapping 
         *     default arguments to their values.
         */""".split("\n"):
            yield comment_line[8:]

    def reverse_jdoc(self) -> Generator[Optional[str], None, None]:
        """
        The docstring for the reverse function.
        :yield: The JavaScript jdoc comment lines
        """
        for comment_line in """
        /**
         * Reverse a Django url. This method is nearly identical to Django's
         * reverse function, with an additional option for URL parameters. See
         * the class docstring for caveats.
         *
         * @param {string} qname - The name of the url to reverse. Namespaces
         *   are supported using `:` as a delimiter as with Django's reverse.
         * @param {Object} options - The options object.
         * @param {string} options.kwargs - The object holding the reversal 
         *   named arguments.
         * @param {string[]} options.args - The array holding the reversal 
         *   positional arguments.
         * @param {Object.<string, string|string[]>} options.query - URL query
         *   parameters to add to the end of the reversed url.
         */""".split("\n"):
            yield comment_line[8:]

    def constructor(self) -> Generator[Optional[str], None, None]:
        """
        The constructor() function.
        :yield: The JavaScript jdoc comment lines and constructor() function.
        """

        def impl() -> Generator[str, None, None]:
            """constructor default implementation"""
            yield "this.options = options || {};"
            yield 'if (this.options.hasOwnProperty("namespace")) {'
            self.indent()
            yield "this.namespace = this.options.namespace;"
            yield 'if (!this.namespace.endsWith(":")) {'
            self.indent()
            yield 'this.namespace += ":";'
            self.outdent()
            yield "}"
            self.outdent()
            yield "} else {"
            self.indent()
            yield 'this.namespace = "";'
            self.outdent()
            yield "}"

        if "constructor" in self.overrides_:
            yield from self.transpile_override("constructor", impl())
        else:
            yield from self.constructor_jdoc()
            yield "constructor(options=null) {"
            self.indent()
            yield from impl()
            self.outdent()
            yield "}"

    def match(self) -> Generator[Optional[str], None, None]:
        """
        The #match() function.
        :yield: The JavaScript jdoc comment lines and #match() function.
        """

        def impl() -> Generator[str, None, None]:
            """match default implementation"""
            yield "if (defaults) {"
            self.indent()
            yield "kwargs = Object.assign({}, kwargs);"
            yield "for (const [key, val] of Object.entries(defaults)) {"
            self.indent()
            yield "if (kwargs.hasOwnProperty(key)) {"
            self.indent()
            # there was a change in Django 4.1 that seems to coerce kwargs
            # given to the default kwarg type of the same name if one
            # exists for the purposes of reversal. Thus 1 will == '1'
            # In javascript we attempt string conversion and hope for the
            # best. In 4.1 given kwargs will also override default kwargs
            # for kwargs the reversal is expecting. This seems to have
            # been a byproduct of the differentiation of captured_kwargs
            # and extra_kwargs - that this wasn't caught in Django's CI is
            # evidence that previous behavior wasn't considered spec.
            yield (
                "if (kwargs[key] !== val && "
                "JSON.stringify(kwargs[key]) !== JSON.stringify(val) "
                "&& !expected.includes(key)) "
                "{ return false; }"
            )
            yield "if (!expected.includes(key)) { delete kwargs[key]; }"
            self.outdent()
            yield "}"
            self.outdent()
            yield "}"
            self.outdent()
            yield "}"
            yield "if (Array.isArray(expected)) {"
            self.indent()
            yield (
                "return Object.keys(kwargs).length === expected.length && "
                "expected.every(value => kwargs.hasOwnProperty(value));"
            )
            self.outdent()
            yield "} else if (expected) {"
            self.indent()
            yield "return args.length === expected;"
            self.outdent()
            yield "} else {"
            self.indent()
            yield "return Object.keys(kwargs).length === 0 && args.length === 0;"
            self.outdent()
            yield "}"

        if "#match" in self.overrides_:
            yield from self.transpile_override("#match", impl())
        else:
            yield from self.match_jdoc()
            yield "#match(kwargs, args, expected, defaults={}) {"
            self.indent()
            yield from impl()
            self.outdent()
            yield "}"

    def reverse(self) -> Generator[Optional[str], None, None]:
        """
        The reverse() function.
        :yield: The JavaScript jdoc comment lines and reverse() function.
        """

        def impl() -> Generator[str, None, None]:
            """reverse default implementation"""
            yield "if (this.namespace) {"
            self.indent()
            yield ('qname = `${this.namespace}${qname.replace(this.namespace, "")}`;')
            self.outdent()
            yield "}"
            yield "const kwargs = options.kwargs || {};"
            yield "const args = options.args || [];"
            yield "const query = options.query || {};"
            yield "let url = this.urls;"
            yield "for (const ns of qname.split(':')) {"
            self.indent()
            yield "if (ns && url) { url = url.hasOwnProperty(ns) ? url[ns] : null; }"
            self.outdent()
            yield "}"
            yield "if (url) {"
            self.indent()
            yield "let pth = url(kwargs, args);"
            yield 'if (typeof pth === "string") {'
            self.indent()
            yield "if (Object.keys(query).length !== 0) {"
            self.indent()
            yield "const params = new URLSearchParams();"
            yield "for (const [key, value] of Object.entries(query)) {"
            self.indent()
            yield "if (value === null || value === '') continue;"
            yield (
                "if (Array.isArray(value)) value.forEach(element => "
                "params.append(key, element));"
            )
            yield "else params.append(key, value);"
            self.outdent()
            yield "}"
            yield "const qryStr = params.toString();"
            yield r"if (qryStr) return `${pth.replace(/\/+$/, '')}?${qryStr}`;"
            self.outdent()
            yield "}"
            yield "return pth;"
            self.outdent()
            yield "}"
            self.outdent()
            yield "}"
            if self.raise_on_not_found_:
                yield (
                    "throw new TypeError("
                    "`No reversal available for parameters at path: "
                    "${qname}`);"
                )

        if "reverse" in self.overrides_:
            yield from self.transpile_override("reverse", impl())
        else:
            yield from self.reverse_jdoc()
            yield "reverse(qname, options={}) {"
            self.indent()
            yield from impl()
            self.outdent()
            yield "}"

    def init_visit(
        self,
    ) -> Generator[Optional[str], None, None]:
        """
        Start the tree visitation - this is where we write out all the common
        class code.

        :yield: JavaScript LoC for the reversal class
        """
        yield from self.class_jdoc()
        yield f"{'export ' if self.export_ else ''} class {self.class_name_} {{"
        self.indent()
        yield ""
        yield from self.constructor()
        yield ""
        yield from self.match()
        yield ""
        yield from self.reverse()
        yield ""
        yield "urls = {"

    def close_visit(self) -> Generator[Optional[str], None, None]:
        """
        Finish tree visitation/close out the class code.

        :yield: Trailing JavaScript LoC
        """
        yield "}"
        for _, override in self.overrides_.items():
            yield from override.transpile(Context(self.context))
        self.outdent()
        yield "};"

    def enter_namespace(self, namespace: str) -> Generator[Optional[str], None, None]:
        """
        Start the namespace object.

        :param namespace: The name of the current part of the namespace we're
            visiting.
        :yield: JavaScript starting the namespace object structure.
        """
        yield f'"{namespace}": {{'
        self.indent()

    def exit_namespace(self, namespace: str) -> Generator[Optional[str], None, None]:
        """
        End the namespace object.

        :param namespace: The name of the current part of the namespace we're
            visiting.
        :yield: JavaScript ending the namespace object structure.
        """
        self.outdent()
        yield "},"

    def enter_path_group(self, qname: str) -> Generator[Optional[str], None, None]:
        """
        Start of the reversal function for a collection of paths of the given
        qname. If in ES5 mode, sets default args.

        :param qname: The fully qualified path name being reversed
        :yield: LoC for the start out of the JavaScript reversal function
        """
        yield f'"{qname.split(":")[-1]}": (kwargs={{}}, args=[]) => {{'
        self.indent()

    def exit_path_group(self, qname: str) -> Generator[Optional[str], None, None]:
        """
        Close out the function for the given qname.

        :param qname: The fully qualified path name being reversed
        :yield: LoC for the close out of the JavaScript reversal function
        """
        self.outdent()
        yield "},"

    def visit_path(
        self,
        path: List[Union[Substitute, str]],
        kwargs: List[str],
        defaults: Optional[Dict[str, Any]] = None,
    ) -> Generator[Optional[str], None, None]:
        """
        Convert a list of path components into JavaScript reverse function. The
        JS must determine if the passed named or positional arguments match
        this particular pattern and if so return the path with those arguments
        substituted.

        :param path: An iterable of the path components, alternating strings
            and Substitute placeholders for argument substitution
        :param kwargs: The names of the named arguments, if any, for the path
        :param defaults: Any default kwargs specified on the path definition
        :yield: The JavaScript lines of code
        """
        quote = "`"
        visitor = self

        class ArgEncoder(DjangoJSONEncoder):
            """
            An encoder that uses the configured to javascript function to
            convert any unknown types to strings.
            """

            def default(self, o):
                return visitor.to_javascript(o).rstrip('"').lstrip('"')

        defaults_str = json.dumps(defaults, cls=ArgEncoder)
        if len(path) == 1:  # there are no substitutions
            if defaults:
                yield (
                    f"if (this.#match(kwargs, args, [], {defaults_str})) "
                    f'{{ return "/{str(path[0]).lstrip("/")}"; }}'
                )
            else:
                yield (
                    f"if (this.#match(kwargs, args)) "
                    f'{{ return "/{str(path[0]).lstrip("/")}"; }}'
                )
        elif len(kwargs) == 0:
            nargs = len([comp for comp in path if isinstance(comp, Substitute)])
            # no need to handle defaults - there should not be any because
            # Django reverse does not allow mixing args and kwargs in calls
            # to reverse
            yield (
                f"if (this.#match(kwargs, args, {nargs})) {{"
                f" return {quote}/{self.path_join(path).lstrip('/')}"
                f"{quote}; }}"
            )
        else:
            opts_str = ",".join([self.to_javascript(param) for param in kwargs])
            if defaults:
                yield (
                    f"if (this.#match(kwargs, args, [{opts_str}], "
                    f"{defaults_str})) {{"
                    f" return {quote}/{self.path_join(path).lstrip('/')}"
                    f"{quote}; }}"
                )
            else:
                yield (
                    f"if (this.#match(kwargs, args, [{opts_str}])) {{"
                    f" return {quote}/{self.path_join(path).lstrip('/')}"
                    f"{quote}; }}"
                )
