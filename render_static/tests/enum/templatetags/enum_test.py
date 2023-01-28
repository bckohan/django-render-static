# pylint: disable=C0114

from django import template
from django.utils.module_loading import import_string
from render_static.transpilers import (
    to_js as to_js_transpiler,
    JavaScriptGenerator
)
from enum import Enum
from django.utils.safestring import SafeString
try:
    from django.utils.decorators import classproperty
except ImportError:
    from django.utils.functional import classproperty

register = template.Library()


class EnumTests(JavaScriptGenerator):

    name_map = {}
    class_properties_ = []
    properties_ = []
    symmetric_properties_ = []

    def __init__(
            self,
            *args,
            name_map,
            class_properties=True,
            properties=True,
            symmetric_properties=None,
            **kwargs
    ):
        self.name_map = name_map
        self.class_properties_ = class_properties
        self.properties_ = properties
        if symmetric_properties:
            self.symmetric_properties_ = symmetric_properties or []
        super().__init__(*args, **kwargs)

    def generate(self, enums):
        for line in self.transpile_enums(enums):
            self.write_line(line)
        return self.rendered_

    def transpile_enums(self, enums):
        yield 'var enums = {};'
        for enum in enums:
            yield from self.transpile_test(enum)
        yield 'console.log(JSON.stringify(enums));'

    def transpile_test(self, enum):

        class_properties = [
            name for name, member in vars(enum).items()
            if isinstance(member, classproperty)
        ] if self.class_properties_ is True else (
            [prop for prop in self.class_properties_ if hasattr(enum, prop)]
            if self.class_properties_ else []
        )

        properties = ['name', 'value'] + [
            name for name, member in vars(enum).items()
            if isinstance(member, property)
        ] if self.properties_ is True else (
            [prop for prop in self.properties_ if hasattr(enum, prop)]
            if self.properties_ else ['value', 'name']
        )

        yield f'enums.{enum.__name__} = {{'
        self.indent()
        yield 'strings: {},'
        for prop in properties:
            yield f'{prop}: [],'
        yield 'getCheck: false'
        self.outdent()
        yield '};'
        yield f'for (const en of {self.name_map[enum]}) {{'
        self.indent()
        for prop in properties:
            yield f'enums.{enum.__name__}.{prop}.push(en.{prop});'
        yield f'enums.{enum.__name__}.strings[en.value] = en.toString();'

        if class_properties:
            yield f'enums.{enum.__name__}.class_props = {{'
            self.indent()
            for prop in class_properties:
                yield f'{prop}: {self.name_map[enum]}.{prop},'
            self.outdent()
            yield '}'

        self.outdent()
        yield '}'

        for idx1, prop in enumerate(['value'] + self.symmetric_properties_):
            for idx2, en in enumerate(enum):
                yield (
                    f'enums.{enum.__name__}.getCheck {"=" if idx1 == 0 and idx2 == 0else "&="} '
                    f'{self.name_map[enum]}.{en.name} === {self.name_map[enum]}.'
                    f'get({self.to_js(getattr(en, prop))});'
                )


@register.filter(name='enum_list')
def enum_list(enums):
    if isinstance(enums, str) or isinstance(enums, type):
        enums = [enums]
    ret = [
        import_string(en)
        if not isinstance(en, Enum) and isinstance(en, str)
        else en for en in enums
    ]
    return ret


@register.filter(name='to_js')
def to_js(value):
    return to_js_transpiler(value)


@register.simple_tag
def enum_tests(
        enums,
        name_map=None,
        class_properties=True,
        properties=True,
        symmetric_properties=False
):
    if name_map is None:
        name_map = {en: en.__name__ for en in enums}
    return SafeString(
        EnumTests(
            name_map=name_map,
            class_properties=class_properties,
            properties=properties,
            symmetric_properties=symmetric_properties
        ).generate(enums)
    )
