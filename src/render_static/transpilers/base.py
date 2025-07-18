"""
Base transpiler components.
"""

import json
import numbers
from abc import ABCMeta, abstractmethod
from collections.abc import Hashable
from datetime import date, datetime
from enum import Enum
from importlib import import_module
from types import ModuleType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Collection,
    Dict,
    Generator,
    List,
    Optional,
    Set,
    Type,
    Union,
    cast,
)

from django.apps import apps
from django.apps.config import AppConfig
from django.template.context import Context
from django.utils.module_loading import import_string
from django.utils.safestring import SafeString

if TYPE_CHECKING:  # pragma: no cover
    from render_static.templatetags.render_static import OverrideNode


__all__ = [
    "CodeWriter",
    "Transpiler",
    "TranspilerTargets",
    "TranspilerTarget",
    "ResolvedTranspilerTarget",
]

ResolvedTranspilerTarget = Union[Type, ModuleType, AppConfig]
TranspilerTarget = Union[ResolvedTranspilerTarget, str]
TranspilerTargets = Collection[TranspilerTarget]


def to_js(value: Any) -> str:
    """
    Default javascript transpilation function for values. Simply adds quotes
    if it's a string and falls back on json.dumps() for non-strings and non-
    numerics.

    :param value: The value to transpile
    :return: Valid javascript code that represents the value
    """
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, numbers.Number):
        return str(value)
    if isinstance(value, str):
        return f'"{value}"'
    try:
        return json.dumps(value)
    except TypeError:
        if isinstance(value, datetime):
            return f'"{value.isoformat()}"'
        return f'"{str(value)}"'


def to_js_datetime(value: Any) -> str:
    """
    A javascript value transpilation function that transpiles python dates and
    datetimes to javascript Date objects instead of strings. To use this
    function in any of the transpilation routines pass it to the to_javascript
    parameter on any of the template tags::

        {% ... to_javascript="render_static.transpilers.to_js_datetime" %}

    :param value: The value to transpile
    :return: Valid javascript code that represents the value
    """
    if isinstance(value, date):
        return f'new Date("{value.isoformat()}")'
    return to_js(value)


class _TargetTreeNode:
    """
    Simple tree node for tracking python target hierarchy.
    """

    target: Optional[ResolvedTranspilerTarget]
    children: List["_TargetTreeNode"]
    transpile = False

    def __init__(
        self, target: Optional[ResolvedTranspilerTarget] = None, transpile: bool = False
    ):
        """
        :param target: The target at this node
        """
        self.target = target
        self.children = []
        self.transpile = transpile

    def append(self, child: "_TargetTreeNode"):
        """
        Only appends children that are to be transpiled or that have children.

        :param child: The child node
        """
        if child.transpile or child.children:
            self.children.append(child)


class CodeWriter:
    """
    A base class that provides basic code writing functionality. This class
    implements a simple indentation/newline scheme that deriving classes may
    use.
    """

    rendered_: str
    level_: int = 0
    prefix_: str = ""
    indent_: str = " " * 4
    nl_: str = "\n"

    def __init__(
        self,
        level: int = level_,
        indent: Optional[str] = indent_,
        prefix: str = prefix_,
        **kwargs,
    ) -> None:
        """
        :param level: The level to start indentation at
        :param indent: The indent string to use
        :param prefix: A prefix string to add to each line
        :param kwargs: Any additional configuration parameters
        """
        self.rendered_ = ""
        self.level_ = level
        self.indent_ = indent or ""
        self.prefix_ = prefix or ""
        self.nl_ = self.nl_ if self.indent_ else ""

    def get_line(self, line: Optional[str]) -> str:
        """
        Returns a line with indentation and newline.
        """
        return f"{self.prefix_}{self.indent_ * self.level_}{line}{self.nl_}"

    def write_line(self, line: Optional[str]) -> None:
        """
        Writes a line to the rendered code file, respecting
        indentation/newline configuration for this generator.

        :param line: The code line to write
        :return:
        """
        if line is not None:
            self.rendered_ += self.get_line(line)

    def indent(self, incr: int = 1) -> None:
        """
        Step in one or more indentation levels.

        :param incr: The number of indentation levels to step into. Default: 1
        :return:
        """
        self.level_ += incr

    def outdent(self, decr: int = 1) -> None:
        """
        Step out one or more indentation levels.

        :param decr: The number of indentation levels to step out. Default: 1
        :return:
        """
        self.level_ -= decr
        self.level_ = max(0, self.level_)


