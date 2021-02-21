import filecmp
import inspect
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

import js2py
from deepdiff import DeepDiff
from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError, call_command
from django.template.exceptions import TemplateDoesNotExist
from django.template.utils import InvalidTemplateEngineError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.module_loading import import_string
from static_templates.backends import (
    StaticDjangoTemplates,
    StaticJinja2Templates,
)
from static_templates.engine import StaticTemplateEngine
from static_templates.origin import AppOrigin, Origin
from static_templates.tests import defines

APP1_STATIC_DIR = Path(__file__).parent / 'app1' / 'static'  # this dir does not exist and must be cleaned up
APP2_STATIC_DIR = Path(__file__).parent / 'app2' / 'static'  # this dir exists and is checked in
GLOBAL_STATIC_DIR = settings.STATIC_ROOT  # this dir does not exist and must be cleaned up
STATIC_TEMP_DIR = Path(__file__).parent / 'static_templates'
EXPECTED_DIR = Path(__file__).parent / 'expected'


USE_NODE_JS = True if shutil.which('node') else False


class BestEffortEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return json.JSONEncoder.default(self, obj)
        except TypeError:
            return str(obj)


class TestGenerateStaticParserAccessor(TestCase):
    """
    This test is just to get to 100% coverage - the get_parser function is private and is only
    available to serve the sphinx docs
    """

    def test_get_parser(self):
        from django.core.management.base import CommandParser
        from static_templates.management.commands.generate_static import (
            get_parser,
        )
        self.assertTrue(isinstance(get_parser(), CommandParser))


