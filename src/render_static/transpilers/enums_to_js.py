"""
Transpiler tools for PEP 435 style python enumeration classes.
"""

import sys
import warnings
from abc import abstractmethod
from enum import Enum, Flag, IntEnum, IntFlag, auto
from typing import Any, Collection, Dict, Generator, List, Optional, Set, Type, Union

from django.db.models import IntegerChoices, TextChoices
from django.template.context import Context

from render_static.transpilers.base import Transpiler, TranspilerTarget

try:
    from django.utils.decorators import classproperty  # type: ignore[attr-defined]
except ImportError:
    from django.utils.functional import classproperty


IGNORED_ENUMS = {Enum, IntEnum, IntFlag, Flag, TextChoices, IntegerChoices}
if sys.version_info >= (3, 11):
    from enum import EnumCheck, FlagBoundary, ReprEnum, StrEnum

    IGNORED_ENUMS.update({FlagBoundary, ReprEnum, StrEnum, EnumCheck})


class UnrecognizedBehavior(Enum):
    """
    Enumeration of behaviors when a value cannot be mapped to an enum instance:
    """

    THROW_EXCEPTION = auto()
    """
    Throw a TypeError if the value cannot be mapped to an enum instance.
    """

    RETURN_NULL = auto()
    """
    Return null if the value cannot be mapped to an enum instance.
    """

    RETURN_INPUT = auto()
    """
    Return the input value if the value cannot be mapped to an enum instance.
    """