class Transpiler(CodeWriter, metaclass=ABCMeta):
    """
    An abstract base class for JavaScript generator types. This class defines a
    basic generation API, and implements configurable indentation/newline
    behavior. It also offers a toggle for ES5/ES6 mode that deriving classes
    may use.

    To use this class derive from it and implement include_target() and
    visit().
    """

    to_javascript_: Callable = to_js

    parents_: List[Union[ModuleType, Type]]
    target_: ResolvedTranspilerTarget

    overrides_: Dict[str, "OverrideNode"]

    @property
    def target(self):
        """The python artifact that is the target to transpile."""
        return self.target_

    @property
    def parents(self):
        """
        When in visit() this returns the parents (modules and classes) of the
        visited target.
        """
        return [parent for parent in self.parents_ if parent is not self.target]

    @property
    def context(self):
        """
        The base template render context passed to overrides. Includes:

            - **transpiler**: The transpiler instance
        """
        return {"transpiler": self}

    def __init__(
        self,
        to_javascript: Union[str, Callable] = to_javascript_,
        overrides: Optional[Dict[str, "OverrideNode"]] = None,
        **kwargs,
    ) -> None:
        """
        :param to_javascript: A callable that accepts a python artifact and returns
            a transpiled object or primitive instantiation.
        :param kwargs: A set of configuration parameters for the generator, see
            above.
        """
        super().__init__(**kwargs)
        self.to_javascript = (
            to_javascript if callable(to_javascript) else import_string(to_javascript)
        )
        self.overrides_ = overrides or {}
        self.parents_ = []
        assert callable(self.to_javascript), "To_javascript is not callable!"

    def transpile_override(
        self,
        override: str,
        default_impl: Union[str, Generator[Optional[str], None, None]],
        context: Optional[Dict[str, Any]] = None,
    ) -> Generator[str, None, None]:
        """
        Returns a string of lines from a generator with the indentation and
        newlines added. This is meant to be used in place during overrides,
        so the first newline has no indents. So it will have the line prefix
        of {{ default_impl }}.

        :param override: The name of the override to transpile
        :param default_impl: The default implementation to use if the override
            is not present. May be a single line string or a generator of
            lines.
        :param context: Any additional context to pass to the override render
        """
        d_impl = default_impl
        if isinstance(default_impl, Generator):
            d_impl = ""
            for idx, line in enumerate(default_impl):
                if idx == 0:
                    d_impl += f"{line}{self.nl_}"
                else:
                    d_impl += self.get_line(line)
            d_impl.rstrip(self.nl_)

        yield from self.overrides_.pop(override).transpile(
            Context(
                {**self.context, "default_impl": SafeString(d_impl), **(context or {})}
            )
        )

    @abstractmethod
    def include_target(self, target: ResolvedTranspilerTarget) -> bool:
        """
        Deriving transpilers must implement this method to filter targets
        (modules or classes) in and out of transpilation. Transpilers are
        expected to walk module trees and pick out supported python artifacts.

        :param target: The python artifact to filter in or out
        :return: True if the target can be transpiled
        """
        return True

    def transpile(self, targets: TranspilerTargets) -> str:
        """
        Generate and return javascript as a string given the targets. This
        method iterates over the list of given targets, imports any strings
        and builds a tree from targets the deriving transpiler filters
        in via `include_target`. It then does a depth first traversal through
        the tree to any leaf target nodes that were included and visits them
        where any deriving class transpilation takes place.

        :param targets: The python targets to transpile
        :return: The rendered JavaScript string
        """
        root = _TargetTreeNode()
        deduplicate_set: Set[Hashable] = set()

        def walk_class(cls: _TargetTreeNode):
            for name, cls_member in vars(cls.target).items():
                if name.startswith("_"):
                    continue
                if isinstance(cls_member, type) and cls_member not in deduplicate_set:
                    deduplicate_set.add(cls_member)
                    cls.append(
                        walk_class(
                            _TargetTreeNode(cls_member, self.include_target(cls_member))
                        )
                    )
            return cls

        for target in targets:
            # do this instead of isinstance b/c types that inherit from strings
            # may be targets
            if isinstance(target, str):
                if apps.is_installed(target):
                    target = cast(
                        AppConfig,
                        {
                            app_config.name: app_config
                            for app_config in apps.get_app_configs()
                        }.get(target),
                    )
                else:
                    try:
                        target = apps.get_app_config(target)
                    except LookupError:
                        assert isinstance(target, str)
                        parts = target.split(".")
                        tries = 0
                        while True:
                            try:
                                tries += 1
                                target = import_string(
                                    ".".join(
                                        parts[0 : None if tries == 1 else -(tries - 1)]
                                    )
                                )
                                if tries > 1:
                                    for attr in parts[-(tries - 1) :]:
                                        target = getattr(target, attr)
                                break
                            except (ImportError, AttributeError, ValueError) as err:
                                if tries == 1:
                                    try:
                                        target = import_module(".".join(parts))
                                        break
                                    except (ImportError, ModuleNotFoundError):
                                        if len(parts) == 1:
                                            raise ImportError(
                                                f"Unable to import {target}"
                                            ) from err
                                elif tries == len(parts):
                                    raise ImportError(
                                        f"Unable to import {target}"
                                    ) from err

            target = cast(ResolvedTranspilerTarget, target)
            node = _TargetTreeNode(target, self.include_target(target))

            if node.target in deduplicate_set:
                continue

            if isinstance(target, Hashable):
                deduplicate_set.add(target)

            if isinstance(target, type):
                root.append(walk_class(node))
            elif isinstance(target, ModuleType):
                for _, member in vars(target).items():
                    if isinstance(member, type):
                        node.append(
                            walk_class(
                                _TargetTreeNode(member, self.include_target(member))
                            )
                        )
                root.append(node)
            elif isinstance(target, AppConfig):
                root.append(node)

        if not root.transpile and not root.children:
            raise ValueError(f"No targets were transpilable: {targets}")

        def visit_depth_first(
            branch: _TargetTreeNode, is_last: bool = False, final: bool = True
        ):
            is_final = final and not branch.children
            if branch.target and not isinstance(branch.target, AppConfig):
                for stm in self.enter_parent(branch.target, is_last, is_final):
                    self.write_line(stm)

            if branch.transpile and branch.target:
                self.target_ = branch.target
                for stm in self.visit(branch.target, is_last, is_final):
                    self.write_line(stm)

            if branch.children:
                for idx, child in enumerate(branch.children):
                    visit_depth_first(
                        child,
                        idx == len(branch.children) - 1,
                        (idx == len(branch.children) - 1) and final,
                    )

            if branch.target and not isinstance(branch.target, AppConfig):
                for stm in self.exit_parent(branch.target, is_last, is_final):
                    self.write_line(stm)

        for line in self.start_visitation():
            self.write_line(line)

        visit_depth_first(root)

        for line in self.end_visitation():
            self.write_line(line)

        return self.rendered_

    def enter_parent(
        self, parent: Union[ModuleType, Type], is_last: bool, is_final: bool
    ) -> Generator[Optional[str], None, None]:
        """
        Enter and visit a target, pushing it onto the parent stack.

        :param parent: The target, class or module to transpile.
        :param is_last: True if this is the last target that will be visited at
            this level.
        :param is_final: False if this is the last target that will be visited
            at all.
        :yield: javascript lines, writes nothing by default
        """
        self.parents_.append(parent)
        if isinstance(parent, ModuleType):
            yield from self.enter_module(parent, is_last, is_final)
        else:
            yield from self.enter_class(parent, is_last, is_final)

    def exit_parent(
        self, parent: Union[ModuleType, Type], is_last: bool, is_final: bool
    ) -> Generator[Optional[str], None, None]:
        """
        Exit a target, removing it from the parent stack.

        :param parent: The target, class or module that was just transpiled.
        :param is_last: True if this is the last target that will be visited at
            this level.
        :param is_final: False if this is the last target that will be visited
            at all.
        :yield: javascript lines, writes nothing by default
        """
        del self.parents_[-1]
        if isinstance(parent, ModuleType):
            yield from self.exit_module(parent, is_last, is_final)
        else:
            yield from self.exit_class(parent, is_last, is_final)

    def enter_module(
        self,
        module: ModuleType,
        is_last: bool,
        is_final: bool,
    ) -> Generator[Optional[str], None, None]:
        """
        Transpile a module.

        :param module: The module to transpile
        :param is_last: True if this is the last target at this level to
            transpile.
        :param is_final: True if this is the last target at all to transpile.
        :yield: javascript lines, writes nothing by default
        """
        yield None

    def exit_module(
        self,
        module: ModuleType,
        is_last: bool,
        is_final: bool,
    ) -> Generator[Optional[str], None, None]:
        """
        Close transpilation of a module.

        :param module: The module that was just transpiled
        :param is_last: True if this is the last target at this level to
            transpile.
        :param is_final: True if this is the last target at all to transpile.
        :yield: javascript lines, writes nothing by default
        """
        yield None

    def enter_class(
        self,
        cls: Type[Any],
        is_last: bool,
        is_final: bool,
    ) -> Generator[Optional[str], None, None]:
        """
        Transpile a class.

        :param cls: The class to transpile
        :param is_last: True if this is the last target at this level to
            transpile.
        :param is_final: True if this is the last target at all to transpile.
        :yield: javascript lines, writes nothing by default
        """
        yield None

    def exit_class(
        self,
        cls: Type[Any],
        is_last: bool,
        is_final: bool,
    ) -> Generator[Optional[str], None, None]:
        """
        Close transpilation of a class.

        :param cls: The class that was just transpiled
        :param is_last: True if this is the last target at this level to
            transpile.
        :param is_final: True if this is the last target at all to transpile.
        :yield: javascript lines, writes nothing by default
        """
        yield None

    def start_visitation(self) -> Generator[Optional[str], None, None]:
        """
        Begin transpilation - called before visit(). Override this function
        to do any initial code generation.

        :yield: javascript lines, writes nothing by default
        """
        yield None

    def end_visitation(self) -> Generator[Optional[str], None, None]:
        """
        End transpilation - called after all visit() calls have completed.
        Override this function to do any wrap up code generation.

        :yield: javascript lines, writes nothing by default
        """
        yield None

    @abstractmethod
    def visit(
        self, target: ResolvedTranspilerTarget, is_last: bool, is_final: bool
    ) -> Generator[Optional[str], None, None]:
        """
        Deriving transpilers must implement this method.

        :param target: The python target to transpile, will be either a class
            a module or an installed Django app.
        :param is_last: True if this is the last target that will be visited at
            this level.
        :param is_final: True if this is the last target that will be visited
            at all.
        :yield: lines of javascript
        """

    def to_js(self, value: Any):
        """
        Return the javascript transpilation of the given value.

        :param value: The value to transpile
        :return: A valid javascript code that represents the value
        """
        return self.to_javascript(value)
