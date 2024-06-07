"""
Tests for base transpiler source tree traversal.
"""

from copy import copy
from enum import Enum, auto
from types import ModuleType

from django.test import TestCase

from render_static.transpilers.base import Transpiler
from render_static.transpilers.enums_to_js import IGNORED_ENUMS


class ParentTraversal:
    def __init__(self, target, is_last, is_final):
        self.target = target
        self.is_last = is_last
        self.is_final = is_final

    def __eq__(self, other):
        return other.__class__ is self.__class__ and (
            self.target == other.target
            and self.is_last == other.is_last
            and self.is_final == other.is_final
        )

    # def __str__(self):
    #     return f'{self.__class__.__name__}({self.target}, {self.is_last}, {self.is_final})'
    #
    # def __repr__(self):
    #     return str(self)


class EnterModule(ParentTraversal):
    pass


class ExitModule(ParentTraversal):
    pass


class EnterClass(ParentTraversal):
    pass


class ExitClass(ParentTraversal):
    pass


class Visit:
    def __init__(self, target, is_last, is_final, parents=None):
        self.parents = parents or []
        self.target = target
        self.is_last = is_last
        self.is_final = is_final

    def __eq__(self, other):
        return other.__class__ is self.__class__ and (
            self.parents == other.parents
            and self.target == other.target
            and self.is_last == other.is_last
            and self.is_final == other.is_final
        )

    # def __str__(self):
    #     return f'{self.__class__.__name__}({self.target}, {self.is_last}, {self.is_final}, {self.parents})'
    #
    # def __repr__(self):
    #     return str(self)


class TranspilerTester(Transpiler):
    TRAVERSAL = []
    include = None

    def __init__(self, include=include, **kwargs):
        self.TRAVERSAL = []
        self.include = include
        super().__init__(**kwargs)

    def include_target(self, target):
        if self.include:
            return self.include(target)
        if target in {*IGNORED_ENUMS, auto}:
            return False
        return super().include_target(target)

    def enter_module(self, module, is_last, is_final):
        self.TRAVERSAL.append(EnterModule(module, is_last, is_final))
        yield from super().enter_module(module, is_last, is_final)

    def exit_module(self, module, is_last, is_final):
        self.TRAVERSAL.append(ExitModule(module, is_last, is_final))
        yield from super().exit_module(module, is_last, is_final)

    def enter_class(self, cls, is_last, is_final):
        self.TRAVERSAL.append(EnterClass(cls, is_last, is_final))
        yield from super().enter_class(cls, is_last, is_final)

    def exit_class(self, cls, is_last, is_final):
        self.TRAVERSAL.append(ExitClass(cls, is_last, is_final))
        yield from super().exit_class(cls, is_last, is_final)

    def visit(self, target, is_last, is_final):
        self.TRAVERSAL.append(
            Visit(target, is_last, is_final, parents=(copy(self.parents)))
        )
        yield


