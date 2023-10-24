"""
Transpiler tools for PEP 435 style python enumeration classes.
"""
import sys
from abc import abstractmethod
from enum import Enum, Flag, IntEnum, IntFlag
from typing import (
    Any,
    Collection,
    Dict,
    Generator,
    List,
    Optional,
    Set,
    Type,
    Union,
)

from django.db.models import IntegerChoices, TextChoices
from render_static.transpilers import Transpiler, TranspilerTarget

try:
    from django.utils.decorators import classproperty  # pylint: disable=C0412
except ImportError:
    from django.utils.functional import classproperty


IGNORED_ENUMS = {Enum, IntEnum, IntFlag, Flag, TextChoices, IntegerChoices}
if sys.version_info >= (3, 11):  # pragma: no cover
    from enum import EnumCheck, FlagBoundary, ReprEnum, StrEnum
    IGNORED_ENUMS.update({FlagBoundary, ReprEnum, StrEnum, EnumCheck})


class EnumTranspiler(Transpiler):
    """
    The base javascript transpiler for python PEP 435 Enums. Extend from this
    base class to write custom transpilers.
    """

    def include_target(self, target: TranspilerTarget):
        """
        Deriving transpilers must implement this method to filter targets in
        and out of transpilation. Transpilers are expected to walk module trees
        and pick out supported python artifacts.

        :param target: The python artifact to filter in or out
        :return: True if the target can be transpiled
        """
        if isinstance(target, type) and issubclass(target, Enum):
            return (
                target not in IGNORED_ENUMS and
                target.__module__ != 'enum' and
                # make sure this enum type actually has values
                list(target)
            )
        return False

    @abstractmethod
    def visit(
        self,
        enum: Type[Enum],  # type: ignore
                           # pylint: disable=arguments-renamed
        is_last: bool,
        is_final: bool
    ) -> Generator[Optional[str], None, None]:
        """
        Visit and transpile the given Enum class. Deriving classes must
        implement this function.

        :param enum: The enum class being transpiled
        :param is_last: True if this is the last enum to be transpiled at this
            level.
        :param is_final: True if this is the last enum to be transpiled at all.
        :yield: transpiled javascript lines
        """


