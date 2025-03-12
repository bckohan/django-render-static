import inspect
import json
import os
import re
import shutil
import subprocess
import traceback
import uuid
from datetime import date
from enum import Enum
from os import makedirs
from pathlib import Path
from time import perf_counter
import platform

import pytest
from deepdiff import DeepDiff
from django import VERSION as DJANGO_VERSION
from django.conf import settings
from django.core.management import CommandError, call_command
from django.test import override_settings
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
from django.utils.module_loading import import_string

from render_static import placeholders
from tests import bad_pattern, defines
from tests.enum_app.enums import DependentEnum, IndependentEnum
from tests.enum_app.models import EnumTester
from tests.test_core import (
    ENUM_STATIC_DIR,
    GLOBAL_STATIC_DIR,
    BaseTestCase,
)
from render_static.transpilers.base import CodeWriter
from render_static.transpilers.enums_to_js import IGNORED_ENUMS
from render_static.transpilers.urls_to_js import ClassURLWriter

try:
    from django.utils.decorators import classproperty
except ImportError:
    from django.utils.functional import classproperty


node_version = None
if shutil.which("node"):  # pragma: no cover
    match = re.match(r"v(\d+).(\d+).(\d+)", subprocess.getoutput("node --version"))
    if match:
        try:
            node_version = (
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
            )
        except (TypeError, ValueError):
            pass

if not node_version:  # pragma: no cover
    pytest.skip(
        "JavaScript tests require node.js to be installed.", allow_module_level=True
    )


class BadVisitor:
    pass


def get_content(file):
    with open(file, "r") as open_file:
        return open_file.read()


def get_url_mod():
    from tests import urls

    return urls


class BestEffortEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return json.JSONEncoder.default(self, obj)
        except TypeError:
            return str(obj)


def run_js_file(file_path):  # pragma: no cover
    try:
        return (
            subprocess.check_output(["node", file_path], stderr=subprocess.STDOUT)
            .decode("UTF-8")
            .strip()
        )
    except subprocess.CalledProcessError as cp_err:
        if cp_err.stderr:
            return cp_err.stderr.decode("UTF-8").strip()
        elif cp_err.output:
            return cp_err.output.decode("UTF-8").strip()
        elif cp_err.stdout:
            return cp_err.stdout.decode("UTF-8").strip()
        return ""


class StructureDiff:
    def diff_modules(self, js_file, py_modules):
        py_classes = []
        for module in py_modules:
            if isinstance(module, str):
                module = import_string(module)
            for key in dir(module):
                cls = getattr(module, key)
                if inspect.isclass(cls):
                    py_classes.append(cls)

        return self.diff_classes(js_file, py_classes)

    def get_js_structure(self, js_file):  # pragma: no cover
        json_structure = run_js_file(js_file)
        if json_structure:
            return json.loads(json_structure)
        return None

    def diff_classes(self, js_file, py_classes):
        """
        Given a javascript file and a list of classes, evaluate the javascript
        code into a python dictionary and determine if that dictionary matches
        the upper case parameters on the defines class.
        """
        members = {}
        js_dict = self.get_js_structure(js_file)

        def get_members(cls):
            lcls = {}
            if isinstance(cls, str):
                cls = import_string(cls)
            for mcls in reversed(cls.__mro__):
                new_mems = {n: getattr(mcls, n) for n in dir(mcls) if n.isupper()}
                if new_mems:
                    lcls.setdefault(cls.__name__, {}).update(new_mems)
            for nested in cls.__dict__.values():
                if inspect.isclass(nested):
                    lcls.setdefault(cls.__name__, {}).update(get_members(nested))
            return lcls

        for cls in py_classes:
            members.update(get_members(cls))

        from pprint import pprint

        pprint(members)
        return DeepDiff(
            members,
            js_dict,
            # treat tuples and lists the same
            ignore_type_in_groups=[(tuple, list)],
        )


@override_settings(
    STATIC_TEMPLATES={
        "ENGINES": [
            {
                "BACKEND": "render_static.backends.StaticDjangoTemplates",
                "OPTIONS": {
                    "app_dir": "custom_templates",
                    "loaders": [
                        (
                            "render_static.loaders.StaticLocMemLoader",
                            {
                                "defines1.js": '{% defines_to_js defines=classes indent="  " %}'
                                "\nconsole.log(JSON.stringify(defines));",
                                "defines2.js": "{% defines_to_js defines=modules %}"
                                "\nconsole.log(JSON.stringify(defines));",
                                "defines_error.js": "{% defines_to_js defines=classes %}"
                                "\nconsole.log(JSON.stringify(defines));",
                                "empty_defines.js": "{% defines_to_js defines=classes %}"
                                "\nconsole.log(JSON.stringify(defines));",
                            },
                        )
                    ],
                    "builtins": ["render_static.templatetags.render_static"],
                },
            }
        ],
        "templates": {
            "defines1.js": {
                "dest": GLOBAL_STATIC_DIR / "defines1.js",
                "context": {
                    "classes": [
                        defines.MoreDefines,
                        "tests.defines.ExtendedDefines",
                    ]
                },
            },
            "defines2.js": {
                "dest": GLOBAL_STATIC_DIR / "defines2.js",
                "context": {"modules": [defines, "tests.defines2"]},
            },
            "defines_error.js": {
                "dest": GLOBAL_STATIC_DIR / "defines_error.js",
                "context": {"classes": [0, {}]},
            },
            "empty_defines.js": {
                "dest": GLOBAL_STATIC_DIR / "empty_defines.js",
                "context": {"classes": ["tests.empty_defines"]},
            },
        },
    }
)
class DefinesToJavascriptTest(StructureDiff, BaseTestCase):
    # def tearDown(self):
    #     pass

    def test_classes_to_js(self):
        call_command("renderstatic", "defines1.js")
        self.assertEqual(
            self.diff_classes(
                js_file=GLOBAL_STATIC_DIR / "defines1.js",
                py_classes=settings.STATIC_TEMPLATES["templates"]["defines1.js"][
                    "context"
                ]["classes"],
            ),
            {},
        )
        # verify indent
        with open(GLOBAL_STATIC_DIR / "defines1.js", "r") as jf:
            jf.readline()
            self.assertTrue(jf.readline().startswith("  "))

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "app_dir": "custom_templates",
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "defines1.js": '{% defines_to_js defines="tests.defines.ExtendedDefines" indent="  " %}'
                                    "\nconsole.log(JSON.stringify(defines));"
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": [("defines1.js", {"dest": GLOBAL_STATIC_DIR / "defines1.js"})],
        }
    )
    def test_single_class_to_js(self):
        call_command("renderstatic", "defines1.js")
        from tests.defines import ExtendedDefines

        self.assertEqual(
            self.diff_classes(
                js_file=GLOBAL_STATIC_DIR / "defines1.js", py_classes=[ExtendedDefines]
            ),
            {},
        )

    def test_modules_to_js(self):
        call_command("renderstatic", "defines2.js")
        self.assertEqual(
            self.diff_modules(
                js_file=GLOBAL_STATIC_DIR / "defines2.js",
                py_modules=settings.STATIC_TEMPLATES["templates"]["defines2.js"][
                    "context"
                ]["modules"],
            ),
            {},
        )
        # verify indent
        with open(GLOBAL_STATIC_DIR / "defines2.js", "r") as jf:
            jf.readline()
            self.assertFalse(jf.readline().startswith(" "))

    def test_empty_module_to_js(self):
        call_command("renderstatic", "empty_defines.js")
        self.assertEqual(
            self.diff_modules(
                js_file=GLOBAL_STATIC_DIR / "empty_defines.js",
                py_modules=settings.STATIC_TEMPLATES["templates"]["empty_defines.js"][
                    "context"
                ]["classes"],
            ),
            {},
        )

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "app_dir": "custom_templates",
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "defines2.js": '{% defines_to_js defines="tests.defines2" %}'
                                    "\nconsole.log(JSON.stringify(defines));",
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": [("defines2.js", {"dest": GLOBAL_STATIC_DIR / "defines2.js"})],
        }
    )
    def test_single_module_to_js(self):
        call_command("renderstatic", "defines2.js")
        from tests import defines2

        self.assertEqual(
            self.diff_modules(
                js_file=GLOBAL_STATIC_DIR / "defines2.js", py_modules=[defines2]
            ),
            {},
        )

    def test_classes_to_js_error(self):
        self.assertRaises(
            CommandError, lambda: call_command("renderstatic", "defines_error.js")
        )

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "defines1.js": (
                                        "{% "
                                        'defines_to_js defines="'
                                        "tests.defines.MoreDefines "
                                        'tests.defines.ExtendedDefines"|split '
                                        'indent="  " %}'
                                        "\nconsole.log(JSON.stringify(defines));"
                                    ),
                                    "defines2.js": (
                                        '{% defines_to_js defines="tests.defines tests.defines2"|split indent="  " %}'
                                        "\nconsole.log(JSON.stringify(defines));"
                                    ),
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": {
                "defines1.js": {"dest": GLOBAL_STATIC_DIR / "defines1.js"},
                "defines2.js": {"dest": GLOBAL_STATIC_DIR / "defines2.js"},
            },
        }
    )
    def test_split(self):
        call_command("renderstatic", "defines1.js", "defines2.js")
        self.assertEqual(
            self.diff_classes(
                js_file=GLOBAL_STATIC_DIR / "defines1.js",
                py_classes=[defines.MoreDefines, defines.ExtendedDefines],
            ),
            {},
        )
        self.assertEqual(
            self.diff_modules(
                js_file=GLOBAL_STATIC_DIR / "defines2.js",
                py_modules=[
                    "tests.defines",
                    "tests.defines2",
                ],
            ),
            {},
        )

    # def tearDown(self):
    #     pass


@override_settings(
    STATIC_TEMPLATES={
        "ENGINES": [
            {
                "BACKEND": "render_static.backends.StaticDjangoTemplates",
                "OPTIONS": {
                    "app_dir": "custom_templates",
                    "loaders": [
                        (
                            "render_static.loaders.StaticLocMemLoader",
                            {
                                "defines1.js": """
{% defines_to_js defines=classes indent="  " %}
{% override %}
EXTRA_DEFINE: {
    'a': 1,
    'b': 2
}
{% endoverride %}
{% override "ExtendedDefines.DICTIONARY" %}
null
{% endoverride %}
{% enddefines_to_js %}
console.log(JSON.stringify(defines));
"""
                            },
                        )
                    ],
                    "builtins": ["render_static.templatetags.render_static"],
                },
            }
        ],
        "templates": {
            "defines1.js": {
                "dest": GLOBAL_STATIC_DIR / "defines1.js",
                "context": {
                    "classes": [
                        defines.MoreDefines,
                        "tests.defines.ExtendedDefines",
                    ]
                },
            }
        },
    }
)
class DefinesToJavascriptOverrideTest(StructureDiff, BaseTestCase):
    def tearDown(self):
        pass

    def test_define_overrides(self):
        call_command("renderstatic", "defines1.js")
        js_dict = self.get_js_structure(GLOBAL_STATIC_DIR / "defines1.js")
        self.assertEqual(
            js_dict,
            {
                "EXTRA_DEFINE": {"a": 1, "b": 2},
                "ExtendedDefines": {
                    "DEFINE1": "D1",
                    "DEFINE2": "D2",
                    "DEFINE3": "D3",
                    "DEFINE4": "D4",
                    "DEFINES": [
                        ["D1", "Define 1"],
                        ["D2", "Define 2"],
                        ["D3", "Define 3"],
                        ["D4", "Define 4"],
                    ],
                    "DICTIONARY": None,
                },
                "MoreDefines": {
                    "MDEF1": "MD1",
                    "MDEF2": "MD2",
                    "MDEF3": "MD3",
                    "MDEFS": [
                        ["MD1", "MDefine 1"],
                        ["MD2", "MDefine 2"],
                        ["MD3", "MDefine 3"],
                    ],
                    "BOOL1": True,
                    "BOOL2": False,
                },
            },
        )

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "app_dir": "custom_templates",
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "defines1.js": """
{% defines_to_js defines=classes indent="  " %}
{% override %}
EXTRA_DEFINE: {
    const_name: "{{ const_name }}"
}
{% endoverride %}
{% override "ExtendedDefines.DICTIONARY" %}
{
    const_name: "{{ const_name }}"
}
{% endoverride %}
{% enddefines_to_js %}
console.log(JSON.stringify(defines));
"""
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": {
                "defines1.js": {
                    "dest": GLOBAL_STATIC_DIR / "defines1.js",
                    "context": {
                        "classes": [
                            defines.MoreDefines,
                            "tests.defines.ExtendedDefines",
                        ],
                        "context_keys": [],
                    },
                }
            },
        }
    )
    def test_define_override_context(self):
        call_command("renderstatic", "defines1.js")
        js_dict = self.get_js_structure(GLOBAL_STATIC_DIR / "defines1.js")

        self.assertEqual(
            js_dict,
            {
                "EXTRA_DEFINE": {"const_name": "defines"},
                "ExtendedDefines": {
                    "DEFINE1": "D1",
                    "DEFINE2": "D2",
                    "DEFINE3": "D3",
                    "DEFINE4": "D4",
                    "DEFINES": [
                        ["D1", "Define 1"],
                        ["D2", "Define 2"],
                        ["D3", "Define 3"],
                        ["D4", "Define 4"],
                    ],
                    "DICTIONARY": {"const_name": "defines"},
                },
                "MoreDefines": {
                    "MDEF1": "MD1",
                    "MDEF2": "MD2",
                    "MDEF3": "MD3",
                    "MDEFS": [
                        ["MD1", "MDefine 1"],
                        ["MD2", "MDefine 2"],
                        ["MD3", "MDefine 3"],
                    ],
                    "BOOL1": True,
                    "BOOL2": False,
                },
            },
        )


