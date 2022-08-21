from render_static.javascript import JavaScriptGenerator
from typing import Generator, Optional
from enum import Enum


class EnumVisitor(JavaScriptGenerator):

    expected_properties = [
        'name',
        'value',
        'label'
    ]

    def generate(self, enum: Enum) -> str:
        """
        Implements JavaScriptGenerator::generate. Calls the visitation entry
        point and writes all the yielded JavaScript lines to a member string
        which is returned.

        :param enum: The enumeration class to generate javascript for
        :return: The rendered enum as javascript.
        """
        for line in self.visit(enum):
            self.write_line(line)
        return self.rendered_

    def visit(self, enum: Enum) -> Generator[str, None, None]:
        """
        Visit the enumeration, yielding JavaScript where needed.

        :param enum: The URL tree, in the format returned by build_tree().
        :yield: JavaScript lines
        """
        yield from self.start_visitation(enum)
        self.indent()
        yield from self.visit_enum(enum)
        self.outdent()
        yield from self.end_visitation(enum)

    def start_visitation(self, enum: Enum) -> Generator[str, None, None]:
        """
        Begin visitation of the tree - noop

        :yield: writes nothing
        """
        yield None  # type: ignore

    def end_visitation(self, enum: Enum) -> Generator[str, None, None]:
        """
        End visitation of the tree - noop

        :yield: writes nothing
        """
        yield None  # type: ignore

    def visit_enum(self, enum: Enum) -> Generator[str, None, None]:
        for value in enum:
            yield from self.visit_value(value)

    def visit_value(self, enum_value):
        


class EnumClassWriter(EnumVisitor):

    class_name: Optional[str] = None
    raise_on_not_found_: bool = True

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.class_name_ = kwargs.pop(
            'class_name',
            self.class_name
        )
        self.raise_on_not_found_ = kwargs.pop(
            'raise_on_not_found',
            self.raise_on_not_found_
        )

    def visit(self, enum: Enum) -> Generator[str, None, None]:
        self.class_name = self.class_name or enum.__class__.__name__
        yield from super().visit(enum)

    def start_visitation(self, enum: Enum) -> Generator[str, None, None]:
        """
        Begin visitation of the tree - noop

        :yield: writes nothing
        """
        yield None  # type: ignore

    def end_visitation(self, enum: Enum) -> Generator[str, None, None]:
        """
        End visitation of the tree - noop

        :yield: writes nothing
        """
        yield None  # type: ignore