"""
Template tags and filters available when the render_static app is installed.
"""

import functools
from copy import copy
from enum import Enum
from inspect import getfullargspec, unwrap
from types import ModuleType
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Type,
    Union,
    cast,
)

from django import template
from django.conf import settings
from django.template import Node, NodeList
from django.template.context import Context
from django.template.library import parse_bits
from django.utils.module_loading import import_string
from django.utils.safestring import SafeString

from render_static.transpilers.base import (
    Transpiler,
    TranspilerTarget,
    TranspilerTargets,
)
from render_static.transpilers.defines_to_js import DefaultDefineTranspiler
from render_static.transpilers.enums_to_js import EnumClassWriter
from render_static.transpilers.urls_to_js import ClassURLWriter

__all__ = ["split", "defines_to_js", "urls_to_js", "enums_to_js"]

Targets = Union[TranspilerTargets, TranspilerTarget]
TranspilerType = Union[Type[Transpiler], str]


def do_transpile(
    targets: Targets, transpiler: TranspilerType, kwargs: Dict[Any, Any]
) -> str:
    """
    Transpile the given target(s) using the given transpiler and
    parameters for the transpiler.

    :param targets: A list or single transpiler target which can be an import
        string a module type or a class.
    :param transpiler: The transpiler class or import string for the transpiler
        class to use.
    :param kwargs: Any kwargs that the transpiler takes.
    :return: SafeString of rendered transpiled code.
    """
    if isinstance(targets, (type, str)) or not isinstance(targets, Collection):
        targets = [targets]

    transpiler_cls = (
        import_string(transpiler) if isinstance(transpiler, str) else transpiler
    )
    return SafeString(transpiler_cls(**kwargs).transpile(targets))


class OverrideNode(Node):
    """
    A block node that holds a block override. Works with all transpilers.

    :param override_name: The name of the override (i.e. function name).
    :param nodelist: The child nodes for this node. Should be empty
    """

    def __init__(
        self,
        override_name: Optional[Union[str, template.base.FilterExpression]],
        nodelist: NodeList,
    ):
        self.override_name = override_name or f"_{id(self)}"
        self.nodelist = nodelist
        self.context = Context()

    def bind(self, context: Context) -> str:
        """
        Bind the override to the given base context. The same override
        may be transpiled multiple times to extensions of this context.
        See transpile.

        :param context: The context to bind the override to.
        :return: The name of the override.
        """
        self.context = copy(context)
        return (
            self.override_name.resolve(context)
            if isinstance(
                self.override_name,
                (template.base.Variable, template.base.FilterExpression),
            )
            else self.override_name
        )

    def transpile(self, context: Context) -> Generator[str, None, None]:
        """
        Render the override in the given context, yielding each line.

        :param context: The context to render the override in.
        :return: A generator of lines of rendered override.
        """
        self.context.update(context)
        lines = self.nodelist.render(self.context).splitlines()
        yield from lines


class TranspilerNode(Node):
    """
    A block node holding a transpilation and associated parameters.
    Works with all transpilers.

    :param nodelist: The child nodes for this node. Should be empty
        or only contain overrides.
    :param transpiler: The transpiler class or import string.
    :param targets: The index or the targets positional argument or the
        name of the keyword argument that contains the targets.
    :param kwargs: The keyword arguments to pass to the transpiler
    """

    def __init__(
        self,
        func: Callable,
        targets: Optional[str],
        kwargs: Dict[str, Any],
        nodelist: Optional[NodeList] = None,
    ):
        self.func = func
        self.targets = targets
        self.kwargs = kwargs
        self.nodelist = nodelist or NodeList()

    def get_resolved_arguments(self, context: Context) -> Dict[str, Any]:
        """
        Resolve the arguments to the transpiler.

        :param context: The context of the template being rendered.
        :return: A dictionary of resolved arguments.
        """
        resolved_kwargs = {
            k: v.resolve(context)
            if isinstance(v, (template.base.Variable, template.base.FilterExpression))
            else v
            for k, v in self.kwargs.items()
        }
        overrides = self.get_nodes_by_type(OverrideNode)
        if overrides:
            resolved_kwargs["overrides"] = {
                cast(OverrideNode, override).bind(context): override
                for override in overrides
            }
        return resolved_kwargs

    def render(self, context: Context) -> str:
        """
        Transpile the given target(s).

        :param context: The context of the template being rendered.
        :return: SafeString of rendered transpiled code.
        """
        return self.func(**self.get_resolved_arguments(context))


