"""
All examples from the documentation should be tested here!
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest
from deepdiff import DeepDiff
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse

from tests.test_js import (
    GLOBAL_STATIC_DIR,
    EnumComparator,
    StructureDiff,
    URLJavascriptMixin,
    run_js_file,
)
from tests.test_core import BaseTestCase
from render_static.transpilers.urls_to_js import ClassURLWriter

try:
    from django.utils.decorators import classproperty
except ImportError:
    from django.utils.functional import classproperty

EXAMPLE_STATIC_DIR = Path(__file__).parent / "examples" / "static" / "examples"

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


@override_settings(STATIC_TEMPLATES={"templates": ["examples/defines.js"]})
class TestReadmeDefines(StructureDiff, BaseTestCase):
    def tearDown(self):
        pass

    to_remove = [*BaseTestCase.to_remove, EXAMPLE_STATIC_DIR]

    def test_readme_defines(self):
        call_command("renderstatic", "examples/defines.js")
        js_dict = self.get_js_structure(EXAMPLE_STATIC_DIR / "defines.js")
        self.assertEqual(
            DeepDiff(
                js_dict,
                {
                    "ExampleModel": {
                        "DEFINE1": "D1",
                        "DEFINE2": "D2",
                        "DEFINE3": "D3",
                        "DEFINES": [
                            ["D1", "Define 1"],
                            ["D2", "Define 2"],
                            ["D3", "Define 3"],
                        ],
                        "Color": {
                            "RED": "R",
                            "GREEN": "G",
                            "BLUE": "B",
                        },
                        "MapBoxStyle": {
                            "STREETS": 1,
                            "OUTDOORS": 2,
                            "LIGHT": 3,
                            "DARK": 4,
                            "SATELLITE": 5,
                            "SATELLITE_STREETS": 6,
                            "NAVIGATION_DAY": 7,
                            "NAVIGATION_NIGHT": 8,
                        },
                    }
                },
                # treat tuples and lists the same
                ignore_type_in_groups=[(tuple, list)],
            ),
            {},
        )


@override_settings(STATIC_TEMPLATES={"templates": ["examples/enums.js"]})
class TestReadmeEnum(BaseTestCase):
    # def tearDown(self):
    #     pass

    to_remove = []
    #     *BaseTestCase.to_remove,
    #     EXAMPLE_STATIC_DIR
    # ]

    def test_readme_enums(self):
        call_command("renderstatic", "examples/enums.js")
        result = run_js_file(EXAMPLE_STATIC_DIR / "enums.js")
        self.assertEqual(
            result,
            "true\nColor {\n  value: 'R',\n  name: 'RED',\n  label: 'Red',\n  "
            "rgb: [ 1, 0, 0 ],\n  hex: 'ff0000'\n}\nColor {\n  value: 'G',\n  "
            "name: 'GREEN',\n  label: 'Green',\n  rgb: [ 0, 1, 0 ],\n  hex: "
            "'00ff00'\n}\nColor {\n  value: 'B',\n  name: 'BLUE',\n  label: "
            "'Blue',\n  rgb: [ 0, 0, 1 ],\n  hex: '0000ff'\n}",
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
                                "color.js": """
{% enums_to_js enums="tests.examples.models.ExampleModel.Color" %}
    {# to override a function we must pass its name as the argument #}
    {% override 'get' %}
static get(value) {
    if (Array.isArray(value) && value.length === 4) {
        value = Color.cmykToRgb(...value);
    }

    if (Array.isArray(value) && value.length === 3) {
        for (const en of this) {
            let i = 0;
            for (; i < 3; i++) {
                if (en.rgb[i] !== value[i]) break;
            }
            if (i === 3) return en;
        }
    }
    {{ default_impl }}
}
    {% endoverride %}

    {# additions do not require a name argument #}
    {% override %}
static cmykToRgb(c, m, y, k) {

    let r = (1 - c / 100) * (1 - k / 100);
    let g = (1 - m / 100) * (1 - k / 100);
    let b = (1 - y / 100) * (1 - k / 100);
    
    return [Math.round(r), Math.round(g), Math.round(b)]
}
    {% endoverride %}
{% endenums_to_js %}
console.log(Color.get([0, 100, 100, 0]).label);
"""
                            },
                        ),
                        "render_static.loaders.StaticAppDirectoriesBatchLoader",
                    ]
                },
            }
        ]
    }
)
class TestEnumOverrideExample(BaseTestCase):
    to_remove = [GLOBAL_STATIC_DIR]

    def tearDown(self):
        pass

    def test_override_example(self):
        call_command("renderstatic", "color.js")
        result = run_js_file(GLOBAL_STATIC_DIR / "color.js")
        self.assertEqual(result, "Red")


@override_settings(
    ROOT_URLCONF="tests.examples.urls",
    STATIC_TEMPLATES={
        "ENGINES": [
            {
                "BACKEND": "render_static.backends.StaticDjangoTemplates",
                "OPTIONS": {
                    "loaders": [
                        (
                            "render_static.loaders.StaticLocMemLoader",
                            {"urls.js": "{% urls_to_js %}"},
                        ),
                        "render_static.loaders.StaticAppDirectoriesBatchLoader",
                    ]
                },
            }
        ],
        "templates": ["urls.js", "examples/readme_url_usage.js"],
    },
)
class TestReadmeURLs(URLJavascriptMixin, BaseTestCase):
    to_remove = []
    #     *BaseTestCase.to_remove,
    #     EXAMPLE_STATIC_DIR,
    #     TRANSPILED_DIR
    # ]

    # def tearDown(self):
    #     pass

    def test_readme_urls(self):
        """
        Test es6 url class.
        """
        from django.conf import settings

        self.es6_mode = True
        self.url_js = None
        self.class_mode = ClassURLWriter.class_name_

        transpiled = settings.STATIC_ROOT / "urls.js"

        call_command("renderstatic", "urls.js")
        for name, kwargs in [
            ("simple", {}),
            ("simple", {"arg1": 2}),
            ("different", {"arg1": 3, "arg2": "stringarg"}),
        ]:
            self.assertEqual(
                reverse(name, kwargs=kwargs),
                self.get_url_from_js(name, kwargs, url_path=transpiled),
            )

        self.assertNotEqual(
            reverse("admin:index"),
            self.get_url_from_js("admin:index", {}, url_path=transpiled),
        )

    def test_readme_usage(self):
        call_command("renderstatic", "examples/readme_url_usage.js")
        paths = run_js_file(EXAMPLE_STATIC_DIR / "readme_url_usage.js").split()
        self.assertEqual(paths[0], "/different/143/emma")
        self.assertEqual(
            paths[1], "/different/143/emma?intarg=0&listarg=A&listarg=B&listarg=C"
        )