class URLJavascriptMixin:
    url_js = None
    class_mode = None
    legacy_args = False

    def get_js_structure(self, js_file):  # pragma: no cover
        json_structure = run_js_file(js_file)
        if json_structure:
            return json.loads(json_structure)
        return None

    def clear_placeholder_registries(self):
        from importlib import reload

        reload(placeholders)

    def exists(self, *args, **kwargs):
        return len(self.get_url_from_js(*args, **kwargs)) > 0

    class TestJSGenerator(CodeWriter):
        class_mode = None
        legacy_args = (
            False  # generate code that uses separate arguments to js reverse calls
        )
        catch = True
        module = False

        def __init__(
            self, class_mode=None, catch=True, default_ns=None, module=False, **kwargs
        ):
            self.class_mode = class_mode
            self.catch = catch
            self.default_ns = default_ns
            self.module = module
            super().__init__(**kwargs)

        def generate(self, qname, kwargs=None, args=None, query=None):
            def do_gen():
                yield "try {" if self.catch else ""
                self.indent()
                if self.class_mode:
                    if self.default_ns:
                        yield f'const urls = new {self.class_mode}({{namespace: "{self.default_ns}"}});'
                    else:
                        yield f"const urls = new {self.class_mode}();"
                    yield "console.log("
                    self.indent()
                    yield f"urls.reverse("
                    self.indent()
                    yield f'"{qname}",{"" if self.legacy_args else " {"}'
                else:
                    accessor_str = "".join([f'["{comp}"]' for comp in qname.split(":")])
                    yield "console.log("
                    self.indent()
                    yield f"urls{accessor_str}({'' if self.legacy_args else '{'}"
                    self.indent()
                yield (
                    f"{'' if self.legacy_args else 'kwargs: '}"
                    f"{json.dumps(kwargs, cls=BestEffortEncoder)}{',' if args or query else ''}"
                )
                if args:
                    yield (
                        f"{'' if self.legacy_args else 'args: '}"
                        f"{json.dumps(args, cls=BestEffortEncoder)}{',' if query else ''}"
                    )
                if query:
                    yield (
                        f"{'' if self.legacy_args else 'query: '}"
                        f"{json.dumps(query, cls=BestEffortEncoder)}"
                    )
                self.outdent(2)
                yield f"{'' if self.legacy_args else '}'}));"
                if self.catch:
                    self.outdent()
                    yield "} catch (error) {}"

            for line in do_gen():
                self.write_line(line)

            return self.rendered_

    def get_url_from_js(
        self,
        qname,
        kwargs=None,
        args=None,
        query=None,
        js_generator=None,
        url_path=GLOBAL_STATIC_DIR / "urls.js",
        default_ns=None,
    ):  # pragma: no cover
        if kwargs is None:
            kwargs = {}
        if args is None:
            args = []
        if query is None:
            query = {}
        if js_generator is None:
            js_generator = URLJavascriptMixin.TestJSGenerator(
                self.class_mode, legacy_args=self.legacy_args, default_ns=default_ns
            )
        tmp_file_pth = (
            GLOBAL_STATIC_DIR
            / f"get_{url_path.stem}.{'m' if js_generator.module else ''}js"
        )

        makedirs(GLOBAL_STATIC_DIR, exist_ok=True)
        if os.path.exists(tmp_file_pth):
            os.remove(tmp_file_pth)

        with open(tmp_file_pth, "wt") as tmp_js:
            if not js_generator.module:
                with open(url_path, "rt") as url_js:
                    tmp_js.write(url_js.read())
            if js_generator.module:
                if platform.system() == "Windows":
                    pth_str = str(url_path).replace(os.sep, "/")
                    tmp_js.write(
                        f'import {{ {js_generator.class_mode} }} from "file://{pth_str}";\n'
                    )
                else:
                    tmp_js.write(
                        f'import {{ {js_generator.class_mode} }} from "{url_path}";\n'
                    )
            js_code = js_generator.generate(qname, kwargs, args, query)
            tmp_js.write(js_code)

        return run_js_file(tmp_file_pth)

    def compare(
        self,
        qname,
        kwargs=None,
        args=None,
        query=None,
        object_hook=lambda dct: dct,
        args_hook=lambda args: args,
        url_path=GLOBAL_STATIC_DIR / "urls.js",
        js_generator=None,
    ):
        if kwargs is None:
            kwargs = {}
        if args is None:
            args = []
        if query is None or not self.class_mode:
            query = {}

        tst_pth = self.get_url_from_js(
            qname, kwargs, args, query, js_generator=js_generator, url_path=url_path
        )
        resp = self.client.get(tst_pth)

        try:
            resp = resp.json(object_hook=object_hook)
        except ValueError:
            print(resp.content)
            raise
        resp["args"] = args_hook(resp["args"])
        self.assertEqual(
            {
                "request": reverse(qname, kwargs=kwargs, args=args),
                "args": args,
                "kwargs": kwargs,
                "query": query,
            },
            resp,
        )

    @staticmethod
    def convert_to_id(dct, key="id"):
        if key in dct:
            dct[key] = uuid.UUID(dct[key])
        return dct

    @staticmethod
    def convert_to_int(dct, key):
        if key in dct:
            dct[key] = int(dct[key])
        return dct

    @staticmethod
    def convert_to_int_list(dct, key):
        if key in dct:
            dct[key] = [int(val) for val in dct[key]]
        return dct

    @staticmethod
    def convert_idx_to_type(arr, idx, typ):
        arr[idx] = typ(arr[idx])
        return arr


@override_settings(
    STATIC_TEMPLATES={
        "ENGINES": [
            {
                "BACKEND": "render_static.backends.StaticDjangoTemplates",
                "OPTIONS": {
                    "loaders": [
                        (
                            "render_static.loaders.StaticLocMemLoader",
                            {
                                "urls.js": 'var urls = {\n{% urls_to_js transpiler="render_static.transpilers.SimpleURLWriter" %}};'
                            },
                        )
                    ],
                    "builtins": ["render_static.templatetags.render_static"],
                },
            }
        ]
    }
)
class URLSToJavascriptTest(URLJavascriptMixin, BaseTestCase):
    def tearDown(self):
        pass

    def setUp(self):
        self.clear_placeholder_registries()
        placeholders.register_variable_placeholder("strarg", "a")
        placeholders.register_variable_placeholder("intarg", 0)
        placeholders.register_variable_placeholder("intarg", 0)

        placeholders.register_variable_placeholder("name", "deadbeef")
        placeholders.register_variable_placeholder("name", "name1")
        placeholders.register_variable_placeholder("name", "deadbeef", app_name="app1")

        placeholders.register_unnamed_placeholders("re_path_unnamed", ["adf", 143])
        # repeat for cov
        placeholders.register_unnamed_placeholders("re_path_unnamed", ["adf", 143])
        placeholders.register_unnamed_placeholders(
            "re_path_unnamed_solo",
            ["adf", 143],
            app_name="bogus_app",  # this should still work because all placeholders that match any
            # criteria are tried
        )
        # repeat for coverage
        placeholders.register_unnamed_placeholders(
            "re_path_unnamed_solo", ["adf", 143], app_name="bogus_app"
        )

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": '{% urls_to_js transpiler="render_static.transpilers.ClassURLWriter" %}'
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
        }
    )
    def test_full_url_dump_class_es6(self):
        """
        Test es6 url class.
        """
        self.class_mode = ClassURLWriter.class_name_
        self.test_full_url_dump()
        self.class_mode = None

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": '{% urls_to_js transpiler="render_static.transpilers.ClassURLWriter" %}'
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
        }
    )
    def test_full_url_dump_class_es6_legacy_args(self):
        """
        Test class code with legacy arguments specified individually - may be deprecated in 2.0
        """
        self.class_mode = ClassURLWriter.class_name_
        self.legacy_args = True
        self.test_full_url_dump()
        self.class_mode = None
        self.legacy_args = False

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": "var urls = {\n"
                                    '{% urls_to_js transpiler="render_static.transpilers.SimpleURLWriter" include=include %}'
                                    "\n};"
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "context": {"include": ["admin"]},
        }
    )
    def test_admin_urls(self):
        """
        Admin urls should work out-of-box - just check that it doesnt raise
        """
        call_command("renderstatic", "urls.js")
        self.assertTrue(True)

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": '{% urls_to_js transpiler="render_static.transpilers.ClassURLWriter" %}'
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
        }
    )
    def test_full_url_dump_class(self):
        """
        Test ES5 classes.
        """
        self.class_mode = ClassURLWriter.class_name_
        self.test_full_url_dump()
        self.class_mode = None

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": '{% urls_to_js transpiler="render_static.transpilers.ClassURLWriter" %}'
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
        }
    )
    def test_full_url_dump_class_legacy_args(self):
        """
        This ES5 classes
        """
        self.class_mode = ClassURLWriter.class_name_
        self.legacy_args = True
        self.test_full_url_dump()
        self.class_mode = None
        self.legacy_args = False

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": 'const urls = {\n{% urls_to_js transpiler="render_static.transpilers.SimpleURLWriter" %}};'
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
        }
    )
    def test_full_url_dump_es6(self):
        """
        Test ES6 classes.
        """
        self.test_full_url_dump()

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": """
const urls = {
{% urls_to_js transpiler="render_static.transpilers.SimpleURLWriter"  include="path_tst,re_path_mixed,app2:app1"|split:"," exclude="admin"|split raise_on_not_found=False%}
    {% override "re_path_mixed" %}
return {
    'qname': '{{qname}}',
    'raise_on_not_found': {% if raise_on_not_found %}true{% else %}false{% endif %},
    'include': [{% for inc in include %}'{{ inc }}',{% endfor %}],
    'exclude': [{% for exc in exclude %}'{{ exc }}',{% endfor %}],
};
    {% endoverride %}
    {% override "app2:app1:re_path_unnamed" %}
return {
    'qname': '{{qname}}',
    'raise_on_not_found': {% if raise_on_not_found %}true{% else %}false{% endif %},
    'include': [{% for inc in include %}'{{ inc }}',{% endfor %}],
    'exclude': [{% for exc in exclude %}'{{ exc }}',{% endfor %}],
};
    {% endoverride %}
    {% override %}
    extra: () => {
        return JSON.stringify({
            're_path_mixed': urls['re_path_mixed'](),
            'app2:app1:re_path_unnamed': urls.app2.app1.re_path_unnamed(),
            'path_tst': urls['path_tst']()
        })
    }
    {% endoverride %}
{% endurls_to_js %}
};
console.log(urls.extra());
"""
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
        }
    )
    def test_simple_url_overrides(self):
        """
        Check that SimpleURLWriter qname overrides work as expected.
        """
        self.url_js = None
        call_command("renderstatic", "urls.js")
        js_dict = self.get_js_structure(GLOBAL_STATIC_DIR / "urls.js")

        expected_context = {
            "exclude": ["admin"],
            "include": ["path_tst", "re_path_mixed", "app2:app1"],
            "raise_on_not_found": False,
        }
        for key, value in {"qname": "re_path_mixed", **expected_context}.items():
            self.assertEqual(js_dict["re_path_mixed"][key], value)

        for key, value in {
            "qname": "app2:app1:re_path_unnamed",
            **expected_context,
        }.items():
            self.assertEqual(js_dict["app2:app1:re_path_unnamed"][key], value)

        self.assertEqual(js_dict["path_tst"], "/test/simple/")

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": """
{% urls_to_js transpiler="render_static.transpilers.ClassURLWriter"  include="path_tst,re_path_mixed,app2:app1"|split:"," exclude="admin"|split raise_on_not_found=False%}

    {% override "constructor" %}

constructor(options=null) {
    this.constructor_ctx = {
        'raise_on_not_found': {% if raise_on_not_found %}true{% else %}false{% endif %},
        'include': [{% for inc in include %}'{{ inc }}',{% endfor %}],
        'exclude': [{% for exc in exclude %}'{{ exc }}',{% endfor %}],
    };
    {{ default_impl }}
}
    {% endoverride %}

    {% override "#match" %}

#match(kwargs, args, expected, defaults={}) {
    this.match_ctx = {
        'raise_on_not_found': {% if raise_on_not_found %}true{% else %}false{% endif %},
        'include': [{% for inc in include %}'{{ inc }}',{% endfor %}],
        'exclude': [{% for exc in exclude %}'{{ exc }}',{% endfor %}],
    };
    {{ default_impl }}
}
    {% endoverride %}

    {% override "deepEqual" %}

deepEqual(object1, object2) {
    this.deepEqual_ctx = {
        'raise_on_not_found': {% if raise_on_not_found %}true{% else %}false{% endif %},
        'include': [{% for inc in include %}'{{ inc }}',{% endfor %}],
        'exclude': [{% for exc in exclude %}'{{ exc }}',{% endfor %}],
    };
    {{ default_impl }}
}
    {% endoverride %}

    {% override "isObject" %}

isObject(object) {
    this.isObject_ctx = {
        'raise_on_not_found': {% if raise_on_not_found %}true{% else %}false{% endif %},
        'include': [{% for inc in include %}'{{ inc }}',{% endfor %}],
        'exclude': [{% for exc in exclude %}'{{ exc }}',{% endfor %}],
    };
    {{ default_impl }}
}
    {% endoverride %}

    {% override "reverse" %}

reverse(qname, options={}) {
    {{ default_impl }}
    this.reverse_ctx = {
        'raise_on_not_found': {% if raise_on_not_found %}true{% else %}false{% endif %},
        'include': [{% for inc in include %}'{{ inc }}',{% endfor %}],
        'exclude': [{% for exc in exclude %}'{{ exc }}',{% endfor %}],
    };
    return url(kwargs, args);
}
    {% endoverride %}

    {% override "re_path_mixed" %}
return {
    'qname': '{{qname}}',
    'raise_on_not_found': {% if raise_on_not_found %}true{% else %}false{% endif %},
    'include': [{% for inc in include %}'{{ inc }}',{% endfor %}],
    'exclude': [{% for exc in exclude %}'{{ exc }}',{% endfor %}],
};
    {% endoverride %}
    {% override "app2:app1:re_path_unnamed" %}
return {
    'qname': '{{qname}}',
    'raise_on_not_found': {% if raise_on_not_found %}true{% else %}false{% endif %},
    'include': [{% for inc in include %}'{{ inc }}',{% endfor %}],
    'exclude': [{% for exc in exclude %}'{{ exc }}',{% endfor %}],
};
    {% endoverride %}
    {% override %}