register = template.Library()


def transpiler_tag(
    func: Optional[Callable] = None,
    targets: Union[int, str] = 0,
    name: Optional[str] = None,
    node: Type[TranspilerNode] = TranspilerNode,
):
    """
    Register a callable as a transpiler tag. This decorator is similar
    to simple_tag but also passes the parser and token to the decorated
    function.
    """

    def dec(func: Callable):
        (
            pos_args,
            varargs,
            varkw,
            defaults,
            kwonly,
            kwonly_defaults,
            _,
        ) = getfullargspec(unwrap(func))
        function_name = name or getattr(func, "_decorated_function", func).__name__

        assert "transpiler" in pos_args or "transpiler" in kwonly, (
            f"{function_name} must accept a transpiler argument."
        )

        param_defaults = {
            pos_args[len(pos_args or []) - len(defaults or []) + idx]: default
            for idx, default in enumerate(defaults or [])
        }

        @functools.wraps(func)
        def compile_func(parser, token):
            # we have to lookahead to see if there is an end tag because parse
            # will error out if we ask it to parse_until and there isn't one.
            is_block = False
            nodelist = None
            for lookahead in reversed(parser.tokens):
                if lookahead.token_type == template.base.TokenType.BLOCK:
                    command = lookahead.contents.split()[0]
                    if command == f"end{function_name}":
                        is_block = True
                        break
                    if command == f"{function_name}":
                        break
            if is_block:
                nodelist = parser.parse(parse_until=(f"end{function_name}",))
                parser.delete_first_token()

            bits = token.split_contents()[1:]
            pargs, pkwargs = parse_bits(
                parser,
                bits,
                pos_args,
                varargs,
                varkw,
                defaults,
                kwonly,
                kwonly_defaults,
                False,
                function_name,
            )
            # we rearrange everything here to turn all arguments into
            # keyword arguments b/c while this eliminates variadic positional
            # arguments it does make this code more robust to custom
            # transpiler constructor signatures
            for idx, parg in enumerate(pargs):
                pkwargs[pos_args[idx]] = parg

            return node(
                func,
                pos_args[targets] if isinstance(targets, int) else targets,
                {**(kwonly_defaults or {}), **param_defaults, **pkwargs},
                nodelist,
            )

        register.tag(function_name, compile_func)
        return func

    if func is None:
        # @register.transpile_tag(...)
        return dec
    if callable(func):
        # @register.transpile_tag
        return dec(func)
    raise ValueError("Invalid arguments provided to transpiler_tag")


@register.filter(name="split")
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


@transpiler_tag
def transpile(targets: Targets, transpiler: TranspilerType, **kwargs) -> str:
    """
    Run the given transpiler on the given targets and write the generated
    javascript in-place.

    :param targets: A list or single transpiler target which can be an import
        string a module type or a class.
    :param transpiler: The transpiler class or import string for the transpiler
        class to use.
    :param kwargs: Any kwargs that the transpiler takes.
    :return:
    """
    return do_transpile(targets=targets, transpiler=transpiler, kwargs=kwargs)