class EnumTranspiler(Transpiler):
    """
    The base javascript transpiler for python PEP 435 Enums. Extend from this
    base class to write custom transpilers.
    """

    def include_target(self, target: TranspilerTarget) -> bool:
        """
        Deriving transpilers must implement this method to filter targets in
        and out of transpilation. Transpilers are expected to walk module trees
        and pick out supported python artifacts.

        :param target: The python artifact to filter in or out
        :return: True if the target can be transpiled
        """
        if isinstance(target, type) and issubclass(target, Enum):
            return bool(
                target not in IGNORED_ENUMS
                and target.__module__ != "enum"
                and
                # make sure this enum type actually has values
                list(target)
            )
        return False

    @abstractmethod
    def visit(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        enum: Type[Enum],  # type: ignore
        is_last: bool,
        is_final: bool,
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


class EnumClassWriter(EnumTranspiler):
    """
    A PEP 435 transpiler that generates ES6 style classes in the style of
    https://github.com/rauschma/enumify
    """

    enum_: Type[Enum]

    class_name_pattern_: str = "{}"
    class_name_: str
    class_name_map_: Dict[Type[Enum], str] = {}

    on_unrecognized_: UnrecognizedBehavior = UnrecognizedBehavior.THROW_EXCEPTION

    export_: bool = False

    symmetric_properties_kwarg_: Union[bool, Collection[str]] = False
    symmetric_properties_: List[str] = []
    find_ci_: bool = True
    isymmetric_properties_: List[str] = []

    class_properties_kwarg_: Union[bool, Collection[str]] = True
    class_properties_: List[str] = []

    include_properties_: Union[Collection[str], bool] = True
    builtins_: List[str] = ["value", "name"]
    properties_: List[str] = []
    exclude_properties_: Set[str]

    str_prop_: Optional[str] = None
    str_is_prop_: bool = False
    to_string_: Union[bool, str] = True

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
                return f"{self.class_name_map_[value.__class__]}.{value.name}"
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
            bltin
            for bltin in self.builtins_
            if bltin == "value" or bltin not in self.exclude_properties_
        ]
        if (
            hasattr(list(enum)[0], "label")
            and "label" not in builtins
            and "label" not in self.exclude_properties_
            and self.include_properties_
        ):
            builtins.append("label")

        props_on_class = [
            str(name)
            for name, member in vars(enum).items()
            if (
                isinstance(member, property)
                and name not in self.exclude_properties_
                and str(name) not in builtins
            )
        ]
        prop_def_order = [
            *builtins,
            *[
                prop
                for prop in getattr(enum, "_properties_", [])
                if prop not in self.exclude_properties_
                and prop not in builtins
                and prop not in props_on_class
            ],
            *props_on_class,
        ]
        if self.include_properties_ is True:
            self.properties_ = prop_def_order
        elif self.include_properties_:
            self.properties_ = [
                prop
                for prop in prop_def_order
                if prop in self.include_properties_ or prop == "value"
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
            self.isymmetric_properties_ = (
                [] if self.find_ci_ else self.isymmetric_properties_
            )

            def ever_other_case(test_str: str) -> str:
                return "".join(
                    c.upper() if i % 2 == 0 else c.lower()
                    for i, c in enumerate(test_str)
                )

            for prop in self.properties:
                if prop == "value":
                    continue
                count = 0
                i_count = 0
                for enm in enum:
                    try:
                        e_prop = getattr(enm, prop)
                        count += int(enum(e_prop) is enm)
                        i_count += int(
                            self.find_ci_
                            and isinstance(e_prop, str)
                            and enum(e_prop.swapcase()) is enm
                            and enum(ever_other_case(e_prop)) is enm
                        )
                    except (TypeError, ValueError):
                        pass
                if count == len(enum):
                    self.symmetric_properties_.append(prop)
                    if self.find_ci_ and i_count == count:
                        self.isymmetric_properties_.append(prop)
        elif self.symmetric_properties_kwarg_ is False:
            self.symmetric_properties_ = []
        else:
            self.symmetric_properties_ = [
                prop
                for prop in self.symmetric_properties_kwarg_
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
                name
                for name, member in vars(enum).items()
                if isinstance(member, classproperty)
            ]
        elif self.class_properties_kwarg_ is False:
            self.class_properties_ = []
        else:
            self.class_properties_ = [
                prop for prop in self.class_properties_kwarg_ if hasattr(enum, prop)
            ]

    @property
    def str_is_prop(self):
        """
        True if toString() is a property, False otherwise.
        """
        if self.to_string_ and isinstance(self.to_string_, str):
            return True
        return self.str_is_prop_

    @property
    def str_prop(self):
        """
        The property that is the string representation of the field or
        None if the string is different
        """
        if self.to_string_ and isinstance(self.to_string_, str):
            return self.to_string_
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

        candidate = "str"
        idx = 0
        while candidate in self.properties:
            candidate = f"str{idx}"
            idx += 1
        self.str_prop_ = candidate

    @property
    def enum(self):
        """The enum class being transpiled"""
        return self.enum_

    @enum.setter
    def enum(self, enum: Type[Enum]):
        """
        Set the enum class being transpiled

        :param enum: The enum class being transpiled
        """
        self.enum_ = enum
        self.class_name = enum
        self.properties = enum
        self.str_prop = enum
        self.class_properties = enum
        self.symmetric_properties = enum

    @property
    def context(self):
        """
        The template render context passed to overrides. In addition to
        :attr:`render_static.transpilers.Transpiler.context`.
        This includes:

            - **enum**: The enum class being transpiled
            - **class_name**: The name of the transpiled class
            - **properties**: A list of property names of the enum to transpile
            - **str_prop**: The name of the string property of the enum
            - **class_properties**: A list of the class property names of
              the enum to transpile
            - **symmetric_properties**: The list of property names that the
              enum can be instantiated from
            - **to_string**: Boolean, True if the enum should have a
              toString() method
        """
        return {
            **EnumTranspiler.context.fget(self),  # type: ignore
            "enum": self.enum,
            "class_name": self.class_name,
            "properties": self.properties,
            "str_prop": self.str_prop,
            "class_properties": self.class_properties,
            "symmetric_properties": self.symmetric_properties,
            "to_string": self.to_string_,
        }

    def __init__(
        self,
        class_name: str = class_name_pattern_,
        on_unrecognized: Union[str, UnrecognizedBehavior] = on_unrecognized_,
        export: bool = export_,
        include_properties: Union[bool, Collection[str]] = include_properties_,
        symmetric_properties: Union[
            bool, Collection[str]
        ] = symmetric_properties_kwarg_,
        exclude_properties: Optional[Collection[str]] = None,
        class_properties: Union[bool, Collection[str]] = class_properties_kwarg_,
        to_string: Union[bool, str] = to_string_,
        isymmetric_properties: Optional[Union[Collection[str], bool]] = None,
        **kwargs,
    ) -> None:
        """
        :param class_name: A pattern to use to generate class names. This should
            be a string that will be formatted with the class name of each enum.
            The default string '{}' will resolve to the python class name.
        :param on_unrecognized: If the given value cannot be mapped to an
            enum instance, either "THROW_EXCEPTION", "RETURN_NULL", or
            "RETURN_INPUT". See
            :class:`render_static.transpilers.enums_to_js.UnrecognizedBehavior`.
        :param export: If true the classes will be exported - Default: False
        :param include_properties: If true, any python properties present on the
            enums will be included in the transpiled javascript enums. May also
            be an iterable of property names to include. `value` will always
            be included.
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
        :param to_string: If true (default) include a toString() method that
            returns a string representation of the enum. If a non-empty string,
            use that string as the name of the property to return from toString().
        :param isymmetric_properties: If provided, case insensitive symmetric
            properties will be limited to those listed. If not provided, case
            insensitive properties will be dynamically determined. Provide
            an empty list to disable case insensitive properties.
        :param kwargs: additional kwargs for the base transpiler classes.
        """
        super().__init__(**kwargs)
        self.class_name_pattern_ = class_name
        raise_on_not_found = kwargs.pop("raise_on_not_found", None)
        self.on_unrecognized_ = (
            UnrecognizedBehavior[on_unrecognized]
            if isinstance(on_unrecognized, str)
            else on_unrecognized
        )
        if raise_on_not_found is not None:
            warnings.warn(
                "raise_on_not_found is deprecated, use on_unrecognized instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            self.on_unrecognized_ = (
                UnrecognizedBehavior.THROW_EXCEPTION
                if raise_on_not_found
                else UnrecognizedBehavior.RETURN_NULL
            )
        self.export_ = export
        self.include_properties_ = include_properties
        self.include_properties_ = (
            set(include_properties)
            if isinstance(include_properties, Collection)
            else include_properties
        )
        self.symmetric_properties_kwarg_ = symmetric_properties
        self.exclude_properties_ = (
            set(exclude_properties) if exclude_properties else set()
        )
        self.class_properties_kwarg_ = class_properties
        self.class_name_map_ = {}
        self.to_string_ = to_string
        self.find_ci_ = isymmetric_properties in [True, None]
        self.isymmetric_properties_ = (
            list(isymmetric_properties or [])  # type: ignore
            if isymmetric_properties not in [True, None]
            else []
        )

    def visit(
        self,
        enum: Type[Enum],  # type: ignore
        is_last: bool,
        is_final: bool,
    ) -> Generator[Optional[str], None, None]:
        """
        Transpile the enum in sections.

        :param enum: The enum class being transpiled
        :param is_last: True if this is the last enum to be transpiled at this
            level.
        :param is_final: True if this is the last enum to be transpiled at all.
        :yield: transpiled javascript lines
        """
        self.enum = enum
        yield from self.declaration(enum)
        self.indent()
        yield ""
        yield from self.enumerations(enum)
        yield ""
        if self.class_properties:
            yield from self.static_properties(enum)
            yield ""
        yield from self.constructor(enum)
        yield ""
        if self.isymmetric_properties_:
            yield from self.ci_compare()
            yield ""
        if self.to_string_:
            yield from self.to_string(enum)
            yield ""
        if "get" in self.overrides_:
            yield from self.transpile_override("get", self.getter_impl())
        else:
            yield from self.getter()
        yield ""
        yield from self.iterator(enum)
        for _, override in self.overrides_.items():
            yield from override.transpile(Context(self.context))
        self.outdent()
        yield "}"

    def declaration(self, enum: Type[Enum]) -> Generator[Optional[str], None, None]:
        """
        Transpile the class declaration.

        :param enum: The enum being transpiled
        :yield: transpiled javascript lines
        """
        yield f"{'export ' if self.export_ else ''}class {self.class_name} {{"

    def enumerations(self, enum: Type[Enum]) -> Generator[Optional[str], None, None]:
        """
        Transpile the enumeration value instances as static member on the class

        :param enum: The enum class being transpiled
        :yield: transpiled javascript lines
        """
        for enm in enum:
            values = [self.to_js(getattr(enm, prop)) for prop in self.properties]
            if not self.str_is_prop and self.to_string_:
                values.append(self.to_js(str(enm)))
            yield (f"static {enm.name} = new {self.class_name}({', '.join(values)});")

    def static_properties(
        self, enum: Type[Enum]
    ) -> Generator[Optional[str], None, None]:
        """
        Transpile any classproperties as static members on the class.

        :param enum: The enum class being transpiled
        :yield: transpiled javascript lines
        """
        for prop in self.class_properties:
            yield f"static {prop} = {self.to_js(getattr(enum, prop))};"

    def constructor(self, enum: Type[Enum]) -> Generator[Optional[str], None, None]:
        """
        Transpile the constructor for the enum instances.

        :param enum: The enum class being transpiled
        :yield: transpiled javascript lines
        """
        props = [
            *self.properties,
            *([] if self.str_is_prop or not self.to_string_ else [self.str_prop]),
        ]

        def constructor_impl() -> Generator[str, None, None]:
            for prop in self.properties:
                yield f"this.{prop} = {prop};"
            if not self.str_is_prop and self.to_string_:
                yield f"this.{self.str_prop} = {self.str_prop};"

        if "constructor" in self.overrides_:
            yield from self.transpile_override("constructor", constructor_impl())
        else:
            yield f"constructor ({', '.join(props)}) {{"
            self.indent()
            yield from constructor_impl()
            self.outdent()
            yield "}"

    def ci_compare(self) -> Generator[Optional[str], None, None]:
        """
        Transpile a case-insensitive string comparison function.
        """
        impl = (
            "return typeof a === 'string' && typeof b === 'string' ? "
            "a.localeCompare(b, undefined, { sensitivity: 'accent' }) "
            "=== 0 : a === b;"
        )
        if "ciCompare" in self.overrides_:
            yield from self.transpile_override("ciCompare", impl)
        else:
            yield "static ciCompare(a, b) {"
            self.indent()
            yield impl
            self.outdent()
            yield "}"

    def to_string(self, enum: Type[Enum]) -> Generator[Optional[str], None, None]:
        """
        Transpile the toString() method that converts enum instances to
        strings.

        :param enum: The enum class being transpiled
        :yield: transpiled javascript lines
        """
        impl = f"return this.{self.str_prop};"
        if "toString" in self.overrides_:
            yield from self.transpile_override("toString", impl)
        else:
            yield "toString() {"
            self.indent()
            yield impl
            self.outdent()
            yield "}"

    def getter(self) -> Generator[Optional[str], None, None]:
        """
        Transpile the get() method that converts values and properties into
        instances of the Enum type.

        :param enum: The enum class being transpiled
        :yield: transpiled javascript lines
        """
        yield "static get(value) {"
        self.indent()
        yield from self.getter_impl()
        self.outdent()
        yield "}"

    def getter_impl(self) -> Generator[Optional[str], None, None]:
        """
        Transpile the default implementation of get() that converts values and
        properties into instances of the Enum type.
        """
        yield "if (value instanceof this) {"
        self.indent()
        yield "return value;"
        self.outdent()
        yield "}"
        yield ""

        for prop in ["value"] + self.symmetric_properties:
            yield from self.prop_getter(prop)

        if self.on_unrecognized_ is UnrecognizedBehavior.RETURN_INPUT:
            yield "return value;"
        elif self.on_unrecognized_ is UnrecognizedBehavior.RETURN_NULL:
            yield "return null;"
        else:
            yield (
                f"throw new TypeError(`No {self.class_name} "
                f"enumeration maps to value ${{value}}`);"
            )

    def prop_getter(self, prop: str) -> Generator[Optional[str], None, None]:
        """
        Transpile the switch statement to map values of the given property to
        enumeration instance values.

        :param enum: The enum class being transpiled
        :param prop:
        :yield: transpiled javascript lines
        """
        yield "for (const en of this) {"
        self.indent()
        if prop in (self.isymmetric_properties_ or []):
            yield f"if (this.ciCompare(en.{prop}, value)) {{"
        else:
            yield f"if (en.{prop} === value) {{"
        self.indent()
        yield "return en;"
        self.outdent()
        yield "}"
        self.outdent()
        yield "}"

    def iterator(self, enum: Type[Enum]) -> Generator[Optional[str], None, None]:
        """
        Transpile the iterator for iterating through enum value instances.

        :param enum: The enum class being transpiled
        :yield: transpiled javascript lines
        """
        enums = [f"{self.class_name}.{enm.name}" for enm in enum]
        impl = f"return [{', '.join(enums)}][Symbol.iterator]();"
        if "[Symbol.iterator]" in self.overrides_:
            yield from self.transpile_override("[Symbol.iterator]", impl)
        else:
            yield "static [Symbol.iterator]() {"
            self.indent()
            yield impl
            self.outdent()
            yield "}"
