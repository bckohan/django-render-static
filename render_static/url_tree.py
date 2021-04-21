"""
Utilities, functions and classes for generating JavaScript from Django's url configuration files.
"""

import itertools
import re
from abc import abstractmethod
from importlib import import_module
from types import ModuleType
from typing import Dict, Generator, Iterable, List, Optional, Tuple, Union

from django.conf import settings
from django.urls import URLPattern, URLResolver, reverse
from django.urls.exceptions import NoReverseMatch
from django.urls.resolvers import RegexPattern, RoutePattern
from render_static.exceptions import PlaceholderNotFound, URLGenerationFailed
from render_static.javascript import JavaScriptGenerator
from render_static.placeholders import (
    resolve_placeholders,
    resolve_unnamed_placeholders,
)

__all__ = [
    'normalize_ns',
    'build_tree',
    'Substitute',
    'URLTreeVisitor',
    'SimpleURLWriter',
    'ClassURLWriter'
]


def normalize_ns(namespaces: str) -> str:
    """
    Normalizes url names by collapsing multiple `:` characters.
    :param namespaces: The namespace string to normalize
    :return: The normalized version of the url path name
    """
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

    return _prune_tree(
        _build_branch(
            patterns,
            not includes or '' in includes,
            ({}, {}, getattr(url_conf, 'app_name', None)),
            includes,
            excludes
        )
    )


