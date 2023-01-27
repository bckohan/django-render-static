from enum import Enum
from typing import Generator, Optional, Type, List
from render_static.transpilers import JavaScriptGenerator


class EnumVisitor(JavaScriptGenerator):
    expected_properties = [
        'name',
        'label'
    ]

    def __init__(self, indent=None, level=None, **kwargs) -> None:
        super().__init__(indent=indent, level=level)

    def generate(self, enum: Type[Enum]) -> str:
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

    def visit(self, enum: Type[Enum]) -> Generator[str, None, None]:
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

    def start_visitation(self, enum: Type[Enum]) -> Generator[str, None, None]:
        """
        Begin visitation of the tree - noop

        :yield: writes nothing
        """
        yield None  # type: ignore

    def end_visitation(self, enum: Type[Enum]) -> Generator[str, None, None]:
        """
        End visitation of the tree - noop

        :yield: writes nothing
        """
        yield None  # type: ignore

    def visit_enum(self, enum: Type[Enum]) -> Generator[str, None, None]:
        """
        Visit the enum.

        :param enum:
        :return:
        """


class EnumClassWriter(EnumVisitor):
    class_name_: Optional[str] = '{}'
    raise_on_not_found_: bool = True
    export_ = True
    include_properties_ = True
    symmetric_properties_ = None
    exclude_properties_ = None

    def __init__(
            self,
            class_name: str = class_name_,
            raise_on_not_found: bool = raise_on_not_found_,
            export: bool = export_,
            include_properties: bool = include_properties_,
            symmetric_properties: List[str] = symmetric_properties_,
            exclude_properties: List[str] = exclude_properties_,
            **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.class_name_ = class_name
        self.raise_on_not_found_ = raise_on_not_found
        self.export_ = export
        self.include_properties_ = include_properties
        self.symmetric_properties_ = symmetric_properties or []
        self.exclude_properties_ = (
            set(exclude_properties)
            if exclude_properties else set()
        )

    def visit(self, enum: Type[Enum]) -> Generator[str, None, None]:
        self.class_name_.format(enum.__name__)
        yield from super().visit(enum)

    def start_visitation(self, enum: Type[Enum]) -> Generator[str, None, None]:
        """
        Begin visitation of the enum.

        :yield: declaration string
        """
        yield from self.declaration(enum)

    def visit_enum(self, enum: Type[Enum]) -> Generator[str, None, None]:
        """
        Visit the enum.

        :param enum:
        :return:
        """
        yield from self.constructor(enum)

    def declaration(self, enum: Type[Enum]) -> Generator[str, None, None]:
        yield f'{"export " if self.export_ else ""}class {self.class_name_} {{'

    def constructor(self, enum: Type[Enum]) -> Generator[str, None, None]:
        yield 'constructor () {'

    def end_visitation(self, enum: Type[Enum]) -> Generator[str, None, None]:
        """
        End visitation of the enum

        :yield: writes class closing paren
        """
        yield '}'

    def get_properties(self, enum: Type[Enum]) -> List[str]:
        if self.include_properties_:
            return [
                       name
                       for name, member in vars(enum).items()
                       if (
                        isinstance(member, property) and
                        member not in self.exclude_properties_
                )
                   ] + [
                       expected for expected in self.expected_properties
                       if expected in vars(enum)
                   ]
        return []


"""
class SLMFileType {

    static SITE_LOG = new SLMFileType(1, 'Site Log');
    static SITE_IMAGE = new SLMFileType(2, 'Site Image');
    static ATTACHMENT = new SLMFileType(3, 'Attachment');

    constructor(val, label) {
        this.val = val;
        this.label = label;
    }

    toString() {
        return this.label;
    }

    static get(val) {
        switch(val) {
            case 1:
                return SLMFileType.SITE_LOG;
            case 2:
                return SLMFileType.SITE_IMAGE;
            case 3:
                return SLMFileType.ATTACHMENT;
        }
        return null;
    }
}
"""
