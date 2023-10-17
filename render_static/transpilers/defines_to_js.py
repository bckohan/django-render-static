"""
Built-in transpilers for python classes. Only one is provided that transpiles
plain old data found on classes and their ancestors.
"""
from typing import Any, Callable, Dict, Generator, Type, Union
from render_static.transpilers import Transpiler, ResolvedTranspilerTarget
from types import ModuleType


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

    :param include_member: A function that accepts a member name and member
        instance of a class and returns if the member should be written. By
        default this will include any member that is all upper case.
    :param const_name: The name to use for the const variable containing the
        transpiled defines.
    :param kwargs: Set of configuration parameters, see also
        `Transpiler` params
    """

    include_member_: Callable[[Any], bool] = (
        lambda name, member: name.isupper()  # type: ignore
    )
    const_name_ = 'defines'

    members_: Dict[str, Any]

    @property
    def members(self) -> Dict[str, Any]:
        return self.members_

    @members.setter
    def members(self, target: Union[ModuleType, Type[Any]]):
        self.members_ = {}
        for ancestor in (
            list(reversed(getattr(target, '__mro__', []))) + [target]
        ):
            self.members_.update({
                name: member
                for name, member in vars(ancestor).items()
                if getattr(self, 'include_member_')(name, member)
            })

    def include_target(self, target: ResolvedTranspilerTarget):
        if isinstance(target, (type, ModuleType)):
            self.members = target
            return len(self.members) > 0
        return False

    def __init__(
        self,
        include_member: Callable[[Any], bool] = include_member_,
        const_name: str = const_name_,
        **kwargs
    ) -> None:
        self.include_member_ = include_member
        self.const_name_ = const_name
        super().__init__(**kwargs)

    def visit(
            self,
            target: Union[ModuleType, Type[Any]],
            is_last: bool,
            is_final: bool
    ) -> Generator[str, None, None]:
        self.members = target
        yield from self.visit_members(
            self.members,
            is_last=is_last,
            is_final=is_final
        )

    def start_visitation(self) -> Generator[str, None, None]:
        yield f'const {self.const_name_} = {{'
        self.indent()

    def end_visitation(self) -> Generator[str, None, None]:
        self.outdent()
        yield '};'

    def visit_members(
            self,
            members: Dict[str, Any],
            is_last: bool,
            is_final: bool
    ) -> Generator[str, None, None]:
        idx = 0
        for name, member in members.items():
            idx += 1
            yield from self.visit_member(
                name,
                member,
                is_last=(idx == len(members) and is_last),
                is_final=(idx == len(members) and is_final)
            )

    def enter_class(
            self,
            cls: Type[Any],
            is_last: bool,
            is_final: bool
    ) -> Generator[str, None, None]:
        self.members = cls
        if self.members:
            yield f'{cls.__name__}: {{'
            self.indent()

    def exit_class(
            self,
            cls: Type[Any],
            is_last: bool,
            is_final: bool
    ) -> Generator[str, None, None]:
        if self.members:
            self.outdent()
            yield f'}},'

    def visit_member(
        self,
        name: str,
        member: Any,
        is_last: bool = False,
        is_final: bool = False
    ) -> Generator[str, None, None]:
        """
        Visit a member of a class and yield its rendered javascript.

        :param name: The name of the class member
        :param member: The member itself
        :param is_last: True if this is the last member of the class
        :param is_final: True if this is the last member that will be visited at
            all
        :yield: Transpiled javascript for the member.
        """
        yield f'{name}: {self.to_js(member)},'


"""
class ClassPODTranspiler(DefaultDefineTranspiler):
    
    class_name_ = '{}'
    module_name_ = '{}'
    
    def __init__(
        self,
        class_name=class_name_,
        module_name=module_name_,
        **kwargs
    ) -> None:
        self.class_name_ = class_name
        self.module_name_ = module_name
        super().__init__(**kwargs)
"""