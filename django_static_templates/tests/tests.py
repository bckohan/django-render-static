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
EXPECTED_DIR = Path(__file__).parent / 'expected'


class BaseTestCase(TestCase):

    to_remove = [
        APP1_STATIC_DIR,
        GLOBAL_STATIC_DIR
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
    Tests:
        - context overriding
        - directory creation
        - app dir path resolution

    """
    def test_generate(self):
        call_command('generate_static')
        self.assertTrue(filecmp.cmp(
            APP1_STATIC_DIR / 'app1' / 'html' / 'hello.html',
            EXPECTED_DIR / 'ctx_override.html',
            shallow=False
        ))
