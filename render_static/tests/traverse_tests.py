"""
Tests for base transpiler source tree traversal.
"""
from django.test import TestCase
from render_static.transpilers import Transpiler
from render_static.transpilers.enums_to_js import IGNORED_ENUMS
from enum import auto, Enum
from copy import copy


class TestTranspiler(Transpiler):

    VISITS = []
    include = None

    def __init__(self, include=include, **kwargs):
        self.VISITS = []
        self.include = include
        super().__init__(**kwargs)

    def include_target(self, target):
        if self.include:
            return self.include(target)
        if target in {*IGNORED_ENUMS, auto}:
            return False
        return super().include_target(target)

    def visit(
        self,
        target,
        is_last,
        final
    ):
        self.VISITS.append((copy(self.parents), target, is_last, final))
        yield


class TranspileTraverseTests(TestCase):

    def test_class_traversal(self):
        from render_static.tests.traverse.module1 import Class1Module1
        transpiler = TestTranspiler()
        transpiler.transpile([Class1Module1])
        self.assertEqual(
            transpiler.VISITS,
            [
                ([], Class1Module1, True, False),
                ([Class1Module1], Class1Module1.SubClass1, True, False),
                ([
                     Class1Module1,
                     Class1Module1.SubClass1
                 ], Class1Module1.SubClass1.Enum1, False, False),
                ([
                     Class1Module1,
                     Class1Module1.SubClass1
                 ], Class1Module1.SubClass1.Enum2, True, True)
            ]
        )

    def test_class_import_string_traversal(self):
        from render_static.tests.traverse.module1 import Class1Module1
        transpiler = TestTranspiler()
        transpiler.transpile(['render_static.tests.traverse.module1.Class1Module1'])
        self.assertEqual(
            transpiler.VISITS,
            [
                ([], Class1Module1, True, False),
                ([Class1Module1], Class1Module1.SubClass1, True, False),
                ([
                     Class1Module1,
                     Class1Module1.SubClass1
                 ], Class1Module1.SubClass1.Enum1, False, False),
                ([
                     Class1Module1,
                     Class1Module1.SubClass1
                 ], Class1Module1.SubClass1.Enum2, True, True)
            ]
        )

    def test_deduplicate_class(self):
        from render_static.tests.traverse.module1 import Class1Module1
        transpiler = TestTranspiler()
        transpiler.transpile([
            Class1Module1,
            'render_static.tests.traverse.module1.Class1Module1'
        ])
        self.assertEqual(
            transpiler.VISITS,
            [
                ([], Class1Module1, True, False),
                ([Class1Module1], Class1Module1.SubClass1, True, False),
                ([
                     Class1Module1,
                     Class1Module1.SubClass1
                 ], Class1Module1.SubClass1.Enum1, False, False),
                ([
                     Class1Module1,
                     Class1Module1.SubClass1
                 ], Class1Module1.SubClass1.Enum2, True, True)
            ]
        )

    def test_module_traversal(self):
        from render_static.tests.traverse import module1
        from render_static.tests.traverse.module1 import (
            Class1Module1,
            Class2Module1
        )
        transpiler = TestTranspiler()
        transpiler.transpile([module1])
        self.assertEqual(
            transpiler.VISITS,
            [
                ([], module1, True, False),
                ([module1], Class1Module1, False, False),
                ([module1, Class1Module1], Class1Module1.SubClass1, True, False),
                ([
                     module1,
                     Class1Module1,
                     Class1Module1.SubClass1
                 ], Class1Module1.SubClass1.Enum1, False, False),
                ([
                     module1,
                     Class1Module1,
                     Class1Module1.SubClass1
                 ], Class1Module1.SubClass1.Enum2, True, False),
                ([module1], Class2Module1, True, False),
                ([module1, Class2Module1], Class2Module1.EnumStr, False, False),
                ([module1, Class2Module1], Class2Module1.NotAnEnum, True, True)
            ]
        )

    def test_module_import_string_traversal(self):
        from render_static.tests.traverse import module1
        from render_static.tests.traverse.module1 import (
            Class1Module1,
            Class2Module1
        )
        transpiler = TestTranspiler()
        transpiler.transpile(['render_static.tests.traverse.module1'])
        self.assertEqual(
            transpiler.VISITS,
            [
                ([], module1, True, False),
                ([module1], Class1Module1, False, False),
                ([module1, Class1Module1], Class1Module1.SubClass1, True, False),
                ([
                     module1,
                     Class1Module1,
                     Class1Module1.SubClass1
                 ], Class1Module1.SubClass1.Enum1, False, False),
                ([
                     module1,
                     Class1Module1,
                     Class1Module1.SubClass1
                 ], Class1Module1.SubClass1.Enum2, True, False),
                ([module1], Class2Module1, True, False),
                ([module1, Class2Module1], Class2Module1.EnumStr, False, False),
                ([module1, Class2Module1], Class2Module1.NotAnEnum, True, True)
            ]
        )

    def test_deduplicate_module(self):
        from render_static.tests.traverse import module1
        from render_static.tests.traverse.module1 import (
            Class1Module1,
            Class2Module1
        )
        transpiler = TestTranspiler()
        transpiler.transpile([
            'render_static.tests.traverse.module1',
            module1
        ])
        self.assertEqual(
            transpiler.VISITS,
            [
                ([], module1, True, False),
                ([module1], Class1Module1, False, False),
                ([module1, Class1Module1], Class1Module1.SubClass1, True, False),
                ([
                     module1,
                     Class1Module1,
                     Class1Module1.SubClass1
                 ], Class1Module1.SubClass1.Enum1, False, False),
                ([
                     module1,
                     Class1Module1,
                     Class1Module1.SubClass1
                 ], Class1Module1.SubClass1.Enum2, True, False),
                ([module1], Class2Module1, True, False),
                ([module1, Class2Module1], Class2Module1.EnumStr, False, False),
                ([module1, Class2Module1], Class2Module1.NotAnEnum, True, True)
            ]
        )

    def test_multi_module_traversal(self):
        from render_static.tests.traverse import module1
        from render_static.tests.traverse.sub_pkg import module2
        from render_static.tests.traverse.module1 import (
            Class1Module1,
            Class2Module1
        )
        from render_static.tests.traverse.sub_pkg.module2 import (
            Class1Module2,
            Class2Module2
        )
        transpiler = TestTranspiler()
        transpiler.transpile(['render_static.tests.traverse.module1', module2])

        self.assertEqual(
            transpiler.VISITS,
            [
                ([], module1, False, False),
                ([module1], Class1Module1, False, False),
                ([module1, Class1Module1], Class1Module1.SubClass1, True, False),
                ([
                     module1,
                     Class1Module1,
                     Class1Module1.SubClass1
                 ], Class1Module1.SubClass1.Enum1, False, False),
                ([
                     module1,
                     Class1Module1,
                     Class1Module1.SubClass1
                 ], Class1Module1.SubClass1.Enum2, True, False),
                ([module1], Class2Module1, True, False),
                ([module1, Class2Module1], Class2Module1.EnumStr, False, False),
                ([module1, Class2Module1], Class2Module1.NotAnEnum, True, False),

                ([], module2, True, False),
                ([module2], Class1Module2, False, False),
                ([module2, Class1Module2], Class1Module2.SubClass1, True, False),
                ([
                     module2,
                     Class1Module2,
                     Class1Module2.SubClass1
                 ], Class1Module2.SubClass1.Enum1, False, False),
                ([
                     module2,
                     Class1Module2,
                     Class1Module2.SubClass1
                 ], Class1Module2.SubClass1.Enum2, True, False),
                ([module2], Class2Module2, True, False),
                ([module2, Class2Module2], Class2Module2.EnumStr, True, True)
            ]
        )

    def test_multi_class_traversal(self):
        from render_static.tests.traverse.module1 import (
            Class1Module1,
            Class2Module1
        )
        transpiler = TestTranspiler()
        transpiler.transpile([Class1Module1, Class2Module1])
        self.assertEqual(
            transpiler.VISITS,
            [
                ([], Class1Module1, False, False),
                ([Class1Module1], Class1Module1.SubClass1, True, False),
                ([
                     Class1Module1,
                     Class1Module1.SubClass1
                 ], Class1Module1.SubClass1.Enum1, False, False),
                ([
                     Class1Module1,
                     Class1Module1.SubClass1
                 ], Class1Module1.SubClass1.Enum2, True, False),
                ([], Class2Module1, True, False),
                ([Class2Module1], Class2Module1.EnumStr, False, False),
                ([Class2Module1], Class2Module1.NotAnEnum, True, True)
            ]
        )

    def test_select_enums(self):
        class EnumTranspiler(TestTranspiler):

            def include_target(self, target):

                ret = (
                    super().include_target(target) and
                    isinstance(target, type) and
                    issubclass(target, Enum)
                )
                print(f'{target}: {ret}')
                return ret

        from render_static.tests.traverse import module1
        from render_static.tests.traverse.sub_pkg.module2 import Class2Module2
        from render_static.tests.traverse.module1 import (
            Class1Module1,
            Class2Module1
        )
        transpiler = EnumTranspiler()
        transpiler.transpile([
            'render_static.tests.traverse.module1',
            Class2Module2
        ])
        self.assertEqual(
            transpiler.VISITS,
            [
                ([
                    module1,
                    Class1Module1,
                    Class1Module1.SubClass1
                 ], Class1Module1.SubClass1.Enum1, False, False),
                ([
                    module1,
                    Class1Module1,
                    Class1Module1.SubClass1
                 ], Class1Module1.SubClass1.Enum2, True, False),
                ([module1, Class2Module1], Class2Module1.EnumStr, True, False),
                ([Class2Module2], Class2Module2.EnumStr, True, True)
            ]
        )

    def test_app_transpile_string(self):
        from django.apps import apps
        transpiler = TestTranspiler()
        transpiler.transpile([
            'render_static.tests.enum_app'
        ])
        self.assertEqual(
            transpiler.VISITS,
            [
                (
                    [],
                    apps.get_app_config('render_static_tests_enum_app'),
                    True,
                    True
                )
            ]
        )

    def test_app_transpile_app_config(self):
        from django.apps import apps
        transpiler = TestTranspiler()
        transpiler.transpile([
            apps.get_app_config('render_static_tests_enum_app')
        ])
        self.assertEqual(
            transpiler.VISITS,
            [
                (
                    [],
                    apps.get_app_config('render_static_tests_enum_app'),
                    True,
                    True
                )
            ]
        )

    def test_app_transpile_app_label(self):
        from django.apps import apps
        transpiler = TestTranspiler()
        transpiler.transpile([
            'render_static_tests_enum_app'
        ])
        self.assertEqual(
            transpiler.VISITS,
            [
                (
                    [],
                    apps.get_app_config('render_static_tests_enum_app'),
                    True,
                    True
                )
            ]
        )

    def test_deduplicate_appconfigs(self):
        from django.apps import apps
        transpiler = TestTranspiler()
        transpiler.transpile([
            'render_static.tests.enum_app',
            apps.get_app_config('render_static_tests_enum_app'),
            'render_static_tests_enum_app'
        ])
        self.assertEqual(
            transpiler.VISITS,
            [
                (
                    [],
                    apps.get_app_config('render_static_tests_enum_app'),
                    True,
                    True
                )
            ]
        )