class AppOriginTestCase(TestCase):

    def test_equality(self):
        test_app1 = apps.get_app_config('static_templates_tests_app1')
        test_app2 = apps.get_app_config('static_templates_tests_app2')

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
        self.assertTrue(not APP2_STATIC_DIR.exists() or len(os.listdir(APP2_STATIC_DIR)) == 0)
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
        'BACKEND': 'static_templates.backends.StaticDjangoTemplates',
        'DIRS': [STATIC_TEMP_DIR],
        'OPTIONS': {
            'app_dir': 'custom_templates',
            'loaders': [
                'static_templates.loaders.StaticFilesystemLoader',
                'static_templates.loaders.StaticAppDirectoriesLoader'
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
        'BACKEND': 'static_templates.backends.StaticJinja2Templates',
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
        'BACKEND': 'static_templates.backends.StaticJinja2Templates',
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
                'BACKEND': 'static_templates.backends.StaticDjangoTemplates',
                'DIRS': [STATIC_TEMP_DIR],
                'APP_DIRS': True,
                'OPTIONS': {}
            }],
        })
        self.assertEqual(
            engine['StaticDjangoTemplates'].engine.loaders,
            [
                'static_templates.loaders.StaticFilesystemLoader',
                'static_templates.loaders.StaticAppDirectoriesLoader'
            ]
        )

        engine = StaticTemplateEngine({
            'ENGINES': [{
                'BACKEND': 'static_templates.backends.StaticDjangoTemplates',
                'DIRS': [STATIC_TEMP_DIR],
                'APP_DIRS': False,
                'OPTIONS': {}
            }],
        })
        self.assertEqual(
            engine['StaticDjangoTemplates'].engine.loaders, ['static_templates.loaders.StaticFilesystemLoader']
        )

    def test_app_dirs_error(self):
        """
        Configuring APP_DIRS and loader is an error.
        """
        engine = StaticTemplateEngine({
            'ENGINES': [{
                'BACKEND': 'static_templates.backends.StaticDjangoTemplates',
                'DIRS': [STATIC_TEMP_DIR],
                'APP_DIRS': True,
                'OPTIONS': {
                    'loaders': ['static_templates.loaders.StaticFilesystemLoader']
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
                'BACKEND': 'static_templates.backends.StaticDjangoTemplates',
                'APP_DIRS': True
            },
            {
                'NAME': 'IDENTICAL',
                'BACKEND': 'static_templates.backends.StaticJinja2Templates',
                'APP_DIRS': True
            }]
        })
        self.assertRaises(ImproperlyConfigured, lambda: engine.engines)

        engine = StaticTemplateEngine({
            'ENGINES': [{
                'NAME': 'IDENTICAL',
                'BACKEND': 'static_templates.backends.StaticDjangoTemplates',
                'APP_DIRS': True
            },
            {
                'NAME': 'DIFFERENT',
                'BACKEND': 'static_templates.backends.StaticJinja2Templates',
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
                'BACKEND': 'static_templates.backends.StaticDjangoTemplates',
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


@override_settings(STATIC_TEMPLATES=None)
class DirectRenderTestCase(BaseTestCase):

    def test_override_context(self):
        engine = StaticTemplateEngine({
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
        engine.render_to_disk('app1/html/hello.html', context={'punc': '.'})
        self.assertTrue(filecmp.cmp(
            APP1_STATIC_DIR / 'app1/html/hello.html',
            EXPECTED_DIR / 'ctx_override2.html',
            shallow=False
        ))

    def test_override_dest(self):
        engine = StaticTemplateEngine({
            'context': {
                'to': 'world',
                'punc': '!',
                'greeting': 'Bye'
            },
            'templates': {
                'app1/html/hello.html': {}
            }
        })
        engine.render_to_disk(
            'app1/html/hello.html',
            dest=str(GLOBAL_STATIC_DIR/'override_dest.html')
        )
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'override_dest.html',
            EXPECTED_DIR / 'dest_override.html',
            shallow=False
        ))


@override_settings(STATIC_TEMPLATES={
    'ENGINES': [{
        'BACKEND': 'static_templates.backends.StaticDjangoTemplates',
        'DIRS': [STATIC_TEMP_DIR],
        'OPTIONS': {
            'app_dir': 'custom_templates',
            'loaders': [
                'static_templates.loaders.StaticFilesystemLoader',
                'static_templates.loaders.StaticAppDirectoriesLoader'
            ]
        },
    }],
    'templates': {
        'nominal_fs.html': {}
    }
})
class RenderErrorsTestCase(BaseTestCase):

    @override_settings(STATIC_ROOT=None)
    def test_render_no_dest(self):
        self.assertRaises(CommandError, lambda: call_command('generate_static'))

    def test_render_default_static_root(self):
        call_command('generate_static')
        self.assertTrue(filecmp.cmp(
            settings.STATIC_ROOT / 'nominal_fs.html',
            EXPECTED_DIR / 'nominal_fs.html',
            shallow=False
        ))

    def test_render_missing(self):
        self.assertRaises(
            CommandError,
            lambda: call_command('generate_static', 'this/template/doesnt/exist.html')
        )


class GenerateNothing(BaseTestCase):

    def generate_nothing(self):
        """
        When no templates are configured, generate_static should generate nothing and it should not
        raise
        """
        call_command('generate_static')
        self.assertFalse(APP1_STATIC_DIR.exists())
        self.assertEqual(len(os.listdir(APP2_STATIC_DIR)), 0)
        self.assertFalse(GLOBAL_STATIC_DIR.exists())

    @override_settings(STATIC_TEMPLATES={})
    def test_empty_dict(self):
        self.generate_nothing()

    @override_settings(STATIC_TEMPLATES=None)
    def test_none_settings(self):
        self.generate_nothing()

    def test_missing_settings_raises(self):
        self.assertRaises(ImproperlyConfigured, lambda: call_command('generate_static'))


@override_settings(STATIC_TEMPLATES={
    'ENGINES': [{
        'BACKEND': 'static_templates.backends.StaticDjangoTemplates',
        'OPTIONS': {
            'app_dir': 'custom_templates',
            'loaders': [
                ('static_templates.loaders.StaticLocMemLoader', {
                    'defines1.js': 'var defines = {\n{{ classes|classes_to_js:"  " }}};',
                    'defines2.js': 'var defines = {\n{{ modules|modules_to_js }}};',
                    'defines_error.js': 'var defines = {\n{{ classes|classes_to_js }}};'
                })
            ],
            'builtins': ['static_templates.templatetags.static_templates']
        },
    }],
    'templates': {
        'defines1.js': {
            'dest': GLOBAL_STATIC_DIR / 'defines1.js',
            'context': {
                'classes': [defines.MoreDefines, 'static_templates.tests.defines.ExtendedDefines']
            }
        },
        'defines2.js': {
            'dest': GLOBAL_STATIC_DIR / 'defines2.js',
            'context': {
                'modules': [defines, 'static_templates.tests.defines2']
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

    def diff_classes(self, js_file, py_classes):
        """
        Given a javascript file and a list of classes, evaluate the javascript code into a python
        dictionary and determine if that dictionary matches the upper case parameters on the defines
        class.
        """
        members = {}
        with open(js_file, 'r') as js:
            js_dict = js2py.eval_js(js.read()).to_dict()
            for cls in py_classes:
                if isinstance(cls, str):
                    cls = import_string(cls)
                for mcls in reversed(cls.__mro__):
                    new_mems = {n: getattr(mcls, n) for n in dir(mcls) if n.isupper()}
                    if len(new_mems) > 0:
                        members.setdefault(cls.__name__, {}).update(new_mems)

        return DeepDiff(
            members,
            js_dict,
            ignore_type_in_groups=[(tuple, list)]  # treat tuples and lists the same
        )

    def test_classes_to_js(self):
        call_command('generate_static', 'defines1.js')
        self.assertEqual(
            self.diff_classes(
                js_file=GLOBAL_STATIC_DIR / 'defines1.js',
                py_classes=settings.STATIC_TEMPLATES[
                    'templates'
                ]['defines1.js']['context']['classes']
            ),
            {}
        )
        # verify indent
        with open(GLOBAL_STATIC_DIR / 'defines1.js', 'r') as jf:
            jf.readline()
            self.assertTrue(jf.readline().startswith('  '))

    def test_modules_to_js(self):
        call_command('generate_static', 'defines2.js')
        self.assertEqual(
            self.diff_modules(
                js_file=GLOBAL_STATIC_DIR / 'defines2.js',
                py_modules=settings.STATIC_TEMPLATES[
                    'templates'
                ]['defines2.js']['context']['modules']
            ),
            {}
        )
        # verify indent
        with open(GLOBAL_STATIC_DIR / 'defines2.js', 'r') as jf:
            jf.readline()
            self.assertFalse(jf.readline().startswith(' '))

    def test_classes_to_js_error(self):
        self.assertRaises(CommandError, lambda: call_command('generate_static', 'defines_error.js'))


@override_settings(STATIC_TEMPLATES={
    'ENGINES': [{
        'BACKEND': 'static_templates.backends.StaticDjangoTemplates',
        'OPTIONS': {
            'loaders': [
                ('static_templates.loaders.StaticLocMemLoader', {
                    'urls.js': 'var urls = {\n{% urls_to_js indent="  " es5=True%}};'
                })
            ],
            'builtins': ['static_templates.templatetags.static_templates']
        },
    }],
})
class URLSToJavascriptTest(BaseTestCase):

    url_js = None
    es5_mode = False

    def get_url_from_js(self, qname, options=None):  # pragma: no cover
        if options is None:
            options = {}
        if USE_NODE_JS:
            shutil.copyfile(GLOBAL_STATIC_DIR/'urls.js', GLOBAL_STATIC_DIR / 'get_url.js')
            accessor_str = ''
            for comp in qname.split(':'):
                accessor_str += f'["{comp}"]'
            with open(GLOBAL_STATIC_DIR / 'get_url.js', 'a+') as tmp_js:
                tmp_js.write(
                    f'\nconsole.log(urls{accessor_str}'
                    f'({json.dumps(options, cls=BestEffortEncoder)}));\n')

            return subprocess.check_output([
                'node',
                GLOBAL_STATIC_DIR / 'get_url.js'
            ]).decode('UTF-8').strip()

        if self.url_js is None:
            with open(GLOBAL_STATIC_DIR / 'urls.js', 'r') as jf:
                if self.es5_mode:
                    url_js = js2py.eval_js(jf.read())
                else:
                    import warnings
                    with warnings.catch_warnings():
                        warnings.filterwarnings('ignore', category=UserWarning)
                        """
                        Suppress the following warning from js2py:

                            Importing babel.py for the first time - this can take some time. 
                            Please note that currently Javascript 6 in Js2Py is unstable and slow. 
                            Use only for tiny scripts! Importing babel.py for the first time - this can 
                            take some time. Please note that currently Javascript 6 in Js2Py is unstable
                            and slow. Use only for tiny scripts!'
                        """
                        url_js = js2py.eval_js6(jf.read())
        func = url_js
        for comp in qname.split(':'):
            func = url_js[comp]
        return func(options)

    def compare(self, qname, options=None, object_hook=lambda dct: dct):
        if options is None:
            options = {}
        resp = self.client.get(self.get_url_from_js(qname, options))
        if resp.status_code == 301:
            resp = self.client.get(resp.url)

        self.assertEqual({
                'request': reverse(qname, kwargs=options),
                'args': [],
                'kwargs': options
            },
            resp.json(object_hook=object_hook)
        )

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'static_templates.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('static_templates.loaders.StaticLocMemLoader', {
                        'urls.js': 'var urls = {\n{% urls_to_js indent="  "%}};'
                    })
                ],
                'builtins': ['static_templates.templatetags.static_templates']
            },
        }],
    })
    def test_full_url_dump_es6(self):
        """
        This ES6 test is horrendously slow when not using node for reasons mentioned by the Js2Py
        warning
        """
        self.test_full_url_dump(es5=False)

    def test_full_url_dump(self, es5=True):
        self.es5_mode = es5
        self.url_js = None

        from static_templates import placeholders as gen
        gen.register_variable_placeholder('strarg', 'a')
        gen.register_variable_placeholder('intarg', 0)

        call_command('generate_static', 'urls.js')

        def convert_to_id(dct, key='id'):
            if key in dct:
                dct[key] = uuid.UUID(dct[key])
            return dct

        def convert_to_int(dct, key):
            if key in dct:
                dct[key] = int(dct[key])
            return dct

        #################################################################
        # root urls
        qname = 'path_tst'
        self.compare(qname)
        self.compare(qname, {'arg1': 1})
        self.compare(qname, {'arg1': 12, 'arg2': 'xo'})
        #################################################################

        #################################################################
        # app1 straight include 1
        qname = 'sub1:app1_pth'
        self.compare(qname)
        self.compare(qname, {'arg1': 143})  # emma
        self.compare(qname, {'arg1': 5678, 'arg2': 'xo'})
        self.compare('sub1:app1_detail', {'id': uuid.uuid1()}, object_hook=convert_to_id)
        self.compare('sub1:custom_tst', {'year': 2021})
        #################################################################

        #################################################################
        # app1 straight include 2
        qname = 'sub2:app1_pth'
        self.compare(qname)
        self.compare(qname, {'arg1': 143})  # emma
        self.compare(qname, {'arg1': 5678, 'arg2': 'xo'})
        self.compare('sub2:app1_detail', {'id': uuid.uuid1()}, object_hook=convert_to_id)
        self.compare('sub2:custom_tst', {'year': 1021})
        #################################################################

        #################################################################
        # app1 include through app2
        qname = 'app2:app1:app1_pth'
        self.compare(qname)
        self.compare(qname, {'arg1': 1})
        self.compare(qname, {'arg1': 12, 'arg2': 'xo'})
        self.compare('app2:app1:app1_detail', {'id': uuid.uuid1()}, object_hook=convert_to_id)
        self.compare('app2:app1:custom_tst', {'year': 2999})
        #################################################################

        #################################################################
        # app1 include through app2
        qname = 'app2:app2_pth'
        self.compare(qname)
        self.compare(qname, {'arg1': 'adf23'})
        self.compare(
            'app2:app2_pth_diff',
            {'arg2': 'this/is/a/path/', 'arg1': uuid.uuid1()},
            object_hook=lambda dct: convert_to_id(dct, 'arg1')
        )
        self.compare(
            'app2:app2_pth_diff',
            {'arg2': 'so/is/this', 'arg1': uuid.uuid1()},
            object_hook=lambda dct: convert_to_id(dct, 'arg1')
        )
        #################################################################

        #################################################################
        # re_paths

        self.compare('re_path_tst')
        self.compare('re_path_tst', {'strarg': 'DEMOPLY'})
        self.compare(
            're_path_tst',
            {'strarg': 'is', 'intarg': 1337},
            object_hook=lambda dct: convert_to_int(dct, 'intarg')
        )
        #################################################################

    def tearDown(self):
        pass