extra() {
    return JSON.stringify({
        're_path_mixed': urls.reverse('re_path_mixed'),
        'app2:app1:re_path_unnamed': urls.reverse('app2:app1:re_path_unnamed'),
        'path_tst': urls.reverse('path_tst', {kwargs: {arg1: 1, arg2: 'xo'}}),
        'deepEqual': this.deepEqual({a: 1}, {a: 1}),
        'extra_ctx': {
            'raise_on_not_found': {% if raise_on_not_found %}true{% else %}false{% endif %},
            'include': [{% for inc in include %}'{{ inc }}',{% endfor %}],
            'exclude': [{% for exc in exclude %}'{{ exc }}',{% endfor %}],
        },
        'constructor_ctx': this.constructor_ctx,
        'match_ctx': this.match_ctx,
        'deepEqual_ctx': this.deepEqual_ctx,
        'isObject_ctx': this.isObject_ctx,
        'reverse_ctx': this.reverse_ctx
    })
}
    {% endoverride %}
{% endurls_to_js %}
urls = new URLResolver();
console.log(urls.extra());
"""
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
        }
    )
    def test_class_url_overrides(self):
        """
        Check that SimpleURLWriter qname overrides work as expected.
        """
        self.url_js = None
        call_command("renderstatic", "urls.js")
        js_dict = self.get_js_structure(GLOBAL_STATIC_DIR / "urls.js")

        expected_context = {
            "exclude": ["admin"],
            "include": ["path_tst", "re_path_mixed", "app2:app1"],
            "raise_on_not_found": False,
        }
        for key, value in {"qname": "re_path_mixed", **expected_context}.items():
            self.assertEqual(js_dict["re_path_mixed"][key], value)

        for key, value in {
            "qname": "app2:app1:re_path_unnamed",
            **expected_context,
        }.items():
            self.assertEqual(js_dict["app2:app1:re_path_unnamed"][key], value)

        self.assertEqual(js_dict["path_tst"], "/test/different/1/xo")

        functions = ["constructor", "match", "reverse"]
        if DJANGO_VERSION[0:2] < (4, 1):  # pragma: no cover
            self.assertTrue(js_dict["deepEqual"])
            functions.append("deepEqual")
            functions.append("isObject")
        else:  # pragma: no cover
            pass

        for func in functions:
            for key, value in expected_context.items():
                self.assertEqual(js_dict[func + "_ctx"][key], value)

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": 'var urls = {\n{% urls_to_js transpiler="render_static.transpilers.SimpleURLWriter" %}};'
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
        }
    )
    def test_full_url_dump_es6_legacy_args(self):
        """
        Test legacy argument signature - args specified individually on url() calls in javascript.
        """
        self.legacy_args = True
        self.test_full_url_dump()
        self.legacy_args = False

    def test_full_url_dump(self):
        self.url_js = None

        call_command("renderstatic", "urls.js")

        #################################################################
        # root urls
        qname = "path_tst"
        self.compare(qname)
        self.compare(
            qname,
            {"arg1": 1},
            query={"intq1": 0, "str": "aadf"} if not self.legacy_args else {},
            object_hook=lambda dct: self.convert_to_int(dct, "intq1"),
        )
        self.compare(qname, {"arg1": 12, "arg2": "xo"})
        #################################################################

        #################################################################
        # app1 straight include 1
        qname = "sub1:app1_pth"
        self.compare(qname)
        self.compare(qname, {"arg1": 143})  # emma
        self.compare(
            qname,
            {"arg1": 5678, "arg2": "xo"},
            query={"intq1": "0", "intq2": "2"} if not self.legacy_args else {},
        )
        self.compare(
            "sub1:app1_detail", {"id": uuid.uuid1()}, object_hook=self.convert_to_id
        )
        self.compare("sub1:custom_tst", {"year": 2021})
        self.compare("sub1:unreg_conv_tst", {"name": "name2"})
        self.compare(
            "sub1:re_path_unnamed",
            args=["af", 5678],
            query={"intq1": "0", "intq2": "2"} if not self.legacy_args else {},
            args_hook=lambda arr: self.convert_idx_to_type(arr, 1, int),
        )
        #################################################################

        #################################################################
        # app1 straight include 2
        qname = "sub2:app1_pth"
        self.compare(qname)
        self.compare(qname, {"arg1": 143})  # emma
        self.compare(qname, {"arg1": 5678, "arg2": "xo"})
        self.compare(
            "sub2:app1_detail", {"id": uuid.uuid1()}, object_hook=self.convert_to_id
        )
        self.compare("sub2:custom_tst", {"year": 1021})
        self.compare("sub2:unreg_conv_tst", {"name": "name2"})
        self.compare(
            "sub2:re_path_unnamed",
            args=["af", 5678],
            args_hook=lambda arr: self.convert_idx_to_type(arr, 1, int),
        )
        #################################################################

        #################################################################
        # app1 include with hierarchical variable - DJANGO doesnt support this!
        # maybe it will someday - leave test here
        # qname = 'sub2:app1_pth'
        # self.compare(qname, {'root_var': 'root'})
        # self.compare(qname, {'arg1': 143,'root_var': 'root'})  # emma
        # self.compare(qname, {'arg1': 5678, 'arg2': 'xo', 'root_var': 'root'})
        # self.compare(
        #    'sub2:app1_detail',
        #    {'id': uuid.uuid1(), 'root_var': 'root'},
        #    object_hook=self.convert_to_id
        # )
        # self.compare('sub2:custom_tst', {'year': 1021, 'root_var': 'root'})
        # self.compare('sub2:unreg_conv_tst', {'name': 'name2', 'root_var': 'root'})
        #################################################################

        #################################################################
        # app1 include through app2
        qname = "app2:app1:app1_pth"
        self.compare(qname)
        self.compare(qname, {"arg1": 1})
        self.compare(qname, {"arg1": 12, "arg2": "xo"})
        self.compare(
            "app2:app1:app1_detail",
            {"id": uuid.uuid1()},
            object_hook=self.convert_to_id,
        )
        self.compare("app2:app1:custom_tst", {"year": 2999})
        self.compare("app2:app1:unreg_conv_tst", {"name": "name1"})
        self.compare(
            "app2:app1:re_path_unnamed",
            args=["af", 5678],
            args_hook=lambda arr: self.convert_idx_to_type(arr, 1, int),
        )
        #################################################################

        #################################################################
        # app2 include w/ app_name namespace
        qname = "app2:app2_pth"
        self.compare(qname)
        self.compare(qname, {"arg1": "adf23"})
        self.compare(
            "app2:app2_pth_diff",
            {"arg2": "this/is/a/path/", "arg1": uuid.uuid1()},
            object_hook=lambda dct: self.convert_to_id(dct, "arg1"),
        )
        self.compare(
            "app2:app2_pth_diff",
            {"arg2": "so/is/this", "arg1": uuid.uuid1()},
            object_hook=lambda dct: self.convert_to_id(dct, "arg1"),
        )
        #################################################################

        #################################################################
        # re_paths

        self.compare(
            "re_path_tst",
            query={"pre": "A", "list1": ["0", "3", "4"], "post": "B"}
            if not self.legacy_args
            else {},
        )
        self.compare("re_path_tst", {"strarg": "DEMOPLY"})
        self.compare(
            "re_path_tst",
            {"strarg": "is", "intarg": 1337},
            query={"pre": "A", "list1": ["0", "3", "4"], "intarg": 237}
            if not self.legacy_args
            else {},
            object_hook=lambda dct: self.convert_to_int(dct, "intarg"),
        )

        self.compare(
            "re_path_unnamed",
            args=["af", 5678],
            args_hook=lambda arr: self.convert_idx_to_type(arr, 1, int),
        )

        self.compare(
            "re_path_unnamed_solo",
            args=["daf", 7120],
            args_hook=lambda arr: self.convert_idx_to_type(arr, 1, int),
        )
        #################################################################

        #################################################################
        # app3 urls - these should be included into the null namespace
        self.compare("app3_idx")
        self.compare(
            "app3_arg",
            {"arg1": 1},
            query={"list1": ["0", "3", "4"], "intarg": [0, 2, 5], "post": "A"}
            if not self.legacy_args
            else {},
            object_hook=lambda dct: self.convert_to_int_list(dct, "intarg"),
        )
        self.compare("unreg_conv_tst", {"name": "name1"})
        #################################################################

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": "var urls = {\n"
                                    "{% urls_to_js "
                                    'transpiler="render_static.transpilers.SimpleURLWriter" '
                                    "include=include "
                                    "exclude=exclude "
                                    "%}};"
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": {
                "urls.js": {
                    "context": {
                        "include": [
                            "path_tst",
                            "app2:app1",
                            "sub1:app1_detail",
                            "sub2:app1_pth",
                        ],
                        "exclude": [
                            "app2:app1:custom_tst",
                            "app2:app1:app1_detail",
                            "sub2:app1_pth",
                        ],
                    }
                }
            },
        }
    )
    def test_filtering(self):
        self.url_js = None

        call_command("renderstatic", "urls.js")

        self.assertFalse(self.exists("admin:index"))

        qname = "path_tst"
        self.assertTrue(self.exists(qname))
        self.assertTrue(self.exists(qname, {"arg1": 1}))
        self.assertTrue(self.exists(qname, {"arg1": 12, "arg2": "xo"}))

        self.assertFalse(self.exists("app3_idx"))
        self.assertFalse(self.exists("app3_arg", {"arg1": 1}))

        qname = "app2:app1:app1_pth"
        self.assertTrue(self.exists(qname))
        self.assertTrue(self.exists(qname, {"arg1": 1}))
        self.assertTrue(self.exists(qname, {"arg1": 12, "arg2": "xo"}))
        self.assertFalse(self.exists("app2:app1:app1_detail", {"id": uuid.uuid1()}))
        self.assertFalse(self.exists("app2:app1:custom_tst", {"year": 2999}))

        qname = "sub1:app1_pth"
        self.assertFalse(self.exists(qname))
        self.assertFalse(self.exists(qname, {"arg1": 143}))  # emma
        self.assertFalse(self.exists(qname, {"arg1": 5678, "arg2": "xo"}))
        self.assertTrue(self.exists("sub1:app1_detail", {"id": uuid.uuid1()}))
        self.assertFalse(self.exists("sub1:custom_tst", {"year": 2021}))

        qname = "sub2:app1_pth"
        self.assertFalse(self.exists(qname))
        self.assertFalse(self.exists(qname, {"arg1": 143}))  # emma
        self.assertFalse(self.exists(qname, {"arg1": 5678, "arg2": "xo"}))
        self.assertFalse(self.exists("sub2:app1_detail", {"id": uuid.uuid1()}))
        self.assertFalse(self.exists("sub2:custom_tst", {"year": 1021}))

        qname = "app2:app2_pth"
        self.assertFalse(self.exists(qname))
        self.assertFalse(self.exists(qname, {"arg1": "adf23"}))
        self.assertFalse(
            self.exists(
                "app2:app2_pth_diff", {"arg2": "this/is/a/path/", "arg1": uuid.uuid1()}
            )
        )
        self.assertFalse(
            self.exists(
                "app2:app2_pth_diff", {"arg2": "so/is/this", "arg1": uuid.uuid1()}
            )
        )

        self.assertFalse(self.exists("re_path_tst"))
        self.assertFalse(self.exists("re_path_tst", {"strarg": "DEMOPLY"}))
        self.assertFalse(self.exists("re_path_tst", {"strarg": "is", "intarg": 1337}))
        self.assertFalse(self.exists("re_path_unnamed", args=["af", 5678]))
        self.assertFalse(self.exists("re_path_unnamed_solo", args=["daf", 7120]))

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": "var urls = {\n"
                                    "{% urls_to_js "
                                    'transpiler="render_static.transpilers.SimpleURLWriter" '
                                    "include=include "
                                    "exclude=exclude "
                                    "%}};"
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": {
                "urls.js": {
                    "context": {
                        "exclude": [
                            "admin",
                            "app2:app1:custom_tst",
                            "app2:app1:app1_detail",
                            "sub2:app1_pth",
                        ]
                    }
                }
            },
        }
    )
    def test_filtering_excl_only(self):
        self.url_js = None

        call_command("renderstatic", "urls.js")

        self.assertFalse(self.exists("admin:index"))

        qname = "path_tst"
        self.assertTrue(self.exists(qname))
        self.assertTrue(self.exists(qname, {"arg1": 1}))
        self.assertTrue(self.exists(qname, {"arg1": 12, "arg2": "xo"}))

        self.assertTrue(self.exists("app3_idx"))
        self.assertTrue(self.exists("app3_arg", {"arg1": 1}))

        qname = "app2:app1:app1_pth"
        self.assertTrue(self.exists(qname))
        self.assertTrue(self.exists(qname, {"arg1": 1}))
        self.assertTrue(self.exists(qname, {"arg1": 12, "arg2": "xo"}))
        self.assertFalse(self.exists("app2:app1:app1_detail", {"id": uuid.uuid1()}))
        self.assertFalse(self.exists("app2:app1:custom_tst", {"year": 2999}))

        qname = "sub1:app1_pth"
        self.assertTrue(self.exists(qname))
        self.assertTrue(self.exists(qname, {"arg1": 143}))  # emma
        self.assertTrue(self.exists(qname, {"arg1": 5678, "arg2": "xo"}))
        self.assertTrue(self.exists("sub1:app1_detail", {"id": uuid.uuid1()}))
        self.assertTrue(self.exists("sub1:custom_tst", {"year": 2021}))

        qname = "sub2:app1_pth"
        self.assertFalse(self.exists(qname))
        self.assertFalse(self.exists(qname, {"arg1": 143}))  # emma
        self.assertFalse(self.exists(qname, {"arg1": 5678, "arg2": "xo"}))
        self.assertTrue(self.exists("sub2:app1_detail", {"id": uuid.uuid1()}))
        self.assertTrue(self.exists("sub2:custom_tst", {"year": 1021}))

        qname = "app2:app2_pth"
        self.assertTrue(self.exists(qname))
        self.assertTrue(self.exists(qname, {"arg1": "adf23"}))
        self.assertTrue(
            self.exists(
                "app2:app2_pth_diff", {"arg2": "this/is/a/path/", "arg1": uuid.uuid1()}
            )
        )
        self.assertTrue(
            self.exists(
                "app2:app2_pth_diff", {"arg2": "so/is/this", "arg1": uuid.uuid1()}
            )
        )

        self.assertTrue(self.exists("re_path_tst"))
        self.assertTrue(self.exists("re_path_tst", {"strarg": "DEMOPLY"}))
        self.assertTrue(self.exists("re_path_tst", {"strarg": "is", "intarg": 1337}))
        self.assertTrue(self.exists("re_path_unnamed", args=["af", 5678]))
        self.assertTrue(self.exists("re_path_unnamed_solo", args=["daf", 7120]))

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": "var urls = {\n"
                                    "{% urls_to_js "
                                    "url_conf=url_mod "
                                    'transpiler="render_static.transpilers.SimpleURLWriter" '
                                    "include=include "
                                    "exclude=exclude "
                                    "%}};"
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": {
                "urls.js": {
                    "context": {
                        "url_mod": get_url_mod(),
                        "include": [""],
                        "exclude": ["admin", "app2", "sub2", "sub1"],
                    }
                }
            },
        }
    )
    def test_filtering_null_ns_incl(self):
        self.es6_mode = True
        self.url_js = None

        call_command("renderstatic", "urls.js")

        self.assertFalse(self.exists("admin:index"))

        qname = "path_tst"
        self.assertTrue(self.exists(qname))
        self.assertTrue(self.exists(qname, {"arg1": 1}))
        self.assertTrue(self.exists(qname, {"arg1": 12, "arg2": "xo"}))

        self.assertTrue(self.exists("app3_idx"))
        self.assertTrue(self.exists("app3_arg", {"arg1": 1}))

        qname = "app2:app1:app1_pth"
        self.assertFalse(self.exists(qname))
        self.assertFalse(self.exists(qname, {"arg1": 1}))
        self.assertFalse(self.exists(qname, {"arg1": 12, "arg2": "xo"}))
        self.assertFalse(self.exists("app2:app1:app1_detail", {"id": uuid.uuid1()}))
        self.assertFalse(self.exists("app2:app1:custom_tst", {"year": 2999}))

        qname = "sub1:app1_pth"
        self.assertFalse(self.exists(qname))
        self.assertFalse(self.exists(qname, {"arg1": 143}))  # emma
        self.assertFalse(self.exists(qname, {"arg1": 5678, "arg2": "xo"}))
        self.assertFalse(self.exists("sub1:app1_detail", {"id": uuid.uuid1()}))
        self.assertFalse(self.exists("sub1:custom_tst", {"year": 2021}))

        qname = "sub2:app1_pth"
        self.assertFalse(self.exists(qname))
        self.assertFalse(self.exists(qname, {"arg1": 143}))  # emma
        self.assertFalse(self.exists(qname, {"arg1": 5678, "arg2": "xo"}))
        self.assertFalse(self.exists("sub2:app1_detail", {"id": uuid.uuid1()}))
        self.assertFalse(self.exists("sub2:custom_tst", {"year": 1021}))

        qname = "app2:app2_pth"
        self.assertFalse(self.exists(qname))
        self.assertFalse(self.exists(qname, {"arg1": "adf23"}))
        self.assertFalse(
            self.exists(
                "app2:app2_pth_diff", {"arg2": "this/is/a/path/", "arg1": uuid.uuid1()}
            )
        )
        self.assertFalse(
            self.exists(
                "app2:app2_pth_diff", {"arg2": "so/is/this", "arg1": uuid.uuid1()}
            )
        )

        self.assertTrue(self.exists("re_path_tst"))
        self.assertTrue(self.exists("re_path_tst", {"strarg": "DEMOPLY"}))
        self.assertTrue(self.exists("re_path_tst", {"strarg": "is", "intarg": 1337}))
        self.assertTrue(self.exists("re_path_unnamed", args=["af", 5678]))
        self.assertTrue(self.exists("re_path_unnamed_solo", args=["daf", 7120]))

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": "var urls = {\n"
                                    "{% urls_to_js "
                                    'url_conf="tests.urls" '
                                    'transpiler="render_static.transpilers.SimpleURLWriter" '
                                    "include=include "
                                    "exclude=exclude "
                                    "%}};"
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": {"urls.js": {"context": {"include": ["path_tst"]}}},
        }
    )
    def test_top_lvl_ns_incl(self):
        self.es6_mode = True
        self.url_js = None

        call_command("renderstatic", "urls.js")

        self.assertFalse(self.exists("admin:index"))

        qname = "path_tst"
        self.assertTrue(self.exists(qname))
        self.assertTrue(self.exists(qname, {"arg1": 1}))
        self.assertTrue(self.exists(qname, {"arg1": 12, "arg2": "xo"}))

        self.assertFalse(self.exists("app3_idx"))
        self.assertFalse(self.exists("app3_arg", {"arg1": 1}))

        qname = "app2:app1:app1_pth"
        self.assertFalse(self.exists(qname))
        self.assertFalse(self.exists(qname, {"arg1": 1}))
        self.assertFalse(self.exists(qname, {"arg1": 12, "arg2": "xo"}))
        self.assertFalse(self.exists("app2:app1:app1_detail", {"id": uuid.uuid1()}))
        self.assertFalse(self.exists("app2:app1:custom_tst", {"year": 2999}))

        qname = "sub1:app1_pth"
        self.assertFalse(self.exists(qname))
        self.assertFalse(self.exists(qname, {"arg1": 143}))  # emma
        self.assertFalse(self.exists(qname, {"arg1": 5678, "arg2": "xo"}))
        self.assertFalse(self.exists("sub1:app1_detail", {"id": uuid.uuid1()}))
        self.assertFalse(self.exists("sub1:custom_tst", {"year": 2021}))

        qname = "sub2:app1_pth"
        self.assertFalse(self.exists(qname))
        self.assertFalse(self.exists(qname, {"arg1": 143}))  # emma
        self.assertFalse(self.exists(qname, {"arg1": 5678, "arg2": "xo"}))
        self.assertFalse(self.exists("sub2:app1_detail", {"id": uuid.uuid1()}))
        self.assertFalse(self.exists("sub2:custom_tst", {"year": 1021}))

        qname = "app2:app2_pth"
        self.assertFalse(self.exists(qname))
        self.assertFalse(self.exists(qname, {"arg1": "adf23"}))
        self.assertFalse(
            self.exists(
                "app2:app2_pth_diff", {"arg2": "this/is/a/path/", "arg1": uuid.uuid1()}
            )
        )
        self.assertFalse(
            self.exists(
                "app2:app2_pth_diff", {"arg2": "so/is/this", "arg1": uuid.uuid1()}
            )
        )

        self.assertFalse(self.exists("re_path_tst"))
        self.assertFalse(self.exists("re_path_tst", {"strarg": "DEMOPLY"}))
        self.assertFalse(self.exists("re_path_tst", {"strarg": "is", "intarg": 1337}))
        self.assertFalse(self.exists("re_path_unnamed", args=["af", 5678]))
        self.assertFalse(self.exists("re_path_unnamed_solo", args=["daf", 7120]))

    # uncomment to not delete generated js
    # def tearDown(self):
    #    pass


@override_settings(
    ROOT_URLCONF="tests.urls2",
    STATIC_TEMPLATES={
        "ENGINES": [
            {
                "BACKEND": "render_static.backends.StaticDjangoTemplates",
                "OPTIONS": {
                    "loaders": [
                        (
                            "render_static.loaders.StaticLocMemLoader",
                            {
                                "urls.js": (
                                    "{% urls_to_js "
                                    'transpiler="render_static.transpilers.ClassURLWriter" '
                                    "include=include "
                                    "%}"
                                )
                            },
                        )
                    ],
                    "builtins": ["render_static.templatetags.render_static"],
                },
            }
        ],
        "templates": {"urls.js": {"context": {"include": ["default"]}}},
    },
)
class CornerCaseTest(URLJavascriptMixin, BaseTestCase):
    def setUp(self):
        self.clear_placeholder_registries()

    def test_no_default_registered(self):
        """
        Tests: https://github.com/bckohan/django-render-static/issues/8
        :return:
        """
        self.es6_mode = True
        self.url_js = None
        self.class_mode = ClassURLWriter.class_name_

        call_command("renderstatic", "urls.js")
        self.compare("default", kwargs={"def": "named"})
        self.compare("default", args=["unnamed"])

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": (
                                        "{% urls_to_js "
                                        'transpiler="render_static.transpilers.ClassURLWriter" '
                                        "include=include "
                                        "%}"
                                    )
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": {"urls.js": {"context": {"include": ["no_capture"]}}},
        }
    )
    def test_non_capturing_unnamed(self):
        """
        Tests that unnamed arguments can still work when the users also include non-capturing groups
        for whatever reason. Hard to imagine an actual use case for these - but reverse still seems
        to work, so javascript reverse should too
        :return:
        """
        self.es6_mode = True
        self.url_js = None
        self.class_mode = ClassURLWriter.class_name_

        placeholders.register_unnamed_placeholders("no_capture", ["0000"])
        call_command("renderstatic", "urls.js")
        self.compare("no_capture", args=["5555"])

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": (
                                        "{% urls_to_js "
                                        'transpiler="render_static.transpilers.ClassURLWriter" '
                                        "include=include "
                                        "%}"
                                    )
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": {"urls.js": {"context": {"include": ["special"]}}},
        }
    )
    def test_named_unnamed_conflation1(self):
        """
        https://github.com/bckohan/django-render-static/issues/9
        """
        self.es6_mode = True
        self.url_js = None
        self.class_mode = ClassURLWriter.class_name_

        self.assertRaises(CommandError, lambda: call_command("renderstatic", "urls.js"))

        placeholders.register_variable_placeholder("choice", "first")
        placeholders.register_variable_placeholder("choice1", "second")
        self.assertRaises(CommandError, lambda: call_command("renderstatic", "urls.js"))
        placeholders.register_unnamed_placeholders("special", ["third"])

        call_command("renderstatic", "urls.js")
        self.compare("special", {"choice": "second"})
        self.compare("special", {"choice": "second", "choice1": "first"})
        self.compare("special", args=["third"])

    @override_settings(
        ROOT_URLCONF="tests.urls3",
        STATIC_TEMPLATES={
            "context": {"include": ["default"]},
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": (
                                        "{% urls_to_js "
                                        'transpiler="render_static.transpilers.ClassURLWriter" '
                                        "include=include "
                                        "%}"
                                    )
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": {"urls.js": {"context": {"include": ["special"]}}},
        },
    )
    def test_named_unnamed_conflation2(self):
        """
        https://github.com/bckohan/django-render-static/issues/9
        """
        self.es6_mode = True
        self.url_js = None
        self.class_mode = ClassURLWriter.class_name_

        self.assertRaises(CommandError, lambda: call_command("renderstatic", "urls.js"))

        placeholders.register_variable_placeholder("choice", "first")
        placeholders.register_variable_placeholder("choice1", "second")
        self.assertRaises(CommandError, lambda: call_command("renderstatic", "urls.js"))
        placeholders.register_unnamed_placeholders("special", ["third"])

        call_command("renderstatic", "urls.js")
        self.compare("special", {"choice": "second"})
        self.compare("special", {"choice": "second", "choice1": "first"})
        self.compare("special", args=["third"])

    @override_settings(
        ROOT_URLCONF="tests.urls4",
        STATIC_TEMPLATES={
            "context": {"include": ["default"]},
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": '{% urls_to_js transpiler="render_static.transpilers.ClassURLWriter" %}'
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
        },
    )
    def test_named_unnamed_conflation3(self):
        """
        This tests surfaces what appears to be a Django bug in reverse(). urls_to_js should not
        fail in this circumstance, but should leave a comment breadcrumb in the generated JS that
        indicates why no reversal was produced - alternatively if bug is fixed it should also pass

        https://github.com/bckohan/django-render-static/issues/9
        """
        self.es6_mode = True
        self.url_js = None
        self.class_mode = ClassURLWriter.class_name_

        placeholders.register_variable_placeholder("choice", "first")
        placeholders.register_unnamed_placeholders("special", ["first"])
        call_command("renderstatic", "urls.js")

        with open(GLOBAL_STATIC_DIR / "urls.js", "r") as urls:
            if "overruled" not in urls.read():
                self.compare("special", kwargs={"choice": "first"})  # pragma: no cover
                self.compare("special", args=["first"])  # pragma: no cover

        self.assertTrue(True)

    @override_settings(
        ROOT_URLCONF="tests.urls5",
        STATIC_TEMPLATES={
            "context": {"include": ["default"]},
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": '{% urls_to_js transpiler="render_static.transpilers.ClassURLWriter" %}'
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
        },
    )
    def test_nested_named_unnamed(self):
        """
        Nested unnamed/named parameters should work.

        https://github.com/bckohan/django-render-static/issues/93
        """
        self.es6_mode = True
        self.url_js = None
        self.class_mode = ClassURLWriter.class_name_

        # placeholders.register_unnamed_placeholders('nested_re_path_unnamed', ['page-', 22])
        placeholders.register_unnamed_placeholders("nested_re_path_named", 9)
        call_command("renderstatic", "urls.js")

        with open(GLOBAL_STATIC_DIR / "urls.js", "r") as urls:
            # self.compare('nested_re_path_unnamed', args=['page-22'])
            self.compare("nested_re_path_named", kwargs={"page_number": "22"})

        self.assertTrue(True)

    @override_settings(
        STATIC_TEMPLATES={
            "context": {"include": ["bad_mix"]},
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": "{% urls_to_js "
                                    'transpiler="render_static.transpilers.ClassURLWriter" '
                                    "include=include %}"
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
        }
    )
    def test_named_unnamed_bad_mix(self):
        """
        Mix of named and unnamed arguments should not be reversible!
        """
        self.es6_mode = True
        self.url_js = None
        self.class_mode = ClassURLWriter.class_name_

        placeholders.register_variable_placeholder("named", "1111")
        placeholders.register_unnamed_placeholders("bad_mix", ["unnamed"])
        call_command("renderstatic", "urls.js")

        with open(GLOBAL_STATIC_DIR / "urls.js", "r") as urls:
            self.assertTrue("this path may not be reversible" in urls.read())

        self.assertRaises(
            ValueError,
            lambda: reverse("bad_mix", kwargs={"named": "1111"}, args=["unnamed"]),
        )
        self.assertRaises(
            NoReverseMatch, lambda: reverse("bad_mix", kwargs={"named": "1111"})
        )

    @override_settings(
        STATIC_TEMPLATES={
            "context": {"include": ["bad_mix2"]},
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": "{% urls_to_js "
                                    'transpiler="render_static.transpilers.ClassURLWriter" '
                                    "include=include %}"
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
        }
    )
    def test_named_unnamed_bad_mix2(self):
        """
        Mix of named and unnamed arguments should not be reversible!
        """
        self.es6_mode = True
        self.url_js = None
        self.class_mode = ClassURLWriter.class_name_

        placeholders.register_variable_placeholder("named", "1111")
        placeholders.register_unnamed_placeholders("bad_mix2", ["unnamed"])
        self.assertRaises(CommandError, lambda: call_command("renderstatic", "urls.js"))

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": (
                                        "{% urls_to_js "
                                        'transpiler="render_static.transpilers.ClassURLWriter" '
                                        "include=include "
                                        "%}"
                                    )
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": {"urls.js": {"context": {"include": ["complex"]}}},
        }
    )
    def test_complexity_boundary(self):
        """
        https://github.com/bckohan/django-render-static/issues/10

        For URLs with lots of unregistered arguments, the reversal attempts may
        produce an explosion of complexity. Check that the failsafe is working.
        :return:
        """
        self.es6_mode = True
        self.class_mode = ClassURLWriter.class_name_
        self.url_js = None

        t1 = perf_counter()
        tb_str = ""
        try:
            call_command("renderstatic", "urls.js")
        except Exception as complexity_error:
            tb_str = traceback.format_exc()
            t2 = perf_counter()

        self.assertTrue("ReversalLimitHit" in tb_str)

        # very generous reversal timing threshold of 20 seconds - anecdotally
        # the default limit of 2**15 should be hit in about 3 seconds.
        self.assertTrue(t2 - t1 < 20)

        placeholders.register_variable_placeholder("one", "666")
        placeholders.register_variable_placeholder("two", "666")
        placeholders.register_variable_placeholder("three", "666")
        placeholders.register_variable_placeholder("four", "666")
        placeholders.register_variable_placeholder("five", "666")
        placeholders.register_variable_placeholder("six", "666")
        placeholders.register_variable_placeholder("seven", "666")
        placeholders.register_variable_placeholder("eight", "666")

        call_command("renderstatic", "urls.js")

        self.compare(
            "complex",
            {
                "one": 666,
                "two": 666,
                "three": 666,
                "four": 666,
                "five": 666,
                "six": 666,
                "seven": 666,
                "eight": 666,
            },
        )

    # uncomment to not delete generated js
    # def tearDown(self):
    #    pass


class URLSToJavascriptOffNominalTest(URLJavascriptMixin, BaseTestCase):
    def setUp(self):
        self.clear_placeholder_registries()

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": 'var urls = {\n{% urls_to_js transpiler="render_static.transpilers.SimpleURLWriter" include=include %}};'
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": {
                "urls.js": {
                    "context": {
                        "include": ["unreg_conv_tst"],
                    }
                }
            },
        }
    )
    def test_no_placeholders(self):
        self.es6_mode = True
        self.url_js = None

        # this works even though its registered against a different app
        # all placeholders that match at least one criteria are tried
        self.assertRaises(CommandError, lambda: call_command("renderstatic", "urls.js"))
        placeholders.register_variable_placeholder(
            "name", "does_not_match", app_name="app1"
        )
        self.assertRaises(CommandError, lambda: call_command("renderstatic", "urls.js"))
        placeholders.register_variable_placeholder("name", "name1", app_name="app1")
        placeholders.register_variable_placeholder("name", "name1", app_name="app1")
        call_command("renderstatic", "urls.js")
        self.compare("unreg_conv_tst", {"name": "name1"})

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": 'var urls = {\n{% urls_to_js transpiler="render_static.transpilers.SimpleURLWriter" include=include %}};'
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": {
                "urls.js": {
                    "context": {
                        "include": ["sub1:re_path_unnamed"],
                    }
                }
            },
        }
    )
    def test_no_unnamed_placeholders(self):
        self.assertRaises(CommandError, lambda: call_command("renderstatic", "urls.js"))
        placeholders.register_unnamed_placeholders(
            "re_path_unnamed", [143, "adf"]
        )  # shouldnt work
        placeholders.register_unnamed_placeholders(
            "re_path_unnamed", ["adf", 143]
        )  # but this will
        call_command("renderstatic", "urls.js")
        self.compare(
            "sub1:re_path_unnamed",
            args=["af", 5678],
            args_hook=lambda arr: self.convert_idx_to_type(arr, 1, int),
        )

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": 'var urls = {\n{% urls_to_js transpiler="render_static.transpilers.SimpleURLWriter" include=include %}};'
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": {
                "urls.js": {
                    "context": {
                        "include": ["sub1:re_path_unnamed"],
                    }
                }
            },
        }
    )
    def test_bad_only_bad_unnamed_placeholders(self):
        placeholders.register_unnamed_placeholders(
            "re_path_unnamed", []
        )  # shouldnt work
        self.assertRaises(CommandError, lambda: call_command("renderstatic", "urls.js"))

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": '{% urls_to_js transpiler="tests.js_tests.BadVisitor" %};'
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ]
        }
    )
    def test_bad_visitor_type(self):
        self.assertRaises(CommandError, lambda: call_command("renderstatic", "urls.js"))

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": 'var urls = {\n{% urls_to_js transpiler="render_static.transpilers.SimpleURLWriter" url_conf=url_mod %}};'
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": {
                "urls.js": {
                    "context": {
                        "url_mod": placeholders,
                    }
                }
            },
        }
    )
    def test_no_urlpatterns(self):
        self.assertRaises(CommandError, lambda: call_command("renderstatic", "urls.js"))

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": 'var urls = {\n{% urls_to_js transpiler="render_static.transpilers.SimpleURLWriter" url_conf=url_mod %}};'
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": {
                "urls.js": {
                    "context": {
                        "url_mod": bad_pattern,
                    }
                }
            },
        }
    )
    def test_unknown_pattern(self):
        self.assertRaises(CommandError, lambda: call_command("renderstatic", "urls.js"))

    def test_register_bogus_converter(self):
        self.assertRaises(
            ValueError,
            lambda: placeholders.register_converter_placeholder(
                "Not a converter type!", 1234
            ),
        )

    # uncomment to not delete generated js
    # def tearDown(self):
    #    pass


class URLSToJavascriptParametersTest(URLJavascriptMixin, BaseTestCase):
    def setUp(self):
        self.clear_placeholder_registries()
        placeholders.register_unnamed_placeholders("re_path_unnamed", ["adf", 143])

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": "{% urls_to_js "
                                    "raise_on_not_found=False "
                                    "indent=None "
                                    "include=include "
                                    "%}",
                                    "urls2.js": "{% urls_to_js "
                                    "raise_on_not_found=True "
                                    'indent="" '
                                    "include=include "
                                    "%}",
                                    "urls3.js": "var urls = {\n{% urls_to_js "
                                    'transpiler="render_static.transpilers.SimpleURLWriter" '
                                    "raise_on_not_found=False "
                                    "indent=None "
                                    "include=include "
                                    "%}}\n",
                                    "urls4.js": "var urls = {\n{% urls_to_js "
                                    'transpiler="render_static.transpilers.SimpleURLWriter" '
                                    "raise_on_not_found=True "
                                    'indent="" '
                                    "include=include "
                                    "%}};\n",
                                    "urls3_export.mjs": "{% urls_to_js "
                                    "raise_on_not_found=False "
                                    'indent="\t" '
                                    "include=include "
                                    "export=True "
                                    "%}\n",
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": {
                "urls.js": {"context": {"include": ["path_tst", "re_path_unnamed"]}},
                "urls2.js": {"context": {"include": ["path_tst", "re_path_unnamed"]}},
                "urls3.js": {"context": {"include": ["path_tst", "re_path_unnamed"]}},
                "urls4.js": {"context": {"include": ["path_tst", "re_path_unnamed"]}},
                "urls3_export.mjs": {
                    "context": {"include": ["path_tst", "re_path_unnamed"]}
                },
            },
        }
    )
    def test_class_parameters_es6(self):
        self.es6_mode = True
        self.class_mode = ClassURLWriter.class_name_
        call_command("renderstatic")
        js_ret = self.get_url_from_js(
            "doest_not_exist",
            js_generator=URLJavascriptMixin.TestJSGenerator(
                class_mode=self.class_mode, catch=False
            ),
        )
        self.assertFalse("TypeError" in js_ret)
        self.compare("path_tst")
        self.compare("path_tst", {"arg1": 1})
        self.compare("path_tst", {"arg1": 12, "arg2": "xo"})

        up2 = GLOBAL_STATIC_DIR / "urls2.js"
        js_ret2 = self.get_url_from_js(
            "doest_not_exist",
            url_path=up2,
            js_generator=URLJavascriptMixin.TestJSGenerator(
                class_mode=self.class_mode, catch=False
            ),
        )
        self.assertTrue("TypeError" in js_ret2)

        js_ret2_1 = self.get_url_from_js(
            "path_tst",
            kwargs={"arg1": 12, "arg2": "xo", "invalid": 0},
            url_path=up2,
            js_generator=URLJavascriptMixin.TestJSGenerator(
                class_mode=self.class_mode, catch=False
            ),
        )
        self.assertTrue("TypeError" in js_ret2_1)
        self.compare("path_tst", url_path=up2)
        self.compare("path_tst", {"arg1": 1}, url_path=up2)
        self.compare("path_tst", {"arg1": 12, "arg2": "xo"}, url_path=up2)

        self.class_mode = None

        up3 = GLOBAL_STATIC_DIR / "urls3.js"
        js_ret3 = self.get_url_from_js(
            "path_tst",
            kwargs={"arg1": 12, "arg2": "xo", "invalid": 0},
            url_path=up3,
            js_generator=URLJavascriptMixin.TestJSGenerator(catch=False),
        )
        self.assertFalse("TypeError" in js_ret3)
        self.compare("path_tst", url_path=up3)
        self.compare("path_tst", {"arg1": 1}, url_path=up3)
        self.compare("path_tst", {"arg1": 12, "arg2": "xo"}, url_path=up3)

        up4 = GLOBAL_STATIC_DIR / "urls4.js"
        js_ret4 = self.get_url_from_js(
            "path_tst",
            kwargs={"arg1": 12, "arg2": "xo", "invalid": 0},
            url_path=up4,
            js_generator=URLJavascriptMixin.TestJSGenerator(catch=False),
        )
        self.assertTrue("TypeError" in js_ret4)
        self.compare("path_tst", url_path=up4)
        self.compare("path_tst", {"arg1": 1}, url_path=up4)
        self.compare("path_tst", {"arg1": 12, "arg2": "xo"}, url_path=up4)

        up3_exprt = GLOBAL_STATIC_DIR / "urls3_export.mjs"
        generator = URLJavascriptMixin.TestJSGenerator(
            class_mode=ClassURLWriter.class_name_, catch=False, module=True
        )
        js_ret3_exprt = self.get_url_from_js(
            "path_tst",
            kwargs={"arg1": 12, "arg2": "xo"},
            url_path=up3_exprt,
            js_generator=generator,
        )
        self.assertFalse("TypeError" in js_ret3_exprt)
        generator.rendered_ = ""
        self.compare("path_tst", js_generator=generator, url_path=up3_exprt)
        generator.rendered_ = ""
        self.compare(
            "path_tst", {"arg1": 1}, js_generator=generator, url_path=up3_exprt
        )
        generator.rendered_ = ""
        self.compare(
            "path_tst",
            {"arg1": 12, "arg2": "xo"},
            js_generator=generator,
            url_path=up3_exprt,
        )

    # uncomment to not delete generated js
    def tearDown(self):
        pass


@override_settings(
    ROOT_URLCONF="tests.js_reverse_urls",
    STATIC_TEMPLATES={
        "ENGINES": [
            {
                "BACKEND": "render_static.backends.StaticDjangoTemplates",
                "OPTIONS": {
                    "loaders": [
                        (
                            "render_static.loaders.StaticLocMemLoader",
                            {
                                "urls.js": "{% urls_to_js "
                                'transpiler="render_static.transpilers.ClassURLWriter" '
                                'exclude="exclude_namespace"|split '
                                "%};"
                            },
                        )
                    ],
                    "builtins": ["render_static.templatetags.render_static"],
                },
            }
        ]
    },
)
class DjangoJSReverseTest(URLJavascriptMixin, BaseTestCase):
    """
    Run additional tests pilfered from django-js-reverse for the hell of it.
    https://github.com/ierror/django-js-reverse/blob/master/django_js_reverse/tests/test_urls.py
    """

    def setUp(self):
        self.clear_placeholder_registries()

    def test_js_reverse_urls(self):
        self.url_js = None
        self.class_mode = ClassURLWriter.class_name_

        call_command("renderstatic", "urls.js")

    # uncomment to not delete generated js
    # def tearDown(self):
    #    pass


@override_settings(
    ROOT_URLCONF="tests.urls_precedence",
    STATIC_TEMPLATES={
        "ENGINES": [
            {
                "BACKEND": "render_static.backends.StaticDjangoTemplates",
                "OPTIONS": {
                    "loaders": [
                        (
                            "render_static.loaders.StaticLocMemLoader",
                            {
                                "urls.js": "{% urls_to_js "
                                'transpiler="render_static.transpilers.ClassURLWriter" '
                                'exclude="exclude_namespace"|split '
                                "%};"
                            },
                        )
                    ],
                    "builtins": ["render_static.templatetags.render_static"],
                },
            }
        ]
    },
)
class DjangoJSReversePrecedenceTest(URLJavascriptMixin, BaseTestCase):
    """
    Run additional tests pilfered from django-js-reverse for the hell of it.
    https://github.com/ierror/django-js-reverse/blob/master/django_js_reverse/tests/test_urls.py
    """

    def setUp(self):
        self.clear_placeholder_registries()

    def test_js_reverse_urls(self):
        self.url_js = None
        self.class_mode = ClassURLWriter.class_name_
        call_command("renderstatic", "urls.js")
        from django.urls import reverse

        for kwargs in [{}, {"kwarg1": "order_test"}]:
            self.assertEqual(
                reverse("order", kwargs=kwargs), self.get_url_from_js("order", kwargs)
            )

    # uncomment to not delete generated js
    # def tearDown(self):
    #    pass


@override_settings(
    ROOT_URLCONF="tests.urls_bug_65",
    STATIC_TEMPLATES={
        "ENGINES": [
            {
                "BACKEND": "render_static.backends.StaticDjangoTemplates",
                "OPTIONS": {
                    "loaders": [
                        (
                            "render_static.loaders.StaticLocMemLoader",
                            {
                                "urls.js": (
                                    "{% urls_to_js "
                                    'transpiler="render_static.transpilers.ClassURLWriter" %}'
                                )
                            },
                        )
                    ],
                    "builtins": ["render_static.templatetags.render_static"],
                },
            }
        ],
        "templates": {"urls.js": {"context": {}}},
    },
)
class URLBugsTestCases(URLJavascriptMixin, BaseTestCase):
    def setUp(self):
        self.clear_placeholder_registries()

    def test_bug_65_compiles(self):
        """
        Tests: https://github.com/bckohan/django-render-static/issues/65
        Just test that urls_to_js spits out code that compiles now.
        This issue will be further addressed by
        https://github.com/bckohan/django-render-static/issues/66

        This behavior changed from Django 4.0 -> 4.1:

        <4.0 behavior:

        {}: /prefix2
        {'kwarg_param': '2'}: /prefix
        {'kwarg_param': 4}: /prefix2
        {'url_param': 1, 'kwarg_param': '1'}: /prefix/1/postfix/value1
        {'url_param': 4, 'kwarg_param': 4}: /re_path/4/
        {'url_param': 2, 'kwarg_param': '2'}: /prefix/2/postfix/value2
        {'url_param': 4, 'kwarg_param': 1}: /prefix_int/4/postfix_int/1

        >= 4.1 behavior:

        {}: /prefix2
        {'kwarg_param': '2'}: /prefix
        {'kwarg_param': 4}: /prefix2
        {'url_param': 1, 'kwarg_param': '1'}: /prefix_int/1/postfix_int/1
        {'url_param': 4, 'kwarg_param': 4}: /re_path/4/
        {'url_param': 2, 'kwarg_param': '2'}: /prefix_int/2/postfix_int/2
        {'url_param': 4, 'kwarg_param': 1}: /prefix_int/4/postfix_int/1
        """
        self.es6_mode = True
        self.url_js = None
        self.class_mode = ClassURLWriter.class_name_

        call_command("renderstatic", "urls.js")

        dj_gt41 = DJANGO_VERSION[0:2] >= (4, 1)

        from django.urls import reverse

        for kwargs in [
            {},
            {"kwarg_param": "2"},
            {"kwarg_param": 4},
            {"url_param": 1, "kwarg_param": "1"},
            {"url_param": 4, "kwarg_param": 4},
            {"url_param": 2, "kwarg_param": "2"},
            {"url_param": 4, "kwarg_param": 1},
        ] + ([{"url_param": 4}] if dj_gt41 else []):
            self.assertEqual(
                reverse("bug65", kwargs=kwargs), self.get_url_from_js("bug65", kwargs)
            )

        self.assertEqual(
            reverse("bug65", args=[10]), self.get_url_from_js("bug65", args=[10])
        )

        bad = {"url_param": 4, "kwarg_param": 5}
        if dj_gt41:  # pragma: no cover
            self.assertEqual(
                reverse("bug65", kwargs=bad), self.get_url_from_js("bug65", bad)
            )
        else:  # pragma: no cover
            self.assertRaises(NoReverseMatch, lambda: reverse("bug65", kwargs=bad))
            self.assertEqual(self.get_url_from_js("bug65", bad), "")

    # def tearDown(self):
    #     pass

    @override_settings(
        INSTALLED_APPS=[
            "tests.chain",
            "tests.spa",
            "render_static",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.sites",
            "django.contrib.messages",
            "django.contrib.staticfiles",
            "django.contrib.admin",
        ],
        ROOT_URLCONF="tests.urls_bug_13",
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "urls.js": (
                                        "{% urls_to_js "
                                        'transpiler="render_static.transpilers.ClassURLWriter" %}'
                                    )
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": {"urls.js": {"context": {}}},
        },
    )
    def test_bug_13_multilevel_args(self):
        """
        Tests: https://github.com/bckohan/django-render-static/issues/13
        Tests that nested url inclusions with arguments on the stems work.
        """
        self.es6_mode = True
        self.url_js = None
        self.class_mode = ClassURLWriter.class_name_

        call_command("renderstatic", "urls.js")
        for name, kwargs in [
            ("spa1:qry", {"toparg": 1, "arg": 3}),
            ("spa1:qry", {"toparg": 2}),
            ("spa2:qry", {"arg": 2}),
            ("spa2:qry", {}),
            ("chain:spa:qry", {"top": "a5", "chain": "slug"}),
            ("chain:spa:qry", {"top": "a5", "chain": "str", "arg": 100}),
            ("chain:spa:index", {"top": "a5", "chain": "str"}),
            ("chain_re:spa_re:qry", {"top": "a5", "chain": "slug"}),
            ("chain_re:spa_re:qry", {"top": "a5", "chain": "str", "arg": 100}),
            ("chain_re:spa_re:index", {"top": "a5", "chain": "str"}),
            ("noslash:spa:qry", {"top": "a5", "chain": "slug"}),
            ("noslash:spa:qry", {"top": "a5", "chain": "str", "arg": 100}),
            ("noslash:spa:index", {"top": "a5", "chain": "str"}),
        ]:
            self.assertEqual(
                reverse(name, kwargs=kwargs), self.get_url_from_js(name, kwargs)
            )

    # def tearDown(self):
    #     pass


@override_settings(
    INSTALLED_APPS=[
        "tests.spa",
        "render_static",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.sites",
        "django.contrib.messages",
        "django.contrib.staticfiles",
        "django.contrib.admin",
    ],
    ROOT_URLCONF="tests.spa_urls",
    STATICFILES_DIRS=[
        ("spa", GLOBAL_STATIC_DIR),
    ],
    STATIC_TEMPLATES={
        "templates": {
            "spa/urls.js": {
                "context": {"include": ["spa1", "spa2"]},
                "dest": str(GLOBAL_STATIC_DIR / "urls.js"),
            }
        }
    },
)
class TestDefaultNamespaces(URLJavascriptMixin, BaseTestCase):
    """
    todo - could use a multi-level test when that bug is fixed.
    """

    def do_test(self):
        call_command("renderstatic", "spa/urls.js")

        self.assertEqual(reverse("spa1:index"), self.get_url_from_js("spa1:index"))
        self.assertEqual(
            reverse("spa1:index"), self.get_url_from_js("spa1:index", default_ns="spa1")
        )
        self.assertEqual(
            reverse("spa1:index"),
            self.get_url_from_js("spa1:index", default_ns="spa1:"),
        )
        self.assertEqual(
            reverse("spa1:index"), self.get_url_from_js("index", default_ns="spa1")
        )
        self.assertEqual(
            reverse("spa1:index"), self.get_url_from_js("index", default_ns="spa1:")
        )

        self.assertEqual(reverse("spa2:index"), self.get_url_from_js("spa2:index"))
        self.assertEqual(
            reverse("spa2:index"), self.get_url_from_js("spa2:index", default_ns="spa2")
        )
        self.assertEqual(
            reverse("spa2:index"), self.get_url_from_js("index", default_ns="spa2")
        )

    def test_es6_default_namespace(self):
        self.es6_mode = True
        self.url_js = None
        self.class_mode = ClassURLWriter.class_name_
        self.do_test()

    # def tearDown(self):
    #    pass


class EnumComparator:
    def enums_compare(
        self,
        js_file,
        enum_classes,
        class_properties=True,
        properties=True,
        to_string=True,
    ):
        for enum in enum_classes:
            self.enum_compare(
                js_file,
                enum,
                class_properties=class_properties,
                properties=properties,
                to_string=to_string,
            )

    def enum_compare(
        self, js_file, cls, class_properties=True, properties=True, to_string=True
    ):
        """
        Given a javascript file and a list of classes, evaluate the javascript
        code into a python dictionary and determine if that dictionary matches
        the upper case parameters on the defines class.
        """

        with open(js_file, "r") as js:
            js_dict = self.get_js_structure(js_file)

            class_properties = (
                [
                    name
                    for name, member in vars(cls).items()
                    if isinstance(member, classproperty)
                ]
                if class_properties is True
                else (
                    [prop for prop in class_properties if hasattr(cls, prop)]
                    if class_properties
                    else []
                )
            )

            properties = (
                [
                    name
                    for name, member in vars(cls).items()
                    if isinstance(member, property)
                ]
                if properties is True
                else (
                    [prop for prop in properties if hasattr(cls, prop)]
                    if properties
                    else []
                )
            )
            for param in ["value"]:  # pragma: no cover
                if param not in properties:
                    properties.insert(0, param)

            def to_js_test(value):
                if isinstance(value, date):
                    return value.isoformat()
                if isinstance(value, Enum):
                    return value.value  # pragma: no cover
                return value

            enum_dict = {
                **(
                    {
                        "strings": {
                            en.value.isoformat()
                            if isinstance(en.value, date)
                            else str(en.value): (
                                str(getattr(en, to_string))
                                if isinstance(to_string, str)
                                else str(en)
                            )
                            for en in cls
                        }
                    }
                    if to_string
                    else {}
                ),
                **{
                    prop: [to_js_test(getattr(en, prop)) for en in cls]
                    for prop in properties
                },
                "getCheck": 1,
            }

            if class_properties:
                enum_dict["class_props"] = {
                    prop: getattr(cls, prop) for prop in class_properties
                }

            from pprint import pprint

            pprint(enum_dict)
            pprint(js_dict[cls.__name__])
            self.assertEqual(
                DeepDiff(
                    enum_dict,
                    js_dict[cls.__name__],
                    # treat tuples and lists the same
                    ignore_type_in_groups=[(tuple, list)],
                ),
                {},
            )

    def get_js_structure(self, js_file):  # pragma: no cover
        json_structure = run_js_file(js_file)
        if json_structure:
            return json.loads(json_structure)
        return None


@override_settings(
    INSTALLED_APPS=[
        "tests.enum_app",
        "render_static",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.sites",
        "django.contrib.messages",
        "django.contrib.staticfiles",
        "django.contrib.admin",
    ],
    ROOT_URLCONF="tests.enum_app.urls",
    STATIC_TEMPLATES={
        "context": {
            "include_properties": True,
            "class_properties": True,
            "properties": True,
            "symmetric_properties": False,
        },
        "templates": [
            (
                "enum_app/test.js",
                {
                    "context": {
                        "enums": [
                            EnumTester.MapBoxStyle,
                            EnumTester.AddressRoute,
                            EnumTester.Color,
                        ]
                    },
                    "dest": GLOBAL_STATIC_DIR / "enum/enums.js",
                },
            ),
            (
                "enum_app/test.js",
                {
                    "context": {"enums": "tests.enum_app.defines.Def"},
                    "dest": GLOBAL_STATIC_DIR / "enum/def.js",
                },
            ),
        ],
    },
)
class EnumGeneratorTest(EnumComparator, BaseTestCase):
    def test_simple(self):
        from tests.enum_app.defines import Def

        call_command("renderstatic", "enum_app/test.js")
        self.enums_compare(
            js_file=GLOBAL_STATIC_DIR / "enum/def.js", enum_classes=[Def]
        )

    def test_enum_properties(self):
        call_command("renderstatic", "enum_app/test.js")
        self.enums_compare(
            js_file=GLOBAL_STATIC_DIR / "enum/enums.js",
            enum_classes=[
                EnumTester.MapBoxStyle,
                EnumTester.AddressRoute,
                EnumTester.Color,
            ],
        )

    @override_settings(
        ROOT_URLCONF="tests.enum_app.urls",
        STATIC_TEMPLATES={
            "context": {
                "include_properties": True,
                "class_properties": True,
                "properties": True,
                "symmetric_properties": False,
            },
            "templates": [
                (
                    "enum_app/test.js",
                    {
                        "context": {
                            "enums": "tests.enum_app.models.EnumTester",
                            "test_enums": [
                                EnumTester.MapBoxStyle,
                                EnumTester.AddressRoute,
                                EnumTester.Color,
                            ],
                        },
                        "dest": GLOBAL_STATIC_DIR / "enum/enums.js",
                    },
                )
            ],
        },
    )
    def test_model_import_string(self):
        call_command("renderstatic", "enum_app/test.js")
        self.enums_compare(
            js_file=GLOBAL_STATIC_DIR / "enum/enums.js",
            enum_classes=[
                EnumTester.MapBoxStyle,
                EnumTester.AddressRoute,
                EnumTester.Color,
            ],
        )

    @override_settings(
        STATIC_TEMPLATES={
            "context": {
                "include_properties": True,
                "class_properties": False,
                "properties": True,
                "symmetric_properties": False,
            },
            "templates": [
                (
                    "enum_app/test.js",
                    {"context": {"enums": ["tests.enum_app.defines.TimeEnum"]}},
                )
            ],
        }
    )
    def test_datetime_enum(self):
        call_command("renderstatic", "enum_app/test.js")
        from tests.enum_app.defines import TimeEnum

        self.enums_compare(
            js_file=ENUM_STATIC_DIR / "enum_app/test.js",
            enum_classes=[TimeEnum],
            class_properties=False,
        )

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "enum_app/test.js": '{% enums_to_js enums=enums to_javascript="render_static.transpilers.to_js_datetime" %}\n'
                                    "console.log(TimeEnum.YEAR1.value.toISOString());\n"
                                    "console.log(TimeEnum.YEAR2.with_time.toISOString());\n"
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": [
                (
                    "enum_app/test.js",
                    {"context": {"enums": ["tests.enum_app.defines.TimeEnum"]}},
                ),
            ],
        }
    )
    def test_datetime_enum_to_javascript_param(self):
        call_command("renderstatic", "enum_app/test.js")
        from dateutil.parser import parse

        from tests.enum_app.defines import TimeEnum

        times = run_js_file(GLOBAL_STATIC_DIR / "enum_app/test.js").split()
        self.assertEqual(parse(times[0]).date(), TimeEnum.YEAR1.value)
        self.assertEqual(parse(times[1]), TimeEnum.YEAR2.with_time)

    @override_settings(
        STATIC_TEMPLATES={
            "context": {
                "include_properties": True,
                "class_properties": False,
                "properties": True,
                "symmetric_properties": False,
            },
            "templates": [
                ("enum_app/test.js", {"context": {"enums": EnumTester.MapBoxStyle}}),
            ],
        }
    )
    def test_class_prop_option(self):
        call_command("renderstatic", "enum_app/test.js")
        self.enums_compare(
            js_file=ENUM_STATIC_DIR / "enum_app/test.js",
            enum_classes=[EnumTester.MapBoxStyle],
            class_properties=False,
        )
        self.assertNotIn(
            "class_name", get_content(ENUM_STATIC_DIR / "enum_app/test.js")
        )

    @override_settings(
        STATIC_TEMPLATES={
            "context": {
                "include_properties": True,
                "class_properties": False,
                "properties": True,
                "symmetric_properties": False,
                "to_string": False,
            },
            "templates": [
                ("enum_app/test.js", {"context": {"enums": EnumTester.MapBoxStyle}}),
            ],
        }
    )
    def test_disable_to_string(self):
        call_command("renderstatic", "enum_app/test.js")
        self.enums_compare(
            js_file=ENUM_STATIC_DIR / "enum_app/test.js",
            enum_classes=[EnumTester.MapBoxStyle],
            class_properties=False,
            to_string=False,
        )
        self.assertNotIn(
            "class_name", get_content(ENUM_STATIC_DIR / "enum_app/test.js")
        )
        self.assertNotIn("toString", get_content(ENUM_STATIC_DIR / "enum_app/test.js"))
        self.assertNotIn("this.str", get_content(ENUM_STATIC_DIR / "enum_app/test.js"))
        self.assertNotIn(", str) {", get_content(ENUM_STATIC_DIR / "enum_app/test.js"))
        self.assertNotIn(', "1");', get_content(ENUM_STATIC_DIR / "enum_app/test.js"))

    @override_settings(
        STATIC_TEMPLATES={
            "context": {
                "include_properties": True,
                "class_properties": False,
                "properties": True,
                "symmetric_properties": False,
                "to_string": "uri",
            },
            "templates": [
                ("enum_app/test.js", {"context": {"enums": EnumTester.MapBoxStyle}}),
            ],
        }
    )
    def test_to_string_is_prop(self):
        call_command("renderstatic", "enum_app/test.js")
        self.enums_compare(
            js_file=ENUM_STATIC_DIR / "enum_app/test.js",
            enum_classes=[EnumTester.MapBoxStyle],
            class_properties=False,
            to_string="uri",
        )
        self.assertNotIn(
            "class_name", get_content(ENUM_STATIC_DIR / "enum_app/test.js")
        )
        self.assertIn("toString", get_content(ENUM_STATIC_DIR / "enum_app/test.js"))
        self.assertIn("this.uri", get_content(ENUM_STATIC_DIR / "enum_app/test.js"))
        self.assertNotIn(", str) {", get_content(ENUM_STATIC_DIR / "enum_app/test.js"))
        self.assertNotIn(', "1");', get_content(ENUM_STATIC_DIR / "enum_app/test.js"))

    @override_settings(
        STATIC_TEMPLATES={
            "context": {
                "include_properties": True,
                "class_properties": ["docs"],
                "properties": True,
                "symmetric_properties": False,
            },
            "templates": [
                (
                    "enum_app/test.js",
                    {"context": {"enums": [EnumTester.MapBoxStyle, EnumTester.Color]}},
                ),
            ],
        }
    )
    def test_class_props_specified(self):
        call_command("renderstatic", "enum_app/test.js")
        self.enums_compare(
            js_file=ENUM_STATIC_DIR / "enum_app/test.js",
            enum_classes=[EnumTester.MapBoxStyle, EnumTester.Color],
            class_properties=["docs"],
        )
        contents = get_content(ENUM_STATIC_DIR / "enum_app/test.js")
        self.assertNotIn("class_name", contents)
        self.assertEqual(contents.count("static docs ="), 1)

    @override_settings(
        STATIC_TEMPLATES={
            "context": {
                "include_properties": False,
                "properties": False,
                "symmetric_properties": False,
            },
            "templates": [
                ("enum_app/test.js", {"context": {"enums": [EnumTester.MapBoxStyle]}}),
            ],
        }
    )
    def test_exclude_props(self):
        call_command("renderstatic", "enum_app/test.js")
        self.enums_compare(
            js_file=ENUM_STATIC_DIR / "enum_app/test.js",
            enum_classes=[EnumTester.MapBoxStyle],
            class_properties=False,
            properties=False,
        )
        contents = get_content(ENUM_STATIC_DIR / "enum_app/test.js")
        self.assertNotIn("slug", contents)
        self.assertNotIn("label", contents)
        self.assertNotIn("version", contents)
        self.assertIn("this.value = ", contents)
        self.assertIn("this.name = ", contents)

    @override_settings(
        STATIC_TEMPLATES={
            "context": {
                "include_properties": True,
                "exclude_properties": ["uri", "version", "name"],
                "properties": True,
                "test_properties": ["slug", "label", "value"],
                "symmetric_properties": False,
            },
            "templates": [
                ("enum_app/test.js", {"context": {"enums": [EnumTester.MapBoxStyle]}}),
            ],
        }
    )
    def test_exclude_props_param(self):
        call_command("renderstatic", "enum_app/test.js")
        self.enums_compare(
            js_file=ENUM_STATIC_DIR / "enum_app/test.js",
            enum_classes=[EnumTester.MapBoxStyle],
            class_properties=False,
            properties=["slug", "label", "value"],
        )
        contents = get_content(ENUM_STATIC_DIR / "enum_app/test.js")
        self.assertNotIn("uri", contents)
        self.assertNotIn("version", contents)
        self.assertNotIn("name", contents)
        self.assertIn("this.value = ", contents)
        self.assertIn("this.slug = ", contents)
        self.assertIn("this.label = ", contents)

    @override_settings(
        STATIC_TEMPLATES={
            "context": {
                "include_properties": ["slug", "label"],
                "properties": True,
                "test_properties": ["slug", "label", "value"],
                "symmetric_properties": False,
            },
            "templates": [
                ("enum_app/test.js", {"context": {"enums": [EnumTester.MapBoxStyle]}}),
            ],
        }
    )
    def test_include_props_list(self):
        call_command("renderstatic", "enum_app/test.js")
        self.enums_compare(
            js_file=ENUM_STATIC_DIR / "enum_app/test.js",
            enum_classes=[EnumTester.MapBoxStyle],
            class_properties=False,
            properties=["slug", "label", "value"],
        )
        contents = get_content(ENUM_STATIC_DIR / "enum_app/test.js")
        self.assertNotIn("uri", contents)
        self.assertNotIn("version", contents)
        self.assertNotIn("name", contents)
        self.assertIn("this.value = ", contents)
        self.assertIn("this.slug = ", contents)
        self.assertIn("this.label = ", contents)

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "enum_app/test.js": "{% enums_to_js enums=enums class_name=class_name export=True %}"
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": [
                (
                    "enum_app/test.js",
                    {
                        "context": {
                            "enums": [EnumTester.MapBoxStyle],
                            "class_name": "{}Enum",
                        }
                    },
                ),
            ],
        }
    )
    def test_export_on_and_classname(self):
        call_command("renderstatic", "enum_app/test.js")
        contents = get_content(GLOBAL_STATIC_DIR / "enum_app/test.js")
        self.assertIn("export class MapBoxStyleEnum {", contents)

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "enum_app/test.js": "{% enums_to_js enums=enums class_name=class_name export=False %}\n"
                                    "{% enum_tests enums=enums|enum_list name_map=name_map %}"
                                },
                            )
                        ],
                        "builtins": [
                            "render_static.templatetags.render_static",
                            "tests.enum_app.templatetags.enum_test",
                        ],
                    },
                }
            ],
            "templates": [
                (
                    "enum_app/test.js",
                    {
                        "context": {
                            "enums": [EnumTester.MapBoxStyle],
                            "class_name": "Enum{}",
                            "name_map": {EnumTester.MapBoxStyle: "EnumMapBoxStyle"},
                        }
                    },
                ),
            ],
        }
    )
    def test_export_off_and_classname(self):
        call_command("renderstatic", "enum_app/test.js")
        contents = get_content(GLOBAL_STATIC_DIR / "enum_app/test.js")
        self.assertNotIn("export class EnumMapBoxStyle {", contents)
        self.assertIn("class EnumMapBoxStyle {", contents)
        self.enums_compare(
            js_file=GLOBAL_STATIC_DIR / "enum_app/test.js",
            enum_classes=[EnumTester.MapBoxStyle],
            class_properties=True,
            properties=True,
        )

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "enum_app/test.js": "{% enums_to_js enums=enums class_name=class_name export=False %}\n"
                                    "{% enum_tests enums=enums|enum_list name_map=name_map %}"
                                },
                            )
                        ],
                        "builtins": [
                            "render_static.templatetags.render_static",
                            "tests.enum_app.templatetags.enum_test",
                        ],
                    },
                }
            ],
            "templates": [
                (
                    "enum_app/test.js",
                    {
                        "context": {
                            "enums": [EnumTester.MapBoxStyle],
                            "class_name": "Enum{}",
                            "name_map": {EnumTester.MapBoxStyle: "EnumMapBoxStyle"},
                        }
                    },
                ),
            ],
        }
    )
    def test_default_export_and_classname(self):
        self.test_export_off_and_classname.__wrapped__(self)

    @override_settings(
        STATIC_TEMPLATES={
            "context": {
                "include_properties": True,
                "properties": True,
                "symmetric_properties": ["name", "slug", "label"],
                "test_symmetric_properties": ["name", "slug", "label"],
            },
            "templates": [
                ("enum_app/test.js", {"context": {"enums": [EnumTester.MapBoxStyle]}}),
            ],
        }
    )
    def test_symmetric_props(self):
        call_command("renderstatic", "enum_app/test.js")
        self.enums_compare(
            js_file=ENUM_STATIC_DIR / "enum_app/test.js",
            enum_classes=[EnumTester.MapBoxStyle],
            class_properties=False,
            properties=True,
        )
        content = get_content(ENUM_STATIC_DIR / "enum_app/test.js")
        self.assertIn('=== MapBoxStyle.get("SATELLITE_STREETS");', content)
        self.assertIn('=== MapBoxStyle.get("Satellite Streets");', content)
        self.assertIn('=== MapBoxStyle.get("satellite-streets");', content)
        self.assertIn("=== MapBoxStyle.get(6);", content)
        self.assertEqual(content.count("for (const en of this)"), 4)

    @override_settings(
        STATIC_TEMPLATES={
            "context": {
                "include_properties": True,
                "properties": True,
                "symmetric_properties": True,
                "isymmetric_properties": [],
                "test_symmetric_properties": ["name", "slug", "uri", "label"],
            },
            "templates": [
                ("enum_app/test.js", {"context": {"enums": [EnumTester.MapBoxStyle]}}),
            ],
        }
    )
    def test_resolve_symmetric_props(self):
        call_command("renderstatic", "enum_app/test.js")
        self.enums_compare(
            js_file=ENUM_STATIC_DIR / "enum_app/test.js",
            enum_classes=[EnumTester.MapBoxStyle],
            class_properties=False,
            properties=True,
        )
        content = get_content(ENUM_STATIC_DIR / "enum_app/test.js")
        self.assertIn('=== MapBoxStyle.get("SATELLITE_STREETS");', content)
        self.assertIn('=== MapBoxStyle.get("Satellite Streets");', content)
        self.assertIn('=== MapBoxStyle.get("satellite-streets");', content)
        self.assertIn(
            '=== MapBoxStyle.get("mapbox://styles/mapbox/satellite-streets-v11");',
            content,
        )
        self.assertIn("=== MapBoxStyle.get(6);", content)
        self.assertEqual(content.count("for (const en of this)"), 5)
        self.assertNotIn("ciCompare", content)

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "enum_app/test.js": '{% enums_to_js enums=enums symmetric_properties=True on_unrecognized="RETURN_NULL" %}\n'
                                    "console.log(JSON.stringify({"
                                    'StReEtS: MapBoxStyle.get("StReEtS").label,'
                                    f'"{EnumTester.MapBoxStyle.NAVIGATION_DAY.uri.upper()}": MapBoxStyle.get("{EnumTester.MapBoxStyle.NAVIGATION_DAY.uri.upper()}")'
                                    "}));"
                                },
                            ),
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "enum_app/test2.js": '{% enums_to_js enums=enums symmetric_properties=True isymmetric_properties="uri"|split on_unrecognized="RETURN_NULL" %}\n'
                                    "console.log(JSON.stringify({"
                                    'StReEtS: MapBoxStyle.get("StReEtS"),'
                                    f'"{EnumTester.MapBoxStyle.NAVIGATION_DAY.uri.upper()}": MapBoxStyle.get("{EnumTester.MapBoxStyle.NAVIGATION_DAY.uri.upper()}").label'
                                    "}));"
                                },
                            ),
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": [
                ("enum_app/test.js", {"context": {"enums": [EnumTester.MapBoxStyle]}}),
                ("enum_app/test2.js", {"context": {"enums": [EnumTester.MapBoxStyle]}}),
            ],
        }
    )
    def test_resolve_isymmetric_props(self):
        call_command("renderstatic", ["enum_app/test.js", "enum_app/test2.js"])
        content = get_content(GLOBAL_STATIC_DIR / "enum_app/test.js")
        self.assertIn("static ciCompare", content)
        js_dict = self.get_js_structure(GLOBAL_STATIC_DIR / "enum_app/test.js")
        self.assertEqual(js_dict["StReEtS"], "Streets")
        self.assertEqual(
            js_dict[EnumTester.MapBoxStyle.NAVIGATION_DAY.uri.upper()], None
        )

        content = get_content(GLOBAL_STATIC_DIR / "enum_app/test2.js")
        self.assertIn("static ciCompare", content)
        js_dict = self.get_js_structure(GLOBAL_STATIC_DIR / "enum_app/test2.js")
        self.assertEqual(js_dict["StReEtS"], None)
        self.assertEqual(
            js_dict[EnumTester.MapBoxStyle.NAVIGATION_DAY.uri.upper()],
            EnumTester.MapBoxStyle.NAVIGATION_DAY.label,
        )

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "enum_app/test.js": '{% enums_to_js enums=enums symmetric_properties=True on_unrecognized="RETURN_NULL" %}\n'
                                    'console.log(JSON.stringify({not_found: AddressRoute.get("Aly")}));'
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": [
                ("enum_app/test.js", {"context": {"enums": [EnumTester.AddressRoute]}}),
            ],
        }
    )
    def test_no_raise_on_not_found(self):
        call_command("renderstatic", "enum_app/test.js")
        js_dict = self.get_js_structure(GLOBAL_STATIC_DIR / "enum_app/test.js")
        self.assertDictEqual(js_dict, {"not_found": None})

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "enum_app/test.js": "{% enums_to_js enums=enums symmetric_properties=True raise_on_not_found=False %}\n"
                                    'console.log(JSON.stringify({not_found: AddressRoute.get("Aly")}));'
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": [
                ("enum_app/test.js", {"context": {"enums": [EnumTester.AddressRoute]}}),
            ],
        }
    )
    def test_raise_on_not_found_false_deprecated(self):
        with self.assertWarns(DeprecationWarning):
            call_command("renderstatic", "enum_app/test.js")
        js_dict = self.get_js_structure(GLOBAL_STATIC_DIR / "enum_app/test.js")
        self.assertDictEqual(js_dict, {"not_found": None})

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "enum_app/test.js": "{% enums_to_js enums=enums symmetric_properties=True raise_on_not_found=True %}\n"
                                    'console.log(JSON.stringify({not_found: AddressRoute.get("Aly")}));'
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": [
                ("enum_app/test.js", {"context": {"enums": [EnumTester.AddressRoute]}}),
            ],
        }
    )
    def test_raise_on_not_found_true_deprecated(self):
        with self.assertWarns(DeprecationWarning):
            call_command("renderstatic", "enum_app/test.js")
        self.assertIn(
            "TypeError: No AddressRoute enumeration maps to value Aly",
            run_js_file(GLOBAL_STATIC_DIR / "enum_app/test.js"),
        )

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "enum_app/test.js": '{% enums_to_js enums=enums on_unrecognized="RETURN_INPUT" %}\n'
                                    'console.log(JSON.stringify({not_found: AddressRoute.get("Aly")}));'
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": [
                ("enum_app/test.js", {"context": {"enums": [EnumTester.AddressRoute]}}),
            ],
        }
    )
    def test_return_input_on_unrecognized(self):
        call_command("renderstatic", "enum_app/test.js")
        js_dict = self.get_js_structure(GLOBAL_STATIC_DIR / "enum_app/test.js")
        self.assertDictEqual(js_dict, {"not_found": "Aly"})

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "enum_app/test.js": '{% enums_to_js enums=enums symmetric_properties=True on_unrecognized="THROW_EXCEPTION" %}\n'
                                    'try { AddressRoute.get("Aly") } catch (e) {console.log(JSON.stringify({not_found: e instanceof TypeError ? "TypeError" : "Unknown"}));}'
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": [
                ("enum_app/test.js", {"context": {"enums": [EnumTester.AddressRoute]}}),
            ],
        }
    )
    def test_raise_on_not_found(self):
        call_command("renderstatic", "enum_app/test.js")
        js_dict = self.get_js_structure(GLOBAL_STATIC_DIR / "enum_app/test.js")
        self.assertDictEqual(js_dict, {"not_found": "TypeError"})

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "enum_app/test.js": '{% enums_to_js enums=enums symmetric_properties=True transpiler="render_static.transpilers.EnumClassWriter" %}\n'
                                    'try { AddressRoute.get("Aly") } catch (e) {console.log(JSON.stringify({not_found: e instanceof TypeError ? "TypeError" : "Unknown"}));}'
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": [
                ("enum_app/test.js", {"context": {"enums": [EnumTester.AddressRoute]}}),
            ],
        }
    )
    def test_default_raise_on_not_found(self):
        return self.test_raise_on_not_found.__wrapped__(self)

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "enum_app/test.js": "{% enums_to_js enums=enums %}\n"
                                    "console.log(JSON.stringify({found: AddressRoute.get(AddressRoute.AVENUE)}));"
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": [
                ("enum_app/test.js", {"context": {"enums": [EnumTester.AddressRoute]}}),
            ],
        }
    )
    def test_return_instance(self):
        call_command("renderstatic", "enum_app/test.js")
        js_dict = self.get_js_structure(GLOBAL_STATIC_DIR / "enum_app/test.js")
        self.assertEqual(js_dict["found"]["value"], "AVE")

    @override_settings(
        STATIC_TEMPLATES={
            "templates": [
                (
                    "enum_app/enum.js",
                    {
                        "context": {
                            "enums": [
                                EnumTester.AddressRoute,
                                *IGNORED_ENUMS,
                                EnumTester.AddressRoute,
                                IGNORED_ENUMS,
                            ]
                        }
                    },
                ),
            ]
        }
    )
    def test_exclude_ignored_and_no_repeat(self):
        call_command("renderstatic", "enum_app/enum.js")
        contents = get_content(ENUM_STATIC_DIR / "enum_app/enum.js")
        self.assertEqual(contents.count("class "), 1)
        self.assertIn("class AddressRoute", contents)
        for en in IGNORED_ENUMS:
            self.assertNotIn(f"class {en.__name__}", contents)

    @override_settings(
        ROOT_URLCONF="tests.enum_app.urls",
        STATIC_TEMPLATES={
            "context": {
                "include_properties": True,
                "properties": True,
                "symmetric_properties": True,
            },
            "templates": [
                (
                    "enum_app/test.js",
                    {
                        "context": {
                            "enums": [DependentEnum],
                            "test_symmetric_properties": ["indep"],
                        },
                        "dest": GLOBAL_STATIC_DIR / "enum/missin_dep_enum.js",
                    },
                )
            ],
        },
    )
    def test_chained_enum_values_missing_dep(self):
        """
        This must run before test_chained_enum_values!
        :return:
        """
        call_command("renderstatic", "enum_app/test.js")
        js_dict = self.get_js_structure(GLOBAL_STATIC_DIR / "enum/missin_dep_enum.js")
        self.assertEqual(js_dict["DependentEnum"]["getCheck"], 1)
        contents = get_content(GLOBAL_STATIC_DIR / "enum/missin_dep_enum.js")
        self.assertIn(
            "enums.DependentEnum.getCheck &= DependentEnum.VALUE0 === DependentEnum.get(22);",
            contents,
        )
        self.assertIn(
            "enums.DependentEnum.getCheck &= DependentEnum.VALUE1 === DependentEnum.get(21);",
            contents,
        )
        self.assertIn(
            "enums.DependentEnum.getCheck &= DependentEnum.VALUE2 === DependentEnum.get(20);",
            contents,
        )
        self.assertIn(
            'static VALUE0 = new DependentEnum(0, "VALUE0", 22, "DependentEnum.VALUE0");',
            contents,
        )
        self.assertIn(
            'static VALUE1 = new DependentEnum(1, "VALUE1", 21, "DependentEnum.VALUE1");',
            contents,
        )
        self.assertIn(
            'static VALUE2 = new DependentEnum(2, "VALUE2", 20, "DependentEnum.VALUE2");',
            contents,
        )

    @override_settings(
        ROOT_URLCONF="tests.enum_app.urls",
        STATIC_TEMPLATES={
            "context": {
                "include_properties": True,
                "properties": True,
                "symmetric_properties": True,
            },
            "templates": [
                (
                    "enum_app/test.js",
                    {
                        "context": {
                            "enums": [IndependentEnum, DependentEnum],
                            "test_enums": [DependentEnum],
                            "test_symmetric_properties": ["indep"],
                            "class_name_map": {IndependentEnum: "IndependentEnum"},
                        },
                        "dest": GLOBAL_STATIC_DIR / "enum/dependent_enums.js",
                    },
                )
            ],
        },
    )
    def test_chained_enum_values(self):
        call_command("renderstatic", "enum_app/test.js")
        js_dict = self.get_js_structure(GLOBAL_STATIC_DIR / "enum/dependent_enums.js")
        self.assertEqual(js_dict["DependentEnum"]["getCheck"], 1)
        contents = get_content(GLOBAL_STATIC_DIR / "enum/dependent_enums.js")
        self.assertIn(
            "enums.DependentEnum.getCheck &= DependentEnum.VALUE0 === DependentEnum.get(IndependentEnum.VALUE2);",
            contents,
        )
        self.assertIn(
            "enums.DependentEnum.getCheck &= DependentEnum.VALUE1 === DependentEnum.get(IndependentEnum.VALUE1);",
            contents,
        )
        self.assertIn(
            "enums.DependentEnum.getCheck &= DependentEnum.VALUE2 === DependentEnum.get(IndependentEnum.VALUE0);",
            contents,
        )
        self.assertIn(
            'static VALUE0 = new DependentEnum(0, "VALUE0", IndependentEnum.VALUE2, "DependentEnum.VALUE0");',
            contents,
        )
        self.assertIn(
            'static VALUE1 = new DependentEnum(1, "VALUE1", IndependentEnum.VALUE1, "DependentEnum.VALUE1");',
            contents,
        )
        self.assertIn(
            'static VALUE2 = new DependentEnum(2, "VALUE2", IndependentEnum.VALUE0, "DependentEnum.VALUE2");',
            contents,
        )

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "enum_app/test.js": """
{% enums_to_js enums='tests.enum_app.models.EnumTester.Color' include_properties="hex,name,value,rgb,label"|split:"," %}
{% enums_to_js enums='tests.enum_app.models.EnumTester.MapBoxStyle' include_properties="value,name,label,uri,slug,version"|split:"," %}
{% enums_to_js enums='tests.enum_app.models.EnumTester.AddressRoute' include_properties="name,value,alt"|split:"," %}
"""
                                },
                            )
                        ]
                    },
                }
            ],
        }
    )
    def test_property_order_determinism_bug131(self):
        enum_js = GLOBAL_STATIC_DIR / "enum_app/test.js"
        for _ in range(0, 10):
            call_command("renderstatic", "enum_app/test.js")
            transpilation = enum_js.read_text()
            self.assertIn("constructor (value, name, label, rgb, hex)", transpilation)
            self.assertIn(
                "constructor (value, name, label, slug, version, uri, str)",
                transpilation,
            )
            self.assertIn("constructor (value, name, alt, str)", transpilation)
            os.remove(enum_js)

    def tearDown(self):
        pass

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "enum_app/test.js": """
{% enums_to_js enums=enums symmetric_properties=True %}
{% override "get" %}
/**
 * A comment.
 */