def _build_branch(  # pylint: disable=R0913
        nodes: Iterable[URLPattern],
        included: bool,
        branch: Tuple[Dict, Dict, Optional[str]],
        includes: Iterable[str],
        excludes: Iterable[str],
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

            _build_branch(
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


def _prune_tree(
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
            branch, branch_urls = _prune_tree(branch)
            if branch_urls == 0:
                to_delete.append(nmsp)
            num_urls += branch_urls
        for nmsp in to_delete:
            del tree[0][nmsp]

    return tree, num_urls


class Substitute:
    """
    A placeholder representing a substitution, either by a positional argument or a named argument
    in a url path string.

    :param arg_or_kwarg: Either an integer index corresponding to the argument to substitute for
        this placeholder or the string name of the argument to substitute at this placeholder.
    """

    arg_: Optional[Union[str, int]] = None

    @property
    def arg(self) -> Optional[Union[str, int]]:
        """
        :return: Either the position of the positional argument to substitute in, or the name of the
            named parameter
        """
        return self.arg_

    def __init__(self, arg_or_kwarg: Union[str, int]) -> None:
        self.arg_ = arg_or_kwarg

    def to_str(self, es5: bool = False) -> str:
        """
        Converts a _Substitution object placeholder into JavaScript code that substitutes the
        positional or named arguments in the string.

        :param es5: If true, generate ES5 compliant code
        :return: The JavaScript as a string
        """
        if isinstance(self.arg, int):
            return (
                f'"+args[{self.arg}].toString()+"' if es5
                else f'${{args[{self.arg}]}}'
            )
        return (
            f'"+kwargs["{self.arg}"].toString()+"' if es5
            else f'${{kwargs["{self.arg}"]}}'
        )


class URLTreeVisitor(JavaScriptGenerator):
    """
    An abstract base class for JavaScript generators of url reversal code. This class defines a
    a visitation design pattern that deriving classes may extend.

    Most of the difficult work of walking the URL tree is handled by this base class. Deriving
    classes are free to focus on generating Javascript, but may override the tree walking and
    url reversal logic if they so desire.

    To use this class derive from it and implement its abstract visitation methods. Visitor methods
    should `yield` lines of JavaScript code and set the indentation levels by calling indent() and
    outdent(). Each yielded line is written by the base class using the configured
    ndentation/newline options. When None is yielded or returned, nothing will be written. To write
    a newline and nothing else, simply yield or return an empty string.

    :param kwargs: Set of configuration parameters, see `JavaScriptGenerator` params
    """

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

    @abstractmethod
    def start_visitation(self) -> Generator[str, None, None]:
        """
        The first visitation call. Deriving visitors must implement.

        :yield: JavaScript, if any, that should be placed at at the very start
        """
        ...  # pragma: no cover - abstract

    @abstractmethod
    def end_visitation(self) -> Generator[str, None, None]:
        """
        The last visitation call - visitation will cease after returning. Deriving visitors must
        implement.

        :yield: JavaScript, if any, that should be placed at the very end
        """
        ...  # pragma: no cover - abstract

    @abstractmethod
    def enter_namespace(self, namespace) -> Generator[str, None, None]:
        """
        Walking down the url tree, the visitor has entered the given namespace. Deriving visitors
        must implement.

        :param namespace: namespace string
        :yield: JavaScript, if any, that should be placed at namespace visitation start
        """
        ...  # pragma: no cover - abstract

    @abstractmethod
    def exit_namespace(self, namespace) -> Generator[str, None, None]:
        """
        Walking down the url tree, the visitor has exited the given namespace. Deriving visitors
        must implement.
        :param namespace: namespace string
        :yield: JavaScript, if any, that should be placed at namespace visitation exit
        """
        ...  # pragma: no cover - abstract

    def visit_pattern(  # pylint: disable=R0914, R0912
            self,
            endpoint: URLPattern,
            qname: str,
            app_name: Optional[str]
    ) -> Generator[str, None, Optional[str]]:
        """
        Visit a pattern. Translates the pattern into a path component string which may contain
        substitution objects. This function will call visit_path once the path components have been
        constructed.

        The JavaScript url reversal code guarantees that it will always return the same paths as
        Django's reversal calls. It does this by using those same calls to create the path
        components. The registered placeholders for the url pattern name are used for path reversal.
        This technique forms the bedrock of the reliability of the JavaScript url reversals. Do not
        change it lightly!

        :param endpoint: The URLPattern to add
        :param qname: The fully qualified name of the URL
        :param app_name: The app_name the URLs belong to, if any
        :yield: JavaScript LoC that reverse the pattern
        :return: JavaScript comment if non-reversible
        :except URLGenerationFailed: When no successful placeholders are found for the given pattern
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
                                replacements.append((mtch.span(idx), Substitute(idx-1)))
                            else:
                                assert(idx in grp_mp and grp_mp[idx] in kwargs)
                                replacements.append((mtch.span(idx), Substitute(grp_mp[idx])))

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
    def enter_path_group(self, qname: str) -> Generator[str, None, None]:
        """
        Visit one or more path(s) all referred to by the same fully qualified name. Deriving classes
        must implement.

        :param qname: The fully qualified name of the path group
        :yield: JavaScript that should placed at the start of each path group.
        """
        ...  # pragma: no cover - abstract

    @abstractmethod
    def exit_path_group(self, qname: str) -> Generator[str, None, None]:
        """
        End visitation to one or more path(s) all referred to by the same fully qualified name.
        Deriving classes must implement.

        :param qname: The fully qualified name of the path group
        :yield: JavaScript that should placed at the end of each path group.
        """
        ...  # pragma: no cover - abstract

    @abstractmethod
    def visit_path(
            self,
            path: List[Union[Substitute, str]],
            kwargs: List[str]
    ) -> Generator[str, None, None]:
        """
        Visit a singular realization of a path into components. This is called by visit_pattern and
        deriving classes must implement.

        :param path: The path components making up the URL. An iterable containing strings and
            placeholder substitution objects. The _Substitution objects represent the locations
            where either positional or named arguments should be swapped into the path. Strings and
            substitutions will always alternate.
        :param kwargs: The list of named arguments present in the path, if any
        :yield: JavaScript that should handle the realized path.
        """
        ...  # pragma: no cover - abstract

    def visit_path_group(
        self,
        nodes: Iterable[URLPattern],
        qname: str,
        app_name: Optional[str] = None
    ) -> Generator[str, None, None]:
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
    ) -> Generator[str, None, None]:
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
            for nmsp, brch in branch[0].items():
                yield from self.enter_namespace(nmsp)
                yield from self.visit_branch(brch, nmsp, parent_qname)
                yield from self.exit_namespace(nmsp)

    def generate(self, *args, **kwargs) -> str:
        """
        Implements JavaScriptGenerator::generate. Calls the visitation entry point and writes all
        the yielded JavaScript lines to a member string which is returned.

        :param args: The URL tree to visit/generate code for - first positional
        :param kwargs: Optionally give tree as named parameter 'tree'
        :return: The rendered JavaScript URL reversal code.
        """
        for line in self.visit(args[0] if args else kwargs.pop('tree')):
            self.write_line(line)
        return self.rendered_

    def visit(self, tree) -> Generator[str, None, None]:
        """
        Visit the nodes of the URL tree, yielding JavaScript where needed.

        :param tree: The URL tree, in the format returned by build_tree().
        :yield: JavaScript lines
        """
        yield from self.start_visitation()
        self.indent()
        yield from self.visit_branch(tree)
        self.outdent()
        yield from self.end_visitation()

    def path_join(self, path: List[Union[Substitute, str]]) -> str:
        """
        Combine a list of path components into a singular JavaScript substitution string.

        :param path: The path components to collapse
        :return: The JavaScript substitution code that will realize a path with its arguments
        """
        return ''.join([
            comp if isinstance(comp, str) else comp.to_str(es5=self.es5_) for comp in path
        ])


class SimpleURLWriter(URLTreeVisitor):
    """
    A URLTreeVisitor that produces a JavaScript object where the keys are the path namespaces and
    names and the values are functions that accept positional and named arguments and return paths.

    This is the default visitor for the `url_to_js` tag, but its probably not the one you want.
    It accepts several additional parameters on top of the base parameters. To use this visitor you
    may call it like so:

    ..code-block::

        var urls = {
            {% urls_to_js raise_on_not_found=False %}'
        };

    This will produce JavaScript you may invoke like so:

    ..code-block::

        urls.namespace.path_name({'arg1': 1, 'arg2': 'a'});

    The classes generated by this visitor, both ES5 and ES6 minimize significantly worse than the
    `ClassURLWriter`.

    The configuration parameters that control the JavaScript output include:

        * *raise_on_not_found*
            Raise a TypeError if no reversal for a url pattern is found, default: True

    :param kwargs: Set of configuration parameters, see also `URLTreeVisitor` params
    """

    raise_on_not_found_ = True

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.raise_on_not_found_ = kwargs.pop('raise_on_not_found', self.raise_on_not_found_)

    def start_visitation(self) -> Generator[str, None, None]:
        """
        Begin visitation of the tree - noop

        :yield: writes nothing
        """
        yield None  # type: ignore

    def end_visitation(self) -> Generator[str, None, None]:
        """
        End visitation of the tree - noop

        :yield: writes nothing
        """
        yield None  # type: ignore

    def enter_namespace(self, namespace: str) -> Generator[str, None, None]:
        """
        Start the namespace object.

        :param namespace: The name of the current part of the namespace we're visiting.
        :yield: JavaScript starting the namespace object structure.
        """
        yield f'"{namespace}": {{'
        self.indent()

    def exit_namespace(self, namespace: str) -> Generator[str, None, None]:
        """
        End the namespace object.

        :param namespace: The name of the current part of the namespace we're visiting.
        :yield: JavaScript ending the namespace object structure.
        """
        self.outdent()
        yield '},'

    def enter_path_group(self, qname: str) -> Generator[str, None, None]:
        """
        Start of the reversal function for a collection of paths of the given qname. If in ES5 mode,
        sets default args.

        :param qname: The fully qualified path name being reversed
        :yield: LoC for the start out of the JavaScript reversal function
        """
        if self.es5_:
            yield f'"{qname.split(":")[-1]}": function(kwargs, args) {{'
            self.indent()
            yield 'kwargs = kwargs || {};'
            yield 'args = args || [];'
        else:
            yield f'"{qname.split(":")[-1]}": function(kwargs={{}}, args=[]) {{'
            self.indent()

    def exit_path_group(self, qname: str) -> Generator[str, None, None]:
        """
        Close out the function for the given qname. If we're configured to throw an exception if no
        path reversal was found, we do that here because all options have already been exhausted.

        :param qname: The fully qualified path name being reversed
        :yield: LoC for the close out of the JavaScript reversal function
        """
        if self.raise_on_not_found_:
            yield f'throw new TypeError("No reversal available for parameters at path: {qname}");'
        self.outdent()
        yield '},'

    def visit_path(
            self,
            path: List[Union[Substitute, str]],
            kwargs: List[str]
    ) -> Generator[str, None, None]:
        """
        Convert a list of path components into JavaScript reverse function. The JS must determine
        if the passed named or positional arguments match this particular pattern and if so return
        the path with those arguments substituted.

        :param path: An iterable of the path components, alternating strings and Substitute
            placeholders for argument substitution
        :param kwargs: The names of the named arguments, if any, for the path
        :yield: The JavaScript lines of code
        """

        if len(path) == 1:
            yield 'if (Object.keys(kwargs).length === 0 && args.length === 0)'
            self.indent()
            yield f'return "/{path[0].lstrip("/")}";'  # type: ignore
            self.outdent()
        elif len(kwargs) == 0:
            nargs = len([comp for comp in path if isinstance(comp, Substitute)])
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
    """
    A URLTreeVisitor that produces a JavaScript class with a reverse() function directly analogous
    to Django's url reverse function.

    This is not the default visitor for the `url_to_js` tag, but its probably the one you want.
    It accepts several additional parameters on top of the base parameters. To use this visitor you
    may call it like so:

    ..code-block::

        {% urls_to_js visitor="render_static.ClassURLWriter" class_name='URLResolver' indent=' ' %}'

    This will produce JavaScript you may invoke like so:

    ..code-block::

        const urls = new URLResolver();
        urls.reverse('namespace:path_name', {'arg1': 1, 'arg2': 'a'});

    The classes generated by this visitor, both ES5 and ES6 minimize significantly better than the
    default `SimpleURLWriter`.

    The configuration parameters that control the JavaScript output include:

        * *class_name*
            The name of the JavaScript class to use: default: URLResolver
        * *raise_on_not_found*
            Raise a TypeError if no reversal for a url pattern is found,
            default: True

    :param kwargs: Set of configuration parameters, see also `URLTreeVisitor` params
    """

    class_name_ = 'URLResolver'
    raise_on_not_found_ = True

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.class_name_ = kwargs.pop('class_name', self.class_name_)
        self.raise_on_not_found_ = kwargs.pop('raise_on_not_found', self.raise_on_not_found_)

    def start_visitation(self) -> Generator[str, None, None]:  # pylint: disable=R0915
        """
        Start the tree visitation - this is where we write out all the common class code.

        :yield: JavaScript LoC for the reversal class
        """
        if self.es5_:
            yield f'{self.class_name_} = function() {{}};'
            yield ''
            yield f'{self.class_name_}.prototype = {{'
            self.indent()
            yield 'match: function(kwargs, args, expected) {'
            self.indent()
            yield 'if (Array.isArray(expected)) {'
            self.indent()
            yield ('return (Object.keys(kwargs).length === expected.length && '
                   'expected.every(function(value) { return kwargs.hasOwnProperty(value); }))'
            )
            self.outdent()
            yield '} else if (expected) {'
            self.indent()
            yield 'return args.length === expected;'
            self.outdent()
            yield '} else {'
            self.indent()
            yield 'return Object.keys(kwargs).length === 0 && args.length === 0;'
            self.outdent()
            yield '}'
            self.outdent()
            yield '},'
            yield 'reverse: function(qname, kwargs, args) {'
            self.indent()
            yield 'kwargs = kwargs || {};'
            yield 'args = args || [];'
            yield 'let url = this.urls;'
            yield "qname.split(':').forEach(function(ns) {"
            self.indent()
            yield 'if (ns && url) { url = url.hasOwnProperty(ns) ? url[ns] : null; }'
            self.outdent()
            yield '});'
            yield 'if (url) {'
            self.indent()
            yield 'let pth = url.call(this, kwargs, args);'
            yield 'if (typeof pth === "string") { return pth; }'
            self.outdent()
            yield '}'
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
            yield 'if (Array.isArray(expected)) {'
            self.indent()
            yield (
                'return Object.keys(kwargs).length === expected.length && '
                'expected.every(value => kwargs.hasOwnProperty(value));'
            )
            self.outdent()
            yield '} else if (expected) {'
            self.indent()
            yield 'return args.length === expected;'
            self.outdent()
            yield '} else {'
            self.indent()
            yield 'return Object.keys(kwargs).length === 0 && args.length === 0;'
            self.outdent()
            yield '}'
            self.outdent()
            yield '}'
            yield ''
            yield 'reverse(qname, kwargs={}, args=[]) {'
            self.indent()
            yield 'let url = this.urls;'
            yield "for (const ns of qname.split(':')) {"
            self.indent()
            yield 'if (ns && url) { url = url.hasOwnProperty(ns) ? url[ns] : null; }'
            self.outdent()
            yield '}'
            yield 'if (url) {'
            self.indent()
            yield 'let pth = url(kwargs, args);'
            yield 'if (typeof pth === "string") { return pth; }'
            self.outdent()
            yield '}'
            if self.raise_on_not_found_:
                yield ('throw new TypeError('
                       '`No reversal available for parameters at path: ${qname}`);'
                )
            self.outdent()
            yield '}'
            yield ''
            yield 'urls = {'

    def end_visitation(self) -> Generator[str, None, None]:
        """
        Finish tree visitation/close out the class code.

        :yield: Trailing JavaScript LoC
        """
        yield '}'
        self.outdent()
        yield '};'

    def enter_namespace(self, namespace: str) -> Generator[str, None, None]:
        """
        Start the namespace object.

        :param namespace: The name of the current part of the namespace we're visiting.
        :yield: JavaScript starting the namespace object structure.
        """
        yield f'"{namespace}": {{'
        self.indent()

    def exit_namespace(self, namespace: str) -> Generator[str, None, None]:
        """
        End the namespace object.

        :param namespace: The name of the current part of the namespace we're visiting.
        :yield: JavaScript ending the namespace object structure.
        """
        self.outdent()
        yield '},'

    def enter_path_group(self, qname: str) -> Generator[str, None, None]:
        """
        Start of the reversal function for a collection of paths of the given qname. If in ES5 mode,
        sets default args.

        :param qname: The fully qualified path name being reversed
        :yield: LoC for the start out of the JavaScript reversal function
        """
        if self.es5_:
            yield f'"{qname.split(":")[-1]}": function(kwargs, args) {{'
            self.indent()
            yield 'kwargs = kwargs || {};'
            yield 'args = args || [];'
        else:
            yield f'"{qname.split(":")[-1]}": (kwargs={{}}, args=[]) => {{'
            self.indent()

    def exit_path_group(self, qname: str) -> Generator[str, None, None]:
        """
        Close out the function for the given qname.

        :param qname: The fully qualified path name being reversed
        :yield: LoC for the close out of the JavaScript reversal function
        """
        self.outdent()
        yield '},'

    def visit_path(
            self,
            path: List[Union[Substitute, str]],
            kwargs: List[str]
    ) -> Generator[str, None, None]:
        """
        Convert a list of path components into JavaScript reverse function. The JS must determine
        if the passed named or positional arguments match this particular pattern and if so return
        the path with those arguments substituted.

        :param path: An iterable of the path components, alternating strings and Substitute
            placeholders for argument substitution
        :param kwargs: The names of the named arguments, if any, for the path
        :yield: The JavaScript lines of code
        """
        quote = '"' if self.es5_ else '`'
        if len(path) == 1:
            yield f'if (this.match(kwargs, args)) {{ return "/{str(path[0]).lstrip("/")}"; }}'
        elif len(kwargs) == 0:
            nargs = len([comp for comp in path if isinstance(comp, Substitute)])
            yield (
                f'if (this.match(kwargs, args, {nargs})) {{'
                f' return {quote}/{self.path_join(path).lstrip("/")}{quote}; }}'
            )
        else:
            opts_str = ",".join([f"'{param}'" for param in kwargs])
            yield (
                f'if (this.match(kwargs, args, [{opts_str}])) {{'
                f' return {quote}/{self.path_join(path).lstrip("/")}{quote}; }}'
            )
