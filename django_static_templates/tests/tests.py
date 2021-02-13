import filecmp
import os
import shutil
from pathlib import Path

from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError, call_command
from django.template.exceptions import TemplateDoesNotExist
from django.template.utils import InvalidTemplateEngineError
from django.test import TestCase, override_settings
from django_static_templates.backends import (
    StaticDjangoTemplates,
    StaticJinja2Templates,
)
from django_static_templates.engine import StaticTemplateEngine
from django_static_templates.origin import AppOrigin, Origin
from django_static_templates.tests import defines, defines2

APP1_STATIC_DIR = Path(__file__).parent / 'app1' / 'static'  # this dir does not exist and must be cleaned up
APP2_STATIC_DIR = Path(__file__).parent / 'app2' / 'static'  # this dir exists and is checked in
GLOBAL_STATIC_DIR = Path(__file__).parent / 'global_static'  # this dir does not exist and must be cleaned up
STATIC_TEMP_DIR = Path(__file__).parent / 'static_templates'
EXPECTED_DIR = Path(__file__).parent / 'expected'


class AppOriginTestCase(TestCase):

    def test_equality(self):
        test_app1 = apps.get_app_config('django_static_templates_tests_app1')
        test_app2 = apps.get_app_config('django_static_templates_tests_app2')

        origin1 = AppOrigin(name='/path/to/tmpl.html', template_name='to/tmpl.html', app=test_app1)
        origin2 = AppOrigin(name='/path/to/tmpl.html', template_name='to/tmpl.html', app=test_app1)
        origin3 = Origin(name='/path/to/tmpl.html', template_name='to/tmpl.html')
        origin4 = AppOrigin(name='/path/to/tmpl.html', template_name='to/tmpl.html', app=test_app2)
        origin5 = AppOrigin(name='/path/tmpl.html', template_name='tmpl.html', app=test_app2)
        origin6 = AppOrigin(name='/path/to/tmpl.html', template_name='tmpl.html')
        self.assertEqual(origin1, origin2)
        self.assertNotEqual(origin1, origin3)
        self.assertNotEqual(origin1, origin4)
        self.assertNotEqual(origin4, origin5)
        self.assertEqual(origin3, origin6)