static get(value) {
    if (value === null) {
        return {
            'enum': {% autoescape off %}"{{enum}}"{% endautoescape %},
            'class_name': "{{class_name}}",
            'properties': [{% for prop in properties %}"{{prop}}",{% endfor %}],
            'class_properties': [{% for prop in class_properties %}"{{prop}}",{% endfor %}],
            'symmetric_properties': [{% for prop in symmetric_properties %}"{{prop}}",{% endfor %}],
            'to_string': {% if to_string %}true{% else %}false{% endif %},
            'str_prop': "{{ str_prop }}"
        };
    }
    {{ default_impl }}}
{% endoverride %}

'enum': self.enum,
'class_name': self.class_name,
'properties': self.properties,
'str_prop': self.str_prop,
'class_properties': self.class_properties,
'symmetric_properties': self.symmetric_properties,
'to_string': self.to_string_

{% override "constructor" %}
constructor (value, name, label, alt, str, str0) {
    {{ default_impl }}
    this.constructor_context = {
        'enum': {% autoescape off %}"{{enum}}"{% endautoescape %},
        'class_name': "{{class_name}}",
        'properties': [{% for prop in properties %}"{{prop}}",{% endfor %}],
        'class_properties': [{% for prop in class_properties %}"{{prop}}",{% endfor %}],
        'symmetric_properties': [{% for prop in symmetric_properties %}"{{prop}}",{% endfor %}],
        'to_string': {% if to_string %}true{% else %}false{% endif %},
        'str_prop': "{{ str_prop }}"
    };
}
{% endoverride %}

