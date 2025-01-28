# pylint: disable=C0114

from enum import Enum

from django import template
from django.utils.module_loading import import_string
from django.utils.safestring import SafeString

from render_static.transpilers.enums_to_js import EnumTranspiler

try:
    from django.utils.decorators import classproperty
except ImportError:
    from django.utils.functional import classproperty

register = template.Library()


class EnumTests(EnumTranspiler):
    name_map = {}
    class_properties_ = []
    properties_ = []
    symmetric_properties_ = []
    class_name_map_ = {}

    def to_js(self, value):
        if isinstance(value, Enum):
            if value.__class__ in self.class_name_map_:
                return f"{self.class_name_map_[value.__class__]}.{value.name}"
        return self.to_javascript(value)

    def __init__(
        self,
        *args,
        name_map,
        class_properties=True,
        properties=True,
        symmetric_properties=None,
        class_name_map=None,
        to_string=True,
        **kwargs,
    ):
        self.name_map = name_map
        self.class_properties_ = class_properties
        self.properties_ = properties
        if symmetric_properties:
            self.symmetric_properties_ = symmetric_properties or []
        self.class_name_map_ = class_name_map or self.class_name_map_
        self.to_string_ = to_string
        super().__init__(*args, **kwargs)

    def start_visitation(self):
        yield "var enums = {};"

    def end_visitation(self):
        yield "console.log(JSON.stringify(enums));"

    def visit(self, enum, is_bool, final):
        class_properties = (
            [
                name
                for name, member in vars(enum).items()
                if isinstance(member, classproperty)
            ]
            if self.class_properties_ is True
            else (
                [prop for prop in self.class_properties_ if hasattr(enum, prop)]
                if self.class_properties_
                else []
            )
        )

        properties = (
            [
                name
                for name, member in vars(enum).items()
                if isinstance(member, property)
            ]
            if self.properties_ is True
            else (
                [prop for prop in self.properties_ if hasattr(enum, prop)]
                if self.properties_
                else []
            )
        )
        for param in ["value"]:  # pragma: no cover
            if param not in properties:
                properties.insert(0, param)

        yield f"enums.{enum.__name__} = {{"
        self.indent()
        if self.to_string_:
            yield "strings: {},"
        for prop in properties:
            yield f"{prop}: [],"
        yield "getCheck: false"
        self.outdent()
        yield "};"
        yield f"for (const en of {self.name_map[enum]}) {{"
        self.indent()
        for prop in properties:
            yield f"enums.{enum.__name__}.{prop}.push(en.{prop});"

        if self.to_string_:
            yield f"enums.{enum.__name__}.strings[en.value] = en.toString();"

        if class_properties:
            yield f"enums.{enum.__name__}.class_props = {{"
            self.indent()
            for prop in class_properties:
                yield f"{prop}: {self.name_map[enum]}.{prop},"
            self.outdent()
            yield "}"

        self.outdent()
        yield "}"

        for idx1, prop in enumerate(["value"] + self.symmetric_properties_):
            for idx2, en in enumerate(enum):
                yield (
                    f"enums.{enum.__name__}.getCheck {'=' if (idx1 == 0 and idx2 == 0) else '&='} "
                    f"{self.name_map[enum]}.{en.name} === {self.name_map[enum]}."
                    f"get({self.to_js(getattr(en, prop))});"
                )


@register.filter(name="enum_list")
def enum_list(enums):
    if isinstance(enums, str) or isinstance(enums, type):
        enums = [enums]
    ret = [
        import_string(en) if not isinstance(en, Enum) and isinstance(en, str) else en
        for en in enums
    ]
    return ret


@register.simple_tag
def enum_tests(
    enums,
    name_map=None,
    class_properties=True,
    properties=True,
    symmetric_properties=False,
    class_name_map=None,
    to_string=True,
):
    if name_map is None:
        name_map = {en: en.__name__ for en in enums}
    return SafeString(
        EnumTests(
            name_map=name_map,
            class_properties=class_properties,
            properties=properties,
            symmetric_properties=symmetric_properties,
            class_name_map=class_name_map,
            to_string=to_string,
        ).transpile(enums)
    )


@register.filter(name="default_bool")
def default_bool(value, default):
    if value in [None, ""]:
        return default
    return value
