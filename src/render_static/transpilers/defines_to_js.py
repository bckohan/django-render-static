"""
Built-in transpilers for python classes. Only one is provided that transpiles
plain old data found on classes and their ancestors.
"""

from types import ModuleType
from typing import Any, Callable, Dict, Generator, Optional, Type, Union

from django.apps import AppConfig
from django.template.context import Context

from render_static.transpilers.base import ResolvedTranspilerTarget, Transpiler


class DefaultDefineTranspiler(Transpiler):
    """
    A Transpiler that transpiles plain old data in python classes
    into simple JavaScript structures. For example if you have a model with
    choices:

    .. code-block:: python

        class MyModel(models.Model):

            FIELD_CHOICES = (
                ('A', 'Choice A'),
                ('B', 'Choice B'),
                ('C', 'Choice C')
            )

            field = models.CharField(max_length=1, choices=FIELD_CHOICES)

    Your template might look like:

    .. code-block:: js+django

        {% defines_to_js defines='package.MyModel' %}

    This will produce JavaScript you may invoke like so:

    .. code-block::

        const defines = {
            FIELD_CHOICES: [
                ["A", "Choice A"],
                ["B", "Choice B"],
                ["C", "Choice C"]
            ]
        };

    The code produced will nest depending on the level at which it was
    targeted. For instance if instead of the above we had done:

    .. code-block:: js+django

        {% defines_to_js defines='package' %}

    The transpilation would be:

    .. code-block::

        const defines = {
            MyModel: {
                FIELD_CHOICES: [
                    ["A", "Choice A"],
                    ["B", "Choice B"],
                    ["C", "Choice C"]
                ]
            }
        };
    """

    include_member_: Callable[[Any], bool] = lambda name, member: name.isupper()  # type: ignore
    const_name_ = "defines"

    members_: Dict[str, Any]

    object_path_: str = ""

    @property
    def members(self) -> Dict[str, Any]:
        """
        The members of the transpilation target that will be transpiled as
        defines.
        """
        return self.members_

    @members.setter
    def members(self, target: Union[ModuleType, Type]):
        self.members_ = {}
        for ancestor in list(reversed(getattr(target, "__mro__", []))) + [target]:
            self.members_.update(
                {
                    name: member
                    for name, member in vars(ancestor).items()
                    if getattr(self, "include_member_")(name, member)
                }
            )

    def include_target(self, target: ResolvedTranspilerTarget):
        if isinstance(target, (type, ModuleType)):
            self.members = target  # type: ignore
            return len(self.members) > 0
        return False

    @property
    def context(self) -> Dict[str, Any]:
        """
        The template render context passed to overrides. In addition to
        :attr:`render_static.transpilers.Transpiler.context`.
        This includes:

            - **const_name**: The name of the const variable
        """
        return {
            **Transpiler.context.fget(self),  # type: ignore
            "const_name": self.const_name_,
        }

    def __init__(
        self,
        include_member: Callable[[Any], bool] = include_member_,
        const_name: str = const_name_,
        **kwargs,
    ) -> None:
        """
        :param include_member: A function that accepts a member name and member
            instance of a class and returns if the member should be written. By
            default this will include any member that is all upper case.
        :param const_name: The name to use for the const variable containing the
            transpiled defines.
        :param kwargs: Set of configuration parameters, see also
            :class:`~render_static.transpilers.base.Transpiler` params
        """
        self.include_member_ = include_member
        self.const_name_ = const_name
        super().__init__(**kwargs)

    def visit(
        self, target: ResolvedTranspilerTarget, is_last: bool, is_final: bool
    ) -> Generator[Optional[str], None, None]:
        """
        Visit a target (module or class) and yield its defines as transpiled
        javascript.

        :param target: The module or class to transpile defines from.
        :param is_last:
        :param is_final:
        :return:
        """
        assert not isinstance(target, AppConfig), (
            "Unsupported transpiler target: AppConfig"
        )
        self.members = target  # type: ignore
        yield from self.visit_members(self.members, is_last=is_last, is_final=is_final)

    def start_visitation(self) -> Generator[Optional[str], None, None]:
        """
        Lay down the const variable declaration.
        """
        yield f"const {self.const_name_} = {{"
        self.indent()

    def end_visitation(self) -> Generator[Optional[str], None, None]:
        """
        Lay down the closing brace for the const variable declaration.
        """
        for _, override in self.overrides_.items():
            yield from override.transpile(Context(self.context))
        self.outdent()
        yield "};"

    def visit_members(
        self, members: Dict[str, Any], is_last: bool, is_final: bool
    ) -> Generator[Optional[str], None, None]:
        """
        Visit the members of a class and yield their rendered javascript.

        :param members: The members of the class to transpile.
        :param is_last: True if this is the last target that will be visited at
            this level.
        :param is_final: True if this is the last target that will be visited
            at all.
        """
        idx = 0
        for name, member in members.items():
            idx += 1
            yield from self.visit_member(
                name,
                member,
                is_last=(idx == len(members) and is_last),
                is_final=(idx == len(members) and is_final),
            )

    def enter_class(
        self, cls: Type[Any], is_last: bool, is_final: bool
    ) -> Generator[Optional[str], None, None]:
        """
        Enter a class and yield its rendered javascript.

        :param cls: The class with defines to transpile
        :param is_last: True if this is the last class that will be visited at
            this level.
        :param is_final: True if this is the last class that will be visited
            at all.
        """
        self.members = cls  # type: ignore
        yield f"{cls.__name__}: {{"
        self.indent()
        self.object_path_ += f"{'.' if self.object_path_ else ''}{cls.__name__}"

    def exit_class(
        self, cls: Type[Any], is_last: bool, is_final: bool
    ) -> Generator[Optional[str], None, None]:
        """
        Exit a class laying down any closing braces.

        :param cls: The class with defines to transpile
        :param is_last: True if this is the last class that will be visited at
            this level.
        :param is_final: True if this is the last class that will be visited
            at all.
        """
        self.outdent()
        yield "},"
        self.object_path_ = ".".join(self.object_path_.split(".")[:-1])

    def visit_member(
        self,
        name: str,
        member: Any,
        is_last: bool = False,
        is_final: bool = False,
    ) -> Generator[Optional[str], None, None]:
        """
        Visit a member of a class and yield its rendered javascript.

        :param name: The name of the class member
        :param member: The member itself
        :param is_last: True if this is the last member of the class
        :param is_final: True if this is the last member that will be visited
            at all
        :yield: Transpiled javascript for the member.
        """
        self.object_path_ += f"{'.' if self.object_path_ else ''}{name}"
        if self.object_path_ in self.overrides_:
            first = True
            for line in self.transpile_override(self.object_path_, self.to_js(member)):
                if first:
                    yield f"{name}: {line}"
                    first = False
                else:
                    yield line
        else:
            yield f"{name}: {self.to_js(member)},"
        self.object_path_ = ".".join(self.object_path_.split(".")[:-1])