{% override "toString" %}
toString() { 
    return {
        'enum': {% autoescape off %}"{{enum}}"{% endautoescape %},
        'class_name': "{{class_name}}",
        'properties': [{% for prop in properties %}"{{prop}}",{% endfor %}],
        'class_properties': [{% for prop in class_properties %}"{{prop}}",{% endfor %}],
        'symmetric_properties': [{% for prop in symmetric_properties %}"{{prop}}",{% endfor %}],
        'to_string': {% if to_string %}true{% else %}false{% endif %},
        'str_prop': "{{ str_prop }}"
    };
}
{% endoverride %}

{% override "ciCompare" %}
static ciCompare(a, b) { 
    {{ class_name}}.ci_compare_context = {
        'enum': {% autoescape off %}"{{enum}}"{% endautoescape %},
        'class_name': "{{class_name}}",
        'properties': [{% for prop in properties %}"{{prop}}",{% endfor %}],
        'class_properties': [{% for prop in class_properties %}"{{prop}}",{% endfor %}],
        'symmetric_properties': [{% for prop in symmetric_properties %}"{{prop}}",{% endfor %}],
        'to_string': {% if to_string %}true{% else %}false{% endif %},
        'str_prop': "{{ str_prop }}"
    };
    {{ default_impl }}
}
{% endoverride %}


