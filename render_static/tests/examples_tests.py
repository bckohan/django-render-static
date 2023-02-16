"""
All examples from the documentation should be tested here!
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from render_static.tests.js_tests import (
    EnumComparator,
    StructureDiff,
    URLJavascriptMixin,
    run_js_file,
)
from render_static.tests.tests import BaseTestCase
from render_static.transpilers.urls_to_js import ClassURLWriter

try:
    from django.utils.decorators import classproperty
except ImportError:
    from django.utils.functional import classproperty

EXAMPLE_STATIC_DIR = Path(__file__).parent / 'examples' / 'static' / 'examples'
TRANSPILED_DIR = Path(__file__).parent / 'transpiled'

node_version = None
if shutil.which('node'):  # pragma: no cover
    match = re.match(
        r'v(\d+).(\d+).(\d+)',
        subprocess.getoutput('node --version')
    )
    if match:
        try:
            node_version = (
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3))
            )
        except (TypeError, ValueError):
            pass

if not node_version:  # pragma: no cover
    pytest.skip(
        'JavaScript tests require node.js to be installed.',
        allow_module_level=True
    )


@override_settings(
    STATIC_TEMPLATES={
        'templates': [
            'examples/defines.js'
        ]
    }
)
class TestReadmeDefines(StructureDiff, BaseTestCase):

    # def tearDown(self):
    #     pass

    to_remove = [
        *BaseTestCase.to_remove,
        EXAMPLE_STATIC_DIR
    ]

    def test_readme_defines(self):
        call_command('renderstatic', 'examples/defines.js')
        from render_static.tests.examples import models
        self.assertEqual(
            self.diff_modules(
                js_file=EXAMPLE_STATIC_DIR / 'defines.js',
                py_modules=[models]
            ),
            {}
        )


@override_settings(
    STATIC_TEMPLATES={
        'templates': [
            'examples/enums.js'
        ]
    }
)
class TestReadmeEnum(BaseTestCase):

    # def tearDown(self):
    #     pass

    to_remove = [
        *BaseTestCase.to_remove,
        EXAMPLE_STATIC_DIR
    ]

    def test_readme_enums(self):
        call_command('renderstatic', 'examples/enums.js')
        result = run_js_file(EXAMPLE_STATIC_DIR / 'enums.js')
        self.assertEqual(
            result,
            "true\nColor {\n  value: 'R',\n  name: 'RED',\n  label: 'Red',\n  "
            "rgb: [ 1, 0, 0 ],\n  hex: 'ff0000'\n}\nColor {\n  value: 'G',\n  "
            "name: 'GREEN',\n  label: 'Green',\n  rgb: [ 0, 1, 0 ],\n  hex: "
            "'00ff00'\n}\nColor {\n  value: 'B',\n  name: 'BLUE',\n  label: "
            "'Blue',\n  rgb: [ 0, 0, 1 ],\n  hex: '0000ff'\n}"
        )


@override_settings(
    ROOT_URLCONF='render_static.tests.examples.urls',
    STATICFILES_DIRS=[
        TRANSPILED_DIR
    ],
    STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': (
                            '{% urls_to_js exclude=exclude %}'
                        )
                    }),
                    'render_static.loaders.StaticAppDirectoriesBatchLoader'
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }],
        'templates': [
            ('urls.js', {
                'dest': TRANSPILED_DIR / 'urls.js',
                'context': {
                    'exclude': ['admin']
                }
            }),
            ('examples/readme_url_usage.js', {
                'context': {
                    'exclude': ['admin']
                }
            })
        ]
    }
)
class TestReadmeURLs(URLJavascriptMixin, BaseTestCase):

    to_remove = [
        *BaseTestCase.to_remove,
        EXAMPLE_STATIC_DIR,
        TRANSPILED_DIR
    ]

    # def tearDown(self):
    #     pass

    def test_readme_urls(self):
        """
        Test es6 url class.
        """
        self.es6_mode = True
        self.url_js = None
        self.class_mode = ClassURLWriter.class_name_

        transpiled = TRANSPILED_DIR / 'urls.js'

        call_command('renderstatic', 'urls.js')
        for name, kwargs in [
            ('simple', {}),
            ('simple', {'arg1': 2}),
            ('different', {'arg1': 3, 'arg2': 'stringarg'})
        ]:
            self.assertEqual(
                reverse(name, kwargs=kwargs),
                self.get_url_from_js(name, kwargs, url_path=transpiled)
            )

        self.assertNotEqual(
            reverse('admin:index'),
            self.get_url_from_js('admin:index', {}, url_path=transpiled)
        )

    def test_readme_usage(self):
        call_command('renderstatic', 'examples/readme_url_usage.js')
        paths = run_js_file(EXAMPLE_STATIC_DIR / 'readme_url_usage.js').split()
        self.assertEqual(paths[0], '/different/143/emma')
        self.assertEqual(paths[1], '/different/143/emma?intarg=0&listarg=A&listarg=B&listarg=C')