class BaseTestCase(TestCase):

    to_remove = [
        APP1_STATIC_DIR,
        GLOBAL_STATIC_DIR,
        APP2_STATIC_DIR / 'app1',
        APP2_STATIC_DIR / 'app2'
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
        self.assertEqual(not APP2_STATIC_DIR.exists() or len(os.listdir(APP2_STATIC_DIR)), 0)
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
            'dest': str(GLOBAL_STATIC_DIR / 'dest_override.html')
        }
    }
})
class DestOverrideTestCase(BaseTestCase):
    """
    Tests that destination can be overridden for app directory loaded templates and that dest can be a string path
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

    to_remove = BaseTestCase.to_remove + [APP2_STATIC_DIR / 'nominal_fs2.html']

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


@override_settings(STATIC_TEMPLATES={
    'ENGINES': [{
        'BACKEND': 'django_static_templates.backends.StaticJinja2Templates',
        'DIRS': [STATIC_TEMP_DIR],
        'APP_DIRS': True
    }],
    'templates': {
        'nominal_jinja2.html': {
            'dest': GLOBAL_STATIC_DIR / 'nominal_jinja2.html'
        },
        'app1/html/app_jinja2.html': {}
    }
})
class Jinja2TestCase(BaseTestCase):
    """
    Tests:
        - Filesystem loader
        - That loader order determines precedence
        - That app directory static template dirs can be configured @ the backend level
    """
    def test_generate(self):
        call_command('generate_static')
        self.assertEqual(len(os.listdir(APP1_STATIC_DIR)), 1)
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR)), 1)
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'nominal_jinja2.html',
            EXPECTED_DIR / 'nominal_jinja2.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            APP1_STATIC_DIR / 'app1' / 'html' / 'app_jinja2.html',
            EXPECTED_DIR / 'app1_jinja2.html',
            shallow=False
        ))


@override_settings(STATIC_TEMPLATES={
    'ENGINES': [{
        'BACKEND': 'django_static_templates.backends.StaticJinja2Templates',
        'DIRS': [STATIC_TEMP_DIR],
        'APP_DIRS': True,
        'OPTIONS': {
            'app_dir': 'custom_jinja2'
        }
    }],
    'context': {
        'global_ctx': 'present',
        'ctx': 'absent'
    },
    'templates': {
        'app1/html/app_jinja2.html': {
            'context': {'ctx': 'present'}
        }
    }
})
class Jinja2CustomTestCase(BaseTestCase):
    """
    Tests:
        - Jinja2 custom app directory names work
        - Jinja2 contexts are present and that local overrides global
    """
    def test_generate(self):
        call_command('generate_static')
        self.assertEqual(len(os.listdir(APP2_STATIC_DIR)), 1)
        self.assertFalse(APP1_STATIC_DIR.exists())
        self.assertTrue(filecmp.cmp(
            APP2_STATIC_DIR / 'app1' / 'html' / 'app_jinja2.html',
            EXPECTED_DIR / 'app2_jinja2.html',
            shallow=False
        ))


class ConfigTestCase(TestCase):
    """
    Verifies configuration errors are reported as expected and that default loaders are created.
    """
    def test_default_loaders(self):
        """
        When no loaders specified, usage of app directories loaders is togged by APP_DIRS
        """
        engine = StaticTemplateEngine({
            'ENGINES': [{
                'BACKEND': 'django_static_templates.backends.StaticDjangoTemplates',
                'DIRS': [STATIC_TEMP_DIR],
                'APP_DIRS': True,
                'OPTIONS': {}
            }],
        })
        self.assertEqual(
            engine['StaticDjangoTemplates'].engine.loaders,
            [
                'django_static_templates.loaders.StaticFilesystemLoader',
                'django_static_templates.loaders.StaticAppDirectoriesLoader'
            ]
        )

        engine = StaticTemplateEngine({
            'ENGINES': [{
                'BACKEND': 'django_static_templates.backends.StaticDjangoTemplates',
                'DIRS': [STATIC_TEMP_DIR],
                'APP_DIRS': False,
                'OPTIONS': {}
            }],
        })
        self.assertEqual(
            engine['StaticDjangoTemplates'].engine.loaders, ['django_static_templates.loaders.StaticFilesystemLoader']
        )

    def test_app_dirs_error(self):
        """
        Configuring APP_DIRS and loader is an error.
        """
        engine = StaticTemplateEngine({
            'ENGINES': [{
                'BACKEND': 'django_static_templates.backends.StaticDjangoTemplates',
                'DIRS': [STATIC_TEMP_DIR],
                'APP_DIRS': True,
                'OPTIONS': {
                    'loaders': ['django_static_templates.loaders.StaticFilesystemLoader']
                }
            }]
        })
        self.assertRaises(ImproperlyConfigured, lambda: engine.engines)

    def test_dest_error(self):
        """
        Dest must be an absolute path in ether string or Path form.
        """
        engine = StaticTemplateEngine({
            'templates': {
                'nominal_fs.html': {
                    'dest': [GLOBAL_STATIC_DIR / 'nominal_fs.html']
                }
            }
        })
        self.assertRaises(ImproperlyConfigured, lambda: engine.templates)

        engine = StaticTemplateEngine({
            'templates': {
                'nominal_fs.html': {
                    'dest':  './nominal_fs.html'
                }
            }
        })
        self.assertRaises(ImproperlyConfigured, lambda: engine.templates)

    def test_context_error(self):
        """
        Context must be a dictionary.
        """
        engine = StaticTemplateEngine({
            'context': []
        })
        self.assertRaises(ImproperlyConfigured, lambda: engine.context)

        engine = StaticTemplateEngine({
            'templates': {
                'nominal_fs.html': {
                    'dest': GLOBAL_STATIC_DIR / 'nominal_fs.html',
                    'context': []
                }
            }
        })
        self.assertRaises(ImproperlyConfigured, lambda: engine.templates)

    def test_no_settings(self):
        """
        If no STATIC_TEMPLATES setting is present we should raise.
        """
        engine = StaticTemplateEngine()
        self.assertRaises(ImproperlyConfigured, lambda: engine.config)

    def test_unrecognized_settings(self):
        """
        Unrecognized configuration keys should raise.
        """
        engine = StaticTemplateEngine({
            'unknown_key': 0,
            'bad': 'value'
        })
        self.assertRaises(ImproperlyConfigured, lambda: engine.config)

        engine = StaticTemplateEngine({
            'templates': {
                'nominal_fs.html': {
                    'dest': GLOBAL_STATIC_DIR / 'nominal_fs.html',
                    'context': {},
                    'unrecognized_key': 'bad'
                }
            }
        })
        self.assertRaises(ImproperlyConfigured, lambda: engine.templates)

    def test_engines(self):
        """
        Engines must be an iterable containing Engine dictionary configs. Aliases must be unique.
        """
        engine = StaticTemplateEngine({
            'ENGINES': 0
        })
        self.assertRaises(ImproperlyConfigured, lambda: engine.engines)

        engine = StaticTemplateEngine({
            'ENGINES': [{
                'NAME': 'IDENTICAL',
                'BACKEND': 'django_static_templates.backends.StaticDjangoTemplates',
                'APP_DIRS': True
            },
            {
                'NAME': 'IDENTICAL',
                'BACKEND': 'django_static_templates.backends.StaticJinja2Templates',
                'APP_DIRS': True
            }]
        })
        self.assertRaises(ImproperlyConfigured, lambda: engine.engines)

        engine = StaticTemplateEngine({
            'ENGINES': [{
                'NAME': 'IDENTICAL',
                'BACKEND': 'django_static_templates.backends.StaticDjangoTemplates',
                'APP_DIRS': True
            },
            {
                'NAME': 'DIFFERENT',
                'BACKEND': 'django_static_templates.backends.StaticJinja2Templates',
                'APP_DIRS': True
            }]
        })
        self.assertTrue(type(engine['IDENTICAL']) is StaticDjangoTemplates)
        self.assertTrue(type(engine['DIFFERENT']) is StaticJinja2Templates)
        self.assertRaises(InvalidTemplateEngineError, lambda: engine['DOESNT_EXIST'])

    def test_backends(self):
        """
        Backends must exist.
        """
        engine = StaticTemplateEngine({
            'ENGINES': [{
                'BACKEND': 0
            }]
        })
        self.assertRaises(ImproperlyConfigured, lambda: engine.engines)

    def test_allow_dot_modifiers(self):
        engine = StaticTemplateEngine({
            'ENGINES': [{
                'BACKEND': 'django_static_templates.backends.StaticDjangoTemplates',
                'APP_DIRS': True,
            }],
            'templates': {
                '../app1/html/nominal1.html': {}
            }
        })
        self.assertRaises(
            TemplateDoesNotExist,
            lambda: engine.render_to_disk('../app1/html/nominal1.html')
        )


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
        'nominal_fs.html': {}
    }
})
class RenderErrorsTestCase(BaseTestCase):

    def test_render_no_dest(self):
        self.assertRaises(CommandError, lambda: call_command('generate_static'))

    def test_render_missing(self):
        self.assertRaises(CommandError, lambda: call_command('generate_static', 'this/template/doesnt/exist.html'))


@override_settings(STATIC_TEMPLATES={})
class GenerateNothing(BaseTestCase):

    def test_generate_nothing(self):
        """
        When no templates are configured, generate_static should generate nothing and it should not raise
        """
        call_command('generate_static')
        self.assertFalse(APP1_STATIC_DIR.exists())
        self.assertEqual(len(os.listdir(APP2_STATIC_DIR)), 0)
        self.assertFalse(GLOBAL_STATIC_DIR.exists())


@override_settings(STATIC_TEMPLATES={
    'ENGINES': [{
        'BACKEND': 'django_static_templates.backends.StaticDjangoTemplates',
        'OPTIONS': {
            'app_dir': 'custom_templates',
            'autoescape': False,
            'loaders': [
                ('django_static_templates.loaders.StaticLocMemLoader', {
                    'defines1.js': 'var defines = {\n  {{ classes|classes_to_js:"  " }}};',
                    'defines2.js': 'var defines = {\n{{ modules|modules_to_js }}};',
                    'defines_error.js': 'var defines = {\n{{ classes|classes_to_js }}};'
                })
            ],
            'builtins': ['django_static_templates.templatetags.django_static_templates']
        },
    }],
    'templates': {
        'defines1.js': {
            'dest': GLOBAL_STATIC_DIR / 'defines1.js',
            'context': {
                'classes': [defines.MoreDefines, defines.ExtendedDefines]
            }
        },
        'defines2.js': {
            'dest': GLOBAL_STATIC_DIR / 'defines2.js',
            'context': {
                'modules': [defines, defines2]
            }
        },
        'defines_error.js': {
            'dest': GLOBAL_STATIC_DIR / 'defines_error.js',
            'context': {
                'classes': [0, {}]
            }
        }
    }
})
class DefinesToJavascriptTest(BaseTestCase):

    def test_classes_to_js(self):
        call_command('generate_static', 'defines1.js')
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'defines1.js',
            EXPECTED_DIR / 'defines1.js',
            shallow=False
        ))

    def test_modules_to_js(self):
        call_command('generate_static', 'defines2.js')
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'defines2.js',
            EXPECTED_DIR / 'defines2.js',
            shallow=False
        ))

    def test_classes_to_js_error(self):
        self.assertRaises(CommandError, lambda: call_command('generate_static', 'defines_error.js'))