{% override "[Symbol.iterator]" %}
static [Symbol.iterator]() {
    {{ class_name }}.iterator_context = {
        'enum': {% autoescape off %}"{{enum}}"{% endautoescape %},
        'class_name': "{{class_name}}",
        'properties': [{% for prop in properties %}"{{prop}}",{% endfor %}],
        'class_properties': [{% for prop in class_properties %}"{{prop}}",{% endfor %}],
        'symmetric_properties': [{% for prop in symmetric_properties %}"{{prop}}",{% endfor %}],
        'to_string': {% if to_string %}true{% else %}false{% endif %},
        'str_prop': "{{ str_prop }}"
    };
    {{ default_impl }}
}
{% endoverride %}

{% override "testContext" %}
static testContext() { 
    return {
        'enum': {% autoescape off %}"{{enum}}"{% endautoescape %},
        'class_name': "{{class_name}}",
        'properties': [{% for prop in properties %}"{{prop}}",{% endfor %}],
        'class_properties': [{% for prop in class_properties %}"{{prop}}",{% endfor %}],
        'symmetric_properties': [{% for prop in symmetric_properties %}"{{prop}}",{% endfor %}],
        'to_string': {% if to_string %}true{% else %}false{% endif %},
        'str_prop': "{{ str_prop }}"
    };
}
{% endoverride %}