class TranspileTraverseTests(TestCase):
    def test_class_traversal(self):
        from tests.traverse.module1 import Class1Module1

        transpiler = TranspilerTester()
        transpiler.transpile([Class1Module1])
        self.assertEqual(
            transpiler.TRAVERSAL,
            [
                EnterClass(Class1Module1, True, False),
                Visit(Class1Module1, True, False),
                EnterClass(Class1Module1.SubClass1, True, False),
                Visit(Class1Module1.SubClass1, True, False, parents=[Class1Module1]),
                EnterClass(Class1Module1.SubClass1.Enum1, False, False),
                Visit(
                    Class1Module1.SubClass1.Enum1,
                    False,
                    False,
                    parents=[Class1Module1, Class1Module1.SubClass1],
                ),
                ExitClass(Class1Module1.SubClass1.Enum1, False, False),
                EnterClass(Class1Module1.SubClass1.Enum2, True, True),
                Visit(
                    Class1Module1.SubClass1.Enum2,
                    True,
                    True,
                    parents=[Class1Module1, Class1Module1.SubClass1],
                ),
                ExitClass(Class1Module1.SubClass1.Enum2, True, True),
                ExitClass(Class1Module1.SubClass1, True, False),
                ExitClass(Class1Module1, True, False),
            ],
        )

    def test_class_import_string_traversal(self):
        from tests.traverse.module1 import Class1Module1

        transpiler = TranspilerTester()
        transpiler.transpile(["tests.traverse.module1.Class1Module1"])
        self.assertEqual(
            transpiler.TRAVERSAL,
            [
                EnterClass(Class1Module1, True, False),
                Visit(Class1Module1, True, False),
                EnterClass(Class1Module1.SubClass1, True, False),
                Visit(Class1Module1.SubClass1, True, False, parents=[Class1Module1]),
                EnterClass(Class1Module1.SubClass1.Enum1, False, False),
                Visit(
                    Class1Module1.SubClass1.Enum1,
                    False,
                    False,
                    parents=[Class1Module1, Class1Module1.SubClass1],
                ),
                ExitClass(Class1Module1.SubClass1.Enum1, False, False),
                EnterClass(Class1Module1.SubClass1.Enum2, True, True),
                Visit(
                    Class1Module1.SubClass1.Enum2,
                    True,
                    True,
                    parents=[Class1Module1, Class1Module1.SubClass1],
                ),
                ExitClass(Class1Module1.SubClass1.Enum2, True, True),
                ExitClass(Class1Module1.SubClass1, True, False),
                ExitClass(Class1Module1, True, False),
            ],
        )

    def test_deduplicate_class(self):
        from tests.traverse.module1 import Class1Module1

        transpiler = TranspilerTester()
        transpiler.transpile([Class1Module1, "tests.traverse.module1.Class1Module1"])
        self.assertEqual(
            transpiler.TRAVERSAL,
            [
                EnterClass(Class1Module1, True, False),
                Visit(Class1Module1, True, False),
                EnterClass(Class1Module1.SubClass1, True, False),
                Visit(Class1Module1.SubClass1, True, False, parents=[Class1Module1]),
                EnterClass(Class1Module1.SubClass1.Enum1, False, False),
                Visit(
                    Class1Module1.SubClass1.Enum1,
                    False,
                    False,
                    parents=[Class1Module1, Class1Module1.SubClass1],
                ),
                ExitClass(Class1Module1.SubClass1.Enum1, False, False),
                EnterClass(Class1Module1.SubClass1.Enum2, True, True),
                Visit(
                    Class1Module1.SubClass1.Enum2,
                    True,
                    True,
                    parents=[Class1Module1, Class1Module1.SubClass1],
                ),
                ExitClass(Class1Module1.SubClass1.Enum2, True, True),
                ExitClass(Class1Module1.SubClass1, True, False),
                ExitClass(Class1Module1, True, False),
            ],
        )

    def test_module_traversal(self):
        from tests.traverse import module1
        from tests.traverse.module1 import Class1Module1, Class2Module1

        transpiler = TranspilerTester()
        transpiler.transpile([module1])
        self.assertEqual(
            transpiler.TRAVERSAL,
            [
                EnterModule(module1, True, False),
                Visit(module1, True, False),
                EnterClass(Class1Module1, False, False),
                Visit(Class1Module1, False, False, parents=[module1]),
                EnterClass(Class1Module1.SubClass1, True, False),
                Visit(
                    Class1Module1.SubClass1,
                    True,
                    False,
                    parents=[module1, Class1Module1],
                ),
                EnterClass(Class1Module1.SubClass1.Enum1, False, False),
                Visit(
                    Class1Module1.SubClass1.Enum1,
                    False,
                    False,
                    parents=[module1, Class1Module1, Class1Module1.SubClass1],
                ),
                ExitClass(Class1Module1.SubClass1.Enum1, False, False),
                EnterClass(Class1Module1.SubClass1.Enum2, True, False),
                Visit(
                    Class1Module1.SubClass1.Enum2,
                    True,
                    False,
                    parents=[module1, Class1Module1, Class1Module1.SubClass1],
                ),
                ExitClass(Class1Module1.SubClass1.Enum2, True, False),
                ExitClass(Class1Module1.SubClass1, True, False),
                ExitClass(Class1Module1, False, False),
                EnterClass(Class2Module1, True, False),
                Visit(Class2Module1, True, False, parents=[module1]),
                EnterClass(Class2Module1.EnumStr, False, False),
                Visit(
                    Class2Module1.EnumStr,
                    False,
                    False,
                    parents=[module1, Class2Module1],
                ),
                ExitClass(Class2Module1.EnumStr, False, False),
                EnterClass(Class2Module1.NotAnEnum, True, True),
                Visit(
                    Class2Module1.NotAnEnum,
                    True,
                    True,
                    parents=[module1, Class2Module1],
                ),
                ExitClass(Class2Module1.NotAnEnum, True, True),
                ExitClass(Class2Module1, True, False),
                ExitModule(module1, True, False),
            ],
        )

    def test_module_import_string_traversal(self):
        from tests.traverse import module1
        from tests.traverse.module1 import Class1Module1, Class2Module1

        transpiler = TranspilerTester()
        transpiler.transpile(["tests.traverse.module1"])
        self.assertEqual(
            transpiler.TRAVERSAL,
            [
                EnterModule(module1, True, False),
                Visit(module1, True, False),
                EnterClass(Class1Module1, False, False),
                Visit(Class1Module1, False, False, parents=[module1]),
                EnterClass(Class1Module1.SubClass1, True, False),
                Visit(
                    Class1Module1.SubClass1,
                    True,
                    False,
                    parents=[module1, Class1Module1],
                ),
                EnterClass(Class1Module1.SubClass1.Enum1, False, False),
                Visit(
                    Class1Module1.SubClass1.Enum1,
                    False,
                    False,
                    parents=[module1, Class1Module1, Class1Module1.SubClass1],
                ),
                ExitClass(Class1Module1.SubClass1.Enum1, False, False),
                EnterClass(Class1Module1.SubClass1.Enum2, True, False),
                Visit(
                    Class1Module1.SubClass1.Enum2,
                    True,
                    False,
                    parents=[module1, Class1Module1, Class1Module1.SubClass1],
                ),
                ExitClass(Class1Module1.SubClass1.Enum2, True, False),
                ExitClass(Class1Module1.SubClass1, True, False),
                ExitClass(Class1Module1, False, False),
                EnterClass(Class2Module1, True, False),
                Visit(Class2Module1, True, False, parents=[module1]),
                EnterClass(Class2Module1.EnumStr, False, False),
                Visit(
                    Class2Module1.EnumStr,
                    False,
                    False,
                    parents=[module1, Class2Module1],
                ),
                ExitClass(Class2Module1.EnumStr, False, False),
                EnterClass(Class2Module1.NotAnEnum, True, True),
                Visit(
                    Class2Module1.NotAnEnum,
                    True,
                    True,
                    parents=[module1, Class2Module1],
                ),
                ExitClass(Class2Module1.NotAnEnum, True, True),
                ExitClass(Class2Module1, True, False),
                ExitModule(module1, True, False),
            ],
        )

    def test_deduplicate_module(self):
        from tests.traverse import module1
        from tests.traverse.module1 import Class1Module1, Class2Module1

        transpiler = TranspilerTester()
        transpiler.transpile(["tests.traverse.module1", module1])
        self.assertEqual(
            transpiler.TRAVERSAL,
            [
                EnterModule(module1, True, False),
                Visit(module1, True, False),
                EnterClass(Class1Module1, False, False),
                Visit(Class1Module1, False, False, parents=[module1]),
                EnterClass(Class1Module1.SubClass1, True, False),
                Visit(
                    Class1Module1.SubClass1,
                    True,
                    False,
                    parents=[module1, Class1Module1],
                ),
                EnterClass(Class1Module1.SubClass1.Enum1, False, False),
                Visit(
                    Class1Module1.SubClass1.Enum1,
                    False,
                    False,
                    parents=[module1, Class1Module1, Class1Module1.SubClass1],
                ),
                ExitClass(Class1Module1.SubClass1.Enum1, False, False),
                EnterClass(Class1Module1.SubClass1.Enum2, True, False),
                Visit(
                    Class1Module1.SubClass1.Enum2,
                    True,
                    False,
                    parents=[module1, Class1Module1, Class1Module1.SubClass1],
                ),
                ExitClass(Class1Module1.SubClass1.Enum2, True, False),
                ExitClass(Class1Module1.SubClass1, True, False),
                ExitClass(Class1Module1, False, False),
                EnterClass(Class2Module1, True, False),
                Visit(Class2Module1, True, False, parents=[module1]),
                EnterClass(Class2Module1.EnumStr, False, False),
                Visit(
                    Class2Module1.EnumStr,
                    False,
                    False,
                    parents=[module1, Class2Module1],
                ),
                ExitClass(Class2Module1.EnumStr, False, False),
                EnterClass(Class2Module1.NotAnEnum, True, True),
                Visit(
                    Class2Module1.NotAnEnum,
                    True,
                    True,
                    parents=[module1, Class2Module1],
                ),
                ExitClass(Class2Module1.NotAnEnum, True, True),
                ExitClass(Class2Module1, True, False),
                ExitModule(module1, True, False),
            ],
        )

    def test_multi_module_traversal(self):
        from tests.traverse import module1
        from tests.traverse.module1 import Class1Module1, Class2Module1
        from tests.traverse.sub_pkg import module2
        from tests.traverse.sub_pkg.module2 import (
            Class1Module2,
            Class2Module2,
        )

        transpiler = TranspilerTester()
        transpiler.transpile(["tests.traverse.module1", module2])
        expected = [
            EnterModule(module1, False, False),
            Visit(module1, False, False),
            EnterClass(Class1Module1, False, False),
            Visit(Class1Module1, False, False, parents=[module1]),
            EnterClass(Class1Module1.SubClass1, True, False),
            Visit(
                Class1Module1.SubClass1, True, False, parents=[module1, Class1Module1]
            ),
            EnterClass(Class1Module1.SubClass1.Enum1, False, False),
            Visit(
                Class1Module1.SubClass1.Enum1,
                False,
                False,
                parents=[module1, Class1Module1, Class1Module1.SubClass1],
            ),
            ExitClass(Class1Module1.SubClass1.Enum1, False, False),
            EnterClass(Class1Module1.SubClass1.Enum2, True, False),
            Visit(
                Class1Module1.SubClass1.Enum2,
                True,
                False,
                parents=[module1, Class1Module1, Class1Module1.SubClass1],
            ),
            ExitClass(Class1Module1.SubClass1.Enum2, True, False),
            ExitClass(Class1Module1.SubClass1, True, False),
            ExitClass(Class1Module1, False, False),
            EnterClass(Class2Module1, True, False),
            Visit(Class2Module1, True, False, parents=[module1]),
            EnterClass(Class2Module1.EnumStr, False, False),
            Visit(
                Class2Module1.EnumStr, False, False, parents=[module1, Class2Module1]
            ),
            ExitClass(Class2Module1.EnumStr, False, False),
            EnterClass(Class2Module1.NotAnEnum, True, False),
            Visit(
                Class2Module1.NotAnEnum, True, False, parents=[module1, Class2Module1]
            ),
            ExitClass(Class2Module1.NotAnEnum, True, False),
            ExitClass(Class2Module1, True, False),
            ExitModule(module1, False, False),
            EnterModule(module2, True, False),
            Visit(module2, True, False),
            EnterClass(Class1Module2, False, False),
            Visit(Class1Module2, False, False, parents=[module2]),
            EnterClass(Class1Module2.SubClass1, True, False),
            Visit(
                Class1Module2.SubClass1, True, False, parents=[module2, Class1Module2]
            ),
            EnterClass(Class1Module2.SubClass1.Enum1, False, False),
            Visit(
                Class1Module2.SubClass1.Enum1,
                False,
                False,
                parents=[module2, Class1Module2, Class1Module2.SubClass1],
            ),
            ExitClass(Class1Module2.SubClass1.Enum1, False, False),
            EnterClass(Class1Module2.SubClass1.Enum2, True, False),
            Visit(
                Class1Module2.SubClass1.Enum2,
                True,
                False,
                parents=[module2, Class1Module2, Class1Module2.SubClass1],
            ),
            ExitClass(Class1Module2.SubClass1.Enum2, True, False),
            ExitClass(Class1Module2.SubClass1, True, False),
            ExitClass(Class1Module2, False, False),
            EnterClass(Class2Module2, True, False),
            Visit(Class2Module2, True, False, parents=[module2]),
            EnterClass(Class2Module2.EnumStr, True, True),
            Visit(Class2Module2.EnumStr, True, True, parents=[module2, Class2Module2]),
            ExitClass(Class2Module2.EnumStr, True, True),
            ExitClass(Class2Module2, True, False),
            ExitModule(module2, True, False),
        ]
        self.assertEqual(transpiler.TRAVERSAL, expected)

    def test_multi_class_traversal(self):
        from tests.traverse.module1 import Class1Module1, Class2Module1

        transpiler = TranspilerTester()
        transpiler.transpile([Class1Module1, Class2Module1])
        expected = [
            EnterClass(Class1Module1, False, False),
            Visit(Class1Module1, False, False),
            EnterClass(Class1Module1.SubClass1, True, False),
            Visit(Class1Module1.SubClass1, True, False, parents=[Class1Module1]),
            EnterClass(Class1Module1.SubClass1.Enum1, False, False),
            Visit(
                Class1Module1.SubClass1.Enum1,
                False,
                False,
                parents=[Class1Module1, Class1Module1.SubClass1],
            ),
            ExitClass(Class1Module1.SubClass1.Enum1, False, False),
            EnterClass(Class1Module1.SubClass1.Enum2, True, False),
            Visit(
                Class1Module1.SubClass1.Enum2,
                True,
                False,
                parents=[Class1Module1, Class1Module1.SubClass1],
            ),
            ExitClass(Class1Module1.SubClass1.Enum2, True, False),
            ExitClass(Class1Module1.SubClass1, True, False),
            ExitClass(Class1Module1, False, False),
            EnterClass(Class2Module1, True, False),
            Visit(Class2Module1, True, False),
            EnterClass(Class2Module1.EnumStr, False, False),
            Visit(Class2Module1.EnumStr, False, False, parents=[Class2Module1]),
            ExitClass(Class2Module1.EnumStr, False, False),
            EnterClass(Class2Module1.NotAnEnum, True, True),
            Visit(Class2Module1.NotAnEnum, True, True, parents=[Class2Module1]),
            ExitClass(Class2Module1.NotAnEnum, True, True),
            ExitClass(Class2Module1, True, False),
        ]
        self.assertEqual(transpiler.TRAVERSAL, expected)

    def test_select_enums(self):
        class EnumTranspiler(TranspilerTester):
            def include_target(self, target):
                ret = (
                    super().include_target(target)
                    and isinstance(target, type)
                    and issubclass(target, Enum)
                )
                print(f"{target}: {ret}")
                return ret

        from tests.traverse import module1
        from tests.traverse.module1 import Class1Module1, Class2Module1
        from tests.traverse.sub_pkg.module2 import Class2Module2

        transpiler = EnumTranspiler()
        transpiler.transpile(["tests.traverse.module1", Class2Module2])
        expected = [
            EnterModule(module1, False, False),
            EnterClass(Class1Module1, False, False),
            EnterClass(Class1Module1.SubClass1, True, False),
            EnterClass(Class1Module1.SubClass1.Enum1, False, False),
            Visit(
                Class1Module1.SubClass1.Enum1,
                False,
                False,
                parents=[module1, Class1Module1, Class1Module1.SubClass1],
            ),
            ExitClass(Class1Module1.SubClass1.Enum1, False, False),
            EnterClass(Class1Module1.SubClass1.Enum2, True, False),
            Visit(
                Class1Module1.SubClass1.Enum2,
                True,
                False,
                parents=[module1, Class1Module1, Class1Module1.SubClass1],
            ),
            ExitClass(Class1Module1.SubClass1.Enum2, True, False),
            ExitClass(Class1Module1.SubClass1, True, False),
            ExitClass(Class1Module1, False, False),
            EnterClass(Class2Module1, True, False),
            EnterClass(Class2Module1.EnumStr, True, False),
            Visit(Class2Module1.EnumStr, True, False, parents=[module1, Class2Module1]),
            ExitClass(Class2Module1.EnumStr, True, False),
            ExitClass(Class2Module1, True, False),
            ExitModule(module1, False, False),
            EnterClass(Class2Module2, True, False),
            EnterClass(Class2Module2.EnumStr, True, True),
            Visit(Class2Module2.EnumStr, True, True, parents=[Class2Module2]),
            ExitClass(Class2Module2.EnumStr, True, True),
            ExitClass(Class2Module2, True, False),
        ]
        self.assertEqual(transpiler.TRAVERSAL, expected)

    def test_app_transpile_string(self):
        from django.apps import apps

        transpiler = TranspilerTester()
        transpiler.transpile(["tests.enum_app"])
        self.assertEqual(
            transpiler.TRAVERSAL,
            [Visit(apps.get_app_config("tests_enum_app"), True, True)],
        )

    def test_app_transpile_app_config(self):
        from django.apps import apps

        transpiler = TranspilerTester()
        transpiler.transpile([apps.get_app_config("tests_enum_app")])
        self.assertEqual(
            transpiler.TRAVERSAL,
            [Visit(apps.get_app_config("tests_enum_app"), True, True)],
        )

    def test_app_transpile_app_label(self):
        from django.apps import apps

        transpiler = TranspilerTester()
        transpiler.transpile(["tests_enum_app"])
        self.assertEqual(
            transpiler.TRAVERSAL,
            [Visit(apps.get_app_config("tests_enum_app"), True, True)],
        )

    def test_deduplicate_appconfigs(self):
        from django.apps import apps

        transpiler = TranspilerTester()
        transpiler.transpile(
            [
                "tests.enum_app",
                apps.get_app_config("tests_enum_app"),
                "tests_enum_app",
            ]
        )
        self.assertEqual(
            transpiler.TRAVERSAL,
            [Visit(apps.get_app_config("tests_enum_app"), True, True)],
        )

    def test_transpiled_parent_and_children(self):
        def include_defines(target):
            if isinstance(target, (type, ModuleType)):
                for name in dir(target):
                    if name.isupper():
                        return True
            return False

        transpiler = TranspilerTester(include=include_defines)
        from tests.traverse import models

        transpiler.transpile(["tests.traverse.models", None])
        self.assertEqual(
            transpiler.TRAVERSAL,
            [
                EnterModule(models, True, False),
                EnterClass(models.ExampleModel, True, False),
                Visit(models.ExampleModel, True, False, parents=[models]),
                EnterClass(models.ExampleModel.Color, False, False),
                Visit(
                    models.ExampleModel.Color,
                    False,
                    False,
                    parents=[models, models.ExampleModel],
                ),
                ExitClass(models.ExampleModel.Color, False, False),
                EnterClass(models.ExampleModel.MapBoxStyle, True, True),
                Visit(
                    models.ExampleModel.MapBoxStyle,
                    True,
                    True,
                    parents=[models, models.ExampleModel],
                ),
                ExitClass(models.ExampleModel.MapBoxStyle, True, True),
                ExitClass(models.ExampleModel, True, False),
                ExitModule(models, True, False),
            ],
        )