class EnumClassWriter(EnumTranspiler):  # pylint: disable=R0902
    """
    A PEP 435 transpiler that generates ES6 style classes in the style of
    https://github.com/rauschma/enumify

    :param class_name: A pattern to use to generate class names. This should
        be a string that will be formatted with the class name of each enum.
        The default string '{}' will resolve to the python class name.
    :param raise_on_not_found: If true, in the transpiled javascript throw a
        TypeError if an Enum instance cannot be mapped to the given value.
        If false, return null
    :param export: If true the classes will be exported - Default: False
    :param include_properties: If true, any python properties present on the
        enums will be included in the transpiled javascript enums.
    :param symmetric_properties: If true, properties that the enums may be
        instantiated from will be automatically determined and included in the
        get() function. If False (default), enums will not be instantiable
        from properties. May also be an iterable of property names to
        treat as symmetric.
    :param exclude_properties: Exclude this list of properties. Only useful if
        include_properties is True
    :param class_properties: If true, include all Django classproperties as
        static members on the transpiled Enum class. May also be an iterable
        of specific property names to include.
    :param kwargs: additional kwargs for the base transpiler classes.
    """

    class_name_pattern_: str = '{}'
    class_name_: str
    class_name_map_: Dict[Type[Enum], str] = {}

    raise_on_not_found_: bool = True

    export_: bool = False

    symmetric_properties_kwarg_: Union[bool, Collection[str]] = False
    symmetric_properties_: List[str] = []

    class_properties_kwarg_: Union[bool, Collection[str]] = True
    class_properties_: List[str] = []

    include_properties_: bool = True
    builtins_: List[str] = ['value', 'name']
    properties_: List[str] = []
    exclude_properties_: Set[str]

    str_prop_: Optional[str] = None
    str_is_prop_: bool = False

    def to_js(self, value: Any):
        """
        Return the javascript transpilation of the given value. For enum values
        we first determine if the given enum was also transpiled and if so
        use its transpiled name to instantiate it - otherwise default enum
        transpilation is used which simply transpiles the value.

        :param value: The value to transpile
        :return: A valid javascript code that represents the value
        """
        if isinstance(value, Enum):
            if value.__class__ in self.class_name_map_:
                return f'{self.class_name_map_[value.__class__]}.{value.name}'
        return self.to_javascript(value)

    @property
    def class_name(self):
        """Get the class name for the enum being transpiled"""
        return self.class_name_

    @class_name.setter
    def class_name(self, enum):
        """
        Generate the class name for the enum being transpiled from the
        configured pattern.

        :param enum: The enum class being transpiled
        """
        self.class_name_ = self.class_name_pattern_.format(enum.__name__)
        self.class_name_map_[enum] = self.class_name_

    @property
    def properties(self):
        """The properties to include in the transpiled javascript class"""
        return self.properties_

    @properties.setter
    def properties(self, enum: Type[Enum]):
        """
        Determine the properties to include in the transpiled javascript class
        through introspection.

        :param enum: The enum class being transpiled
        """
        builtins = [
            bltin for bltin in self.builtins_
            if bltin not in self.exclude_properties_
        ]
        if self.include_properties_:
            if (
                hasattr(list(enum)[0], 'label') and
                'label' not in builtins and
                'label' not in self.exclude_properties_
            ):
                builtins.append('label')
            props_on_class = [
                str(name)
                for name, member in vars(enum).items()
                if (
                    isinstance(member, property) and
                    name not in self.exclude_properties_
                    and str(name) not in builtins
                )
            ]
            self.properties_ = [
                *builtins,
                *props_on_class,
                # handle enum-properties defined properties
                *[
                    prop for prop in getattr(enum, '_properties_', [])
                    if prop not in self.exclude_properties_
                    and prop not in builtins and prop not in props_on_class
                ]
            ]
        else:
            self.properties_ = builtins

    @property
    def symmetric_properties(self):
        """
        The list of properties that enum values can be instantiated from
        """
        return self.symmetric_properties_

    @symmetric_properties.setter
    def symmetric_properties(self, enum: Type[Enum]):
        """
        Set the list of properties that enum values can be instantiated from.
        If symmetric_properties_ is True, determine the list of symmetric
        properties by walking through all the properties and figuring out
        which properties the Enum can be instantiated from.

        :param enum: The enum class being transpiled
        """
        if self.symmetric_properties_kwarg_ is True:
            self.symmetric_properties_ = []
            for prop in self.properties:
                if prop == 'value':
                    continue
                count = 0
                for enm in enum:
                    try:
                        if enum(getattr(enm, prop)) is enm:
                            count += 1
                    except (TypeError, ValueError):
                        pass
                if count == len(enum):
                    self.symmetric_properties_.append(prop)

        elif self.symmetric_properties_kwarg_ is False:
            self.symmetric_properties_ = []
        else:
            self.symmetric_properties_ = [
                prop for prop in self.symmetric_properties_kwarg_
                if hasattr(enum(enum.values[0]), prop)  # type: ignore
            ]

    @property
    def class_properties(self):
        """
        The list of class properties on the enum class that should be
        transpiled.
        """
        return self.class_properties_

    @class_properties.setter
    def class_properties(self, enum: Type[Enum]):
        """
        Either set the class properties to the given set, or if true set to
        the set of all Django classproperties on the enum class

        :param enum: The enum class to transpile
        """
        if self.class_properties_kwarg_ is True:
            self.class_properties_ = [
                name for name, member in vars(enum).items()
                if isinstance(member, classproperty)
            ]
        elif self.class_properties_kwarg_ is False:
            self.class_properties_ = []
        else:
            self.class_properties_ = [
                prop for prop in self.class_properties_kwarg_
                if hasattr(enum, prop)
            ]

    @property
    def str_prop(self):
        """
        The property that is the string representation of the field or
        None if the string is different
        """
        return self.str_prop_

    @str_prop.setter
    def str_prop(self, enum: Type[Enum]):
        """
        Determine the property that is the string representation of the
        enumeration if one exists.

        :param enum: The enum class being transpiled
        """
        self.str_is_prop_ = False
        prop_matches: Dict[str, int] = {}
        for enm in enum:
            for prop in self.properties:
                if getattr(enm, prop) == str(enm):
                    prop_matches.setdefault(prop, 0)
                    prop_matches[prop] += 1

        for prop, count in prop_matches.items():
            if count == len(enum):
                self.str_prop_ = prop
                self.str_is_prop_ = True
                return

        candidate = 'str'
        idx = 0
        while candidate in self.properties:
            candidate = f'str{idx}'
            idx += 1
        self.str_prop_ = candidate

    def __init__(  # pylint: disable=R0913
            self,
            class_name: str = class_name_pattern_,
            raise_on_not_found: bool = raise_on_not_found_,
            export: bool = export_,
            include_properties: bool = include_properties_,
            symmetric_properties: Union[
                bool,
                Collection[str]
            ] = symmetric_properties_kwarg_,
            exclude_properties: Optional[Collection[str]] = None,
            class_properties: Union[
                bool,
                Collection[str]
            ] = class_properties_kwarg_,
            **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.class_name_pattern_ = class_name
        self.raise_on_not_found_ = raise_on_not_found
        self.export_ = export
        self.include_properties_ = include_properties
        self.symmetric_properties_kwarg_ = symmetric_properties
        self.exclude_properties_ = (
            set(exclude_properties)
            if exclude_properties else set()
        )
        self.class_properties_kwarg_ = class_properties
        self.class_name_map_ = {}

    def visit(
            self,
            enum: Type[Enum],  # type: ignore
                               # pylint: disable=arguments-renamed
            is_last: bool,
            is_final: bool  # pylint: disable=unused-argument
    ) -> Generator[Optional[str], None, None]:
        """
        Transpile the enum in sections.

        :param enum: The enum class being transpiled
        :param is_last: True if this is the last enum to be transpiled at this
            level.
        :param is_final: True if this is the last enum to be transpiled at all.
        :yield: transpiled javascript lines
        """
        self.class_name = enum
        self.properties = enum
        self.str_prop = enum
        self.class_properties = enum
        self.symmetric_properties = enum
        yield from self.declaration(enum)
        self.indent()
        yield ''
        yield from self.enumerations(enum)
        yield ''
        if self.class_properties:
            yield from self.static_properties(enum)
            yield ''
        yield from self.constructor(enum)
        yield ''
        yield from self.to_string(enum)
        yield ''
        yield from self.getter(enum)
        yield ''
        yield from self.iterator(enum)
        self.outdent()
        yield '}'

    def declaration(  # pylint: disable=W0613
            self,
            enum: Type[Enum]
    ) -> Generator[Optional[str], None, None]:
        """
        Transpile the class declaration.

        :param enum: The enum being transpiled
        :yield: transpiled javascript lines
        """
        yield f'{"export " if self.export_ else ""}class {self.class_name} {{'

    def enumerations(
            self,
            enum: Type[Enum]
    ) -> Generator[Optional[str], None, None]:
        """
        Transpile the enumeration value instances as static member on the class

        :param enum: The enum class being transpiled
        :yield: transpiled javascript lines
        """
        for enm in enum:
            values = [
                self.to_js(getattr(enm, prop)) for prop in self.properties
            ]
            if not self.str_is_prop_:
                values.append(self.to_js(str(enm)))
            yield (
                f'static {enm.name} = new {self.class_name}'
                f'({", ".join(values)});'
            )

    def static_properties(
            self,
            enum: Type[Enum]
    ) -> Generator[Optional[str], None, None]:
        """
        Transpile any classproperties as static members on the class.

        :param enum: The enum class being transpiled
        :yield: transpiled javascript lines
        """
        for prop in self.class_properties:
            yield f'static {prop} = {self.to_js(getattr(enum, prop))};'

    def constructor(  # pylint: disable=W0613
            self,
            enum: Type[Enum]
    ) -> Generator[Optional[str], None, None]:
        """
        Transpile the constructor for the enum instances.

        :param enum: The enum class being transpiled
        :yield: transpiled javascript lines
        """
        props = [
            *self.properties,
            *([] if self.str_is_prop_ else [self.str_prop])
        ]
        yield f'constructor ({", ".join(props)}) {{'
        self.indent()
        for prop in self.properties:
            yield f'this.{prop} = {prop};'
        if not self.str_is_prop_:
            yield f'this.{self.str_prop} = {self.str_prop};'
        self.outdent()
        yield '}'

    def to_string(  # pylint: disable=W0613
            self,
            enum: Type[Enum]
    ) -> Generator[Optional[str], None, None]:
        """
        Transpile the toString() method that converts enum instances to
        strings.

        :param enum: The enum class being transpiled
        :yield: transpiled javascript lines
        """
        yield 'toString() {'
        self.indent()
        yield f'return this.{self.str_prop};'
        self.outdent()
        yield '}'

    def getter(self, enum: Type[Enum]) -> Generator[Optional[str], None, None]:
        """
        Transpile the get() method that converts values and properties into
        instances of the Enum type.

        :param enum: The enum class being transpiled
        :yield: transpiled javascript lines
        """
        yield 'static get(value) {'
        self.indent()

        for prop in ['value'] + self.symmetric_properties:
            yield from self.prop_getter(enum, prop)

        if self.raise_on_not_found_:
            yield f'throw new TypeError(`No {self.class_name} ' \
                  f'enumeration maps to value ${{value}}`);'
        else:
            yield 'return null;'
        self.outdent()
        yield '}'

    def prop_getter(
            self,
            enum: Type[Enum],
            prop: str
    ) -> Generator[Optional[str], None, None]:
        """
        Transpile the switch statement to map values of the given property to
        enumeration instance values.

        :param enum: The enum class being transpiled
        :param prop:
        :yield: transpiled javascript lines
        """
        yield 'switch(value) {'
        self.indent()
        for enm in enum:
            yield f'case {self.to_js(getattr(enm, prop))}:'
            self.indent()
            yield f'return {self.class_name}.{enm.name};'
            self.outdent()
        self.outdent()
        yield '}'

    def iterator(
            self,
            enum: Type[Enum]
    ) -> Generator[Optional[str], None, None]:
        """
        Transpile the iterator for iterating through enum value instances.

        :param enum: The enum class being transpiled
        :yield: transpiled javascript lines
        """
        enums = [f'{self.class_name}.{enm.name}' for enm in enum]
        yield 'static [Symbol.iterator]() {'
        self.indent()
        yield f'return [{", ".join(enums)}][Symbol.iterator]();'
        self.outdent()
        yield '}'