{% endenums_to_js %}
console.log(JSON.stringify(
    {
        getNull: AddressRoute.get(null),
        getAve: AddressRoute.get(AddressRoute.AVENUE).label,
        getAve2: AddressRoute.get('AvEnUe').label,
        testContext: AddressRoute.testContext(),
        toString: AddressRoute.AVENUE.toString(),
        constructor_context: AddressRoute.AVENUE.constructor_context,
        iterator_context: AddressRoute.iterator_context,
        ci_compare_context: AddressRoute.ci_compare_context,
    }
));
"""
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
            "templates": [
                ("enum_app/test.js", {"context": {"enums": [EnumTester.AddressRoute]}}),
            ],
        }
    )
    def test_overrides(self):
        call_command("renderstatic", "enum_app/test.js")
        js_dict = self.get_js_structure(GLOBAL_STATIC_DIR / "enum_app/test.js")

        expected_context = {
            "enum": "<enum 'AddressRoute'>",
            "class_name": "AddressRoute",
            "properties": ["value", "name", "label", "alt", "str"],
            "class_properties": ["class_name"],
            "symmetric_properties": ["name", "label"],
            "to_string": True,
            "str_prop": "str0",
        }
        self.assertEqual(js_dict["testContext"], expected_context)
        self.assertEqual(js_dict["getNull"], expected_context)
        self.assertEqual(js_dict["getAve"], "Avenue")
        self.assertEqual(js_dict["getAve2"], "Avenue")
        self.assertEqual(js_dict["toString"], expected_context)
        self.assertEqual(js_dict["constructor_context"], expected_context)
        self.assertEqual(js_dict["iterator_context"], expected_context)
        self.assertEqual(js_dict["ci_compare_context"], expected_context)

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "enum_app/test.js": """
{% enums_to_js enums="tests.enum_app.models.EnumTester.MapBoxStyle" %}
{% enums_to_js enums="tests.enum_app.models.EnumTester.AddressRoute" symmetric_properties=True %}

