from django.test import (
    TestCase,
    override_settings
)
from pathlib import Path
from django.core.management import call_command
import os
import filecmp
import shutil

"""
Subclass engines/loaders, extend template to StaticTemplate that records app
STATIC_TEMPLATES = {
    'ENGINES': [
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [],
            'APP_DIRS': True,  # will look in static
            'OPTIONS': {
                'autoescape': True,
                'context_processors': ['path.to.request.ctx.processor'],
                'debug': True,
                'string_if_invalid': '',
                'loaders': ('loader.module.class', ['arg1', 'arg2']),
                'libraries': [],
                'builtins': []
            },
        },
        {
            'BACKEND': 'django.template.backends.jinja2.Jinja2',
            'APP_DIRS': True,  # will look in jinja2
            'DIRS': [],
            'OPTIONS': {
                'loader': 'a.singular.loader.specific.to.jinja2'
            }
        }
    ],
    'context': {},  # global context
    'templates': {
        'app1/html/hello.html': {
            'dest': '',  # optional
            'context': {}  # file specific context
        }
    }
}
"""

APP1_STATIC_DIR = Path(__file__).parent / 'app1' / 'static'  # this dir does not exist and must be cleaned up
APP2_STATIC_DIR = Path(__file__).parent / 'app2' / 'static'  # this dir exists and is checked in
GLOBAL_STATIC_DIR = Path(__file__).parent / 'global_static'  # this dir does not exist and must be cleaned up
STATIC_TEMP_DIR = Path(__file__).parent / 'static_templates'
EXPECTED_DIR = Path(__file__).parent / 'expected'


class BaseTestCase(TestCase):

    to_remove = [
        APP1_STATIC_DIR,
        GLOBAL_STATIC_DIR,
        APP2_STATIC_DIR / 'app1',
        APP2_STATIC_DIR / 'app2',
        APP2_STATIC_DIR / 'nominal_fs2.html'
    ]

    def setUp(self):
        self.clean_generated()

    def tearDown(self):
        self.clean_generated()

    def clean_generated(self):
        for artifact in self.to_remove:
            if artifact.exists():
                if artifact.is_dir():
                    shutil.rmtree(artifact)
                else:
                    os.remove(artifact)


@override_settings(STATIC_TEMPLATES={})
class NominalTestCase(BaseTestCase):
    """
    The bare minimum configuration test cases. Verifies:
        - that settings present in context
        - that templates are findable even if unconfigured
        - verifies that generate_static accepts template arguments
    """
    def test_generate(self):
        call_command('generate_static', 'app1/html/nominal1.html')
        self.assertEqual(len(os.listdir(APP1_STATIC_DIR)), 1)
        self.assertEqual(len(os.listdir(APP2_STATIC_DIR)), 0)
        self.assertTrue(filecmp.cmp(
            APP1_STATIC_DIR / 'app1' / 'html' / 'nominal1.html',
            EXPECTED_DIR / 'nominal1.html',
            shallow=False
        ))
        call_command('generate_static', 'app1/html/nominal2.html')
        self.assertEqual(len(os.listdir(APP1_STATIC_DIR)), 1)
        self.assertEqual(len(os.listdir(APP2_STATIC_DIR)), 1)
        self.assertTrue(filecmp.cmp(
            APP2_STATIC_DIR / 'app1' / 'html' / 'nominal2.html',
            EXPECTED_DIR / 'nominal2.html',
            shallow=False
        ))


@override_settings(STATIC_TEMPLATES={
    'context': {
        'to': 'world',
        'punc': '!'
    },
    'templates': {
        'app1/html/hello.html': {
            'context': {
                'greeting': 'Hello',
                'to': 'World'
            },
        }
    }
})
class ContextOverrideTestCase(BaseTestCase):
    """
    Tests that per template contexts override global contexts and that the global context is also used.
    """
    def test_generate(self):
        call_command('generate_static')
        self.assertTrue(filecmp.cmp(
            APP1_STATIC_DIR / 'app1' / 'html' / 'hello.html',
            EXPECTED_DIR / 'ctx_override.html',
            shallow=False
        ))


@override_settings(STATIC_TEMPLATES={
    'context': {
        'to': 'world',
        'punc': '!',
        'greeting': 'Bye'
    },
    'templates': {
        'app1/html/hello.html': {
            'dest': GLOBAL_STATIC_DIR / 'dest_override.html'
        }
    }
})
class DestOverrideTestCase(BaseTestCase):
    """
    Tests that destination can be overridden for app directory loaded templates.
    """
    def test_generate(self):
        call_command('generate_static')
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'dest_override.html',
            EXPECTED_DIR / 'dest_override.html',
            shallow=False
        ))


@override_settings(STATIC_TEMPLATES={
    'ENGINES': [{
        'BACKEND': 'django_static_templates.backends.StaticDjangoTemplates',
        'DIRS': [STATIC_TEMP_DIR],
        'OPTIONS': {
            'app_dir': 'custom_templates',
            'loaders': [
                'django_static_templates.loaders.StaticFilesystemLoader',
                'django_static_templates.loaders.StaticAppDirectoriesLoader'
            ]
        },
    }],
    'templates': {
        'nominal_fs.html': {
            'dest': GLOBAL_STATIC_DIR / 'nominal_fs.html'
        }
    }
})
class FSLoaderTestCase(BaseTestCase):
    """
    Tests:
        - Filesystem loader
        - That loader order determines precedence
        - That app directory static template dirs can be configured @ the backend level
    """
    def test_generate(self):
        call_command('generate_static', 'nominal_fs.html', 'nominal_fs2.html')
        self.assertFalse(APP1_STATIC_DIR.exists())
        self.assertEqual(len(os.listdir(APP2_STATIC_DIR)), 1)
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR)), 1)
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'nominal_fs.html',
            EXPECTED_DIR / 'nominal_fs.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            APP2_STATIC_DIR / 'nominal_fs2.html',
            EXPECTED_DIR / 'nominal_fs2.html',
            shallow=False
        ))