@transpiler_tag(targets="url_conf")
def urls_to_js(
    transpiler: TranspilerType = ClassURLWriter,
    url_conf: Optional[Union[ModuleType, str]] = None,
    indent: str = "\t",
    depth: int = 0,
    include: Optional[Iterable[str]] = None,
    exclude: Optional[Iterable[str]] = ("admin",),
    **kwargs,
) -> str:
    """
    Dump reversible URLs to javascript. The javascript generated provides functions for
    each fully qualified URL name that perform the same service as Django's URL
    :func:`~django.urls.reverse` function. The javascript output by this tag isn't
    standalone. It is up to the caller to embed it in another object. For instance,
    given the following urls.py:

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

        {% urls_to_js %}

    You can now reverse code in the javascript like this:

    .. code-block::

        const urls = URLResolver():

        # /my/url/
        console.log(urls.reverse('my_url));

        # /url/with/arg/143
        console.log(urls.reverse('my_url', {kwargs: {'arg1': 143}}));

        # /sub/detail/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa
        console.log(
            urls.reverse(
                'other:detail',
                {kwargs: {'id': 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'}}
            )
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
        Django's :func:`~django.urls.reverse` the strategy is to use the results of the
        :func:`~django.urls.reverse` call for the fully qualified name. Placeholder
        values are passed into :func:`~django.urls.reverse` and then overwritten with
        javascript substitution code based on the regex grouping information. This
        strategy avoids as much error prone regex/string processing as possible. The
        concession here is that placeholder values must be supplied by the user wherever
        we cant infer them. When using path instead of re_path we can use default
        placeholders for all the known converters. When using re_path or custom
        path converters users must register placeholders by parameter name,
        converter type, or app_name. Libraries exist for generating string
        patterns that match regex's but none seem reliable or stable enough to
        include as a dependency.

    :param transpiler: The transpiler class that will generate the JavaScript,
        as either a class or an import string. May be one of the built-ins or a
        user defined transpiler.
    :param url_conf: The root url module to dump urls from,
        default: :setting:`ROOT_URLCONF`
    :param indent: string to use for indentation in javascript, default: '  '
    :param depth: the starting indentation depth, default: 0
    :param include: A list of path names to include, namespaces without path
        names will be treated as every path under the namespace.
        Default: include everything
    :param exclude: A list of path names to exclude, namespaces without path
        names will be treated as every path under the namespace.
        Default: exclude nothing
    :param kwargs: Extra kwargs that will be passed to the visitor class on
        construction. All visitors are passed indent, and depth.
    :return: A javascript object containing functions that generate urls with
        and without parameters
    """
    return do_transpile(
        targets=url_conf or settings.ROOT_URLCONF,
        transpiler=transpiler,
        kwargs={
            "depth": depth,
            "indent": indent,
            "include": include,
            "exclude": exclude,
            **kwargs,
        },
    )


@transpiler_tag
def defines_to_js(
    defines: Union[
        ModuleType, Type[Any], str, Collection[Union[ModuleType, Type[Any], str]]
    ],
    transpiler: TranspilerType = DefaultDefineTranspiler,
    indent: str = "\t",
    depth: int = 0,
    **kwargs,
) -> str:
    """
    Transpile defines from the given modules or classes into javascript.

    :param defines: A module, class or import string to either.
    :param transpiler: The transpiler class or import string for the transpiler
        class that will perform the conversion,
        default: DefaultDefineTranspiler
    :param indent: The indent string to use
    :param depth: The depth of the initial indent
    :param kwargs: Any other kwargs to pass to the transpiler.
    :return: SafeString of rendered transpiled code.
    """
    return do_transpile(
        targets=defines,
        transpiler=transpiler,
        kwargs={"indent": indent, "depth": depth, **kwargs},
    )


@transpiler_tag
def enums_to_js(
    enums: Union[
        ModuleType, Type[Enum], str, Collection[Union[ModuleType, Type[Enum], str]]
    ],
    transpiler: TranspilerType = EnumClassWriter,
    indent: str = "\t",
    depth: int = 0,
    **kwargs,
) -> str:
    """
    Transpile the given enumeration(s).

    :param enums: An enum class or import string or a collection of either to
        transpile.
    :param transpiler: A transpiler class or import string of the transpiler
        class to use for the transpilation.
    :param indent: The indent string to use
    :param depth: The depth of the initial indent
    :param kwargs: Any other parameters to pass to the configured transpiler.
        See transpiler docs for details.
    :return: SafeString of rendered transpiled code.
    """
    return do_transpile(
        targets=enums,
        transpiler=transpiler,
        kwargs={"indent": indent, "depth": depth, **kwargs},
    )


@register.tag(name="override")
def override(parser, token):
    """
    Override a function in the parent transpilation.
    """
    nodelist = parser.parse(parse_until=("endoverride",))
    parser.delete_first_token()
    p_args, _ = parse_bits(
        parser,
        token.split_contents()[1:],
        ["override"],
        None,
        None,
        [],
        [],
        {},
        False,
        "override",
    )
    name = p_args[0] if p_args else None
    return OverrideNode(name, nodelist)