{% override "testContext" %}
static testContext() { 
    return {
        'enum': {% autoescape off %}"{{enum}}"{% endautoescape %},
        'class_name': "{{class_name}}",
        'properties': [{% for prop in properties %}"{{prop}}",{% endfor %}],
        'class_properties': [{% for prop in class_properties %}"{{prop}}",{% endfor %}],
        'symmetric_properties': [{% for prop in symmetric_properties %}"{{prop}}",{% endfor %}],
        'to_string': {% if to_string %}true{% else %}false{% endif %},
        'str_prop': "{{ str_prop }}"
    };
}
{% endoverride %}
{% endenums_to_js %}
{% transpile "tests.enum_app.models.EnumTester.Color" "render_static.transpilers.EnumClassWriter" %}
console.log(JSON.stringify(
    {
        testContext: AddressRoute.testContext(),
        mapbox: MapBoxStyle.get(1).label,
        red: Color.RED.hex,
    }
));
"""
                                },
                            )
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
        }
    )
    def test_multi_block(self):
        call_command("renderstatic", "enum_app/test.js")
        js_dict = self.get_js_structure(GLOBAL_STATIC_DIR / "enum_app/test.js")
        expected_context = {
            "enum": "<enum 'AddressRoute'>",
            "class_name": "AddressRoute",
            "properties": ["value", "name", "label", "alt", "str"],
            "class_properties": ["class_name"],
            "symmetric_properties": ["name", "label"],
            "to_string": True,
            "str_prop": "str0",
        }
        self.assertEqual(js_dict["testContext"], expected_context)
        self.assertEqual(js_dict["mapbox"], "Streets")
        self.assertEqual(js_dict["red"], "ff0000")

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "enum_app/test.js": "{% enums_to_js enums='tests.enum_app.models.EnumTester.Nope' %}"
                                },
                            ),
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "enum_app/test2.js": "{% enums_to_js enums='does_not_exist' %}"
                                },
                            ),
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "enum_app/test3.js": "{% enums_to_js enums='render_static.does_not_exist' %}"
                                },
                            ),
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "enum_app/test4.js": "{% enums_to_js enums='tests.enum_app.models.DNE' %}"
                                },
                            ),
                        ],
                        "builtins": ["render_static.templatetags.render_static"],
                    },
                }
            ],
        }
    )
    def test_import_error(self):
        with self.assertRaises(CommandError):
            call_command("renderstatic", "enum_app/test.js")
        with self.assertRaises(CommandError):
            call_command("renderstatic", "enum_app/test2.js")
        with self.assertRaises(CommandError):
            call_command("renderstatic", "enum_app/test3.js")
        with self.assertRaises(CommandError):
            call_command("renderstatic", "enum_app/test4.js")


@override_settings(
    ROOT_URLCONF="tests.urls_default_args",
    STATIC_TEMPLATES={
        "ENGINES": [
            {
                "BACKEND": "render_static.backends.StaticDjangoTemplates",
                "OPTIONS": {
                    "loaders": [
                        (
                            "render_static.loaders.StaticLocMemLoader",
                            {"urls.js": "{% urls_to_js %}"},
                        )
                    ],
                    "builtins": ["render_static.templatetags.render_static"],
                },
            }
        ]
    },
)
class SitemapURLSToJavascriptTest(URLJavascriptMixin, BaseTestCase):
    # def tearDown(self):
    #     pass

    def setUp(self):
        self.clear_placeholder_registries()

    def test_sitemap_url_generation(self):
        """
        Test class code with legacy arguments specified individually - may be deprecated in 2.0
        """
        self.es6_mode = True
        self.url_js = None
        self.class_mode = ClassURLWriter.class_name_
        call_command("renderstatic", "urls.js")
        self.assertEqual(self.get_url_from_js("sitemap"), reverse("sitemap"))
        self.assertNotIn("sitemaps", Path(GLOBAL_STATIC_DIR / "urls.js").read_text())

        self.assertEqual(
            self.get_url_from_js("default", kwargs={"def": "test"}),
            reverse("default", kwargs={"def": "test"}),
        )

        self.assertIn(
            "complex_default", Path(GLOBAL_STATIC_DIR / "urls.js").read_text()
        )

        from tests.urls_default_args import Default

        self.assertEqual(
            self.get_url_from_js(
                "default", kwargs={"def": "blarg", "complex_default": {"blog": Default}}
            ),
            reverse(
                "default", kwargs={"def": "blarg", "complex_default": {"blog": Default}}
            ),
        )
