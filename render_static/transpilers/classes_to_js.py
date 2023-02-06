"""
Built-in transpilers for python classes. Only one is provided that transpiles
plain old data found on classes and their ancestors.
"""
import inspect
from abc import abstractmethod
from typing import Any, Callable, Collection, Generator, Type, Union

from django.utils.module_loading import import_string
from render_static.transpilers import JavaScriptGenerator


class PythonClassVisitor(JavaScriptGenerator):
    """
    An abstract JavaScriptGenerator that transpiles python classes to
    JavaScript. Transpilers used with classes_to_js must inherit from this
    base class visitor.
    """

    def generate(
        self,
        classes: Union[Collection[Union[Type, str]], Union[Type, str]]
    ) -> str:
        """
        Implements JavaScriptGenerator::generate. Calls the visitation entry
        point and writes all the yielded JavaScript lines to a member string
        which is returned.

        :param classes: The class or list of classes or import strings of
            classes to transpile
        :return: The rendered class(es) as javascript.
        """
        if not isinstance(classes, Collection) or isinstance(classes, str):
            classes = [classes]
        for idx, cls in enumerate(classes):
            if isinstance(cls, str):
                cls = import_string(cls)
            if not inspect.isclass(cls):
                raise ValueError(f'{cls} must be a class!')
            for line in self.visit_class(cls, (idx == len(classes) - 1)):
                self.write_line(line)
        return self.rendered_

    @abstractmethod
    def visit_class(
        self,
        cls: Type,
        is_last: bool = False
    ) -> Generator[str, None, None]:
        """
        Deriving classes must implement this method to transpile and yield the
        javascript for the given class.

        :param cls: The class to transpile
        :param is_last: True if this is the last class to be visited.
        :yield: transpiled JavaScript
        """


class DefaultClassWriter(PythonClassVisitor):
    """
    A JavascriptGenerator that transpiles plain old data in python classes
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

        var defines = {
            {% classes_to_js
                classes='package.MyModel'
                transpiler='render_static.SimplePODWriter'
            %}
        };

    This will produce JavaScript you may invoke like so:

    .. code-block::

        var defines = {
            FIELD_CHOICES: [
                ["A", "Choice A"],
                ["B", "Choice B"],
                ["C", "Choice C"]
            ]
        };

    :param include_member: A function that accepts a member name and member
        instance of a class and returns if the member should be written. By
        default this will include any member that is all upper case.
    :param kwargs: Set of configuration parameters, see also
        `JavascriptGenerator` params
    """

    include_member_: Callable[[Any], bool] = (
        lambda name, member: name.isupper()  # type: ignore
    )

    def __init__(
        self,
        include_member: Callable[[Any], bool] = include_member_,
        **kwargs
    ) -> None:
        self.include_member_ = include_member
        super().__init__(**kwargs)

    def visit_class(
        self,
        cls: Type,
        is_last: bool = False
    ) -> Generator[str, None, None]:
        """
        Convert python class defines to javascript.

        :param cls: The class to visit and yield javascript for
        :param is_last: True if this is the last class to be visited.
        :yield: The class transpiled to javascript
        """
        members = {}
        for ancestor in list(reversed(cls.__mro__)) + [cls]:
            members.update({
                name: member
                for name, member in vars(ancestor).items()
                if getattr(self, 'include_member_')(name, member)
            })

        if not members:
            return

        yield f"{cls.__name__}: {{"
        self.indent()
        idx = 0
        for name, member in members.items():
            idx += 1
            yield from self.visit_member(
                name,
                member,
                is_last=(idx == len(members))
            )
        self.outdent()
        yield f'}}{"" if is_last else ","}'

    def visit_member(
        self,
        name: str,
        member: Any,
        is_last: bool = False
    ) -> Generator[str, None, None]:
        """
        Visit a member of a class and yield its rendered javascript.

        :param name: The name of the class member
        :param member: The member itself
        :param is_last: True if this is the last memeber of the class
        :yield: Transpiled javascript for the member.
        """
        yield f'{name}: {self.to_js(member)}{"" if is_last else ","}'
