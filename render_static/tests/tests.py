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
from render_static import placeholders
from render_static.backends import StaticDjangoTemplates, StaticJinja2Templates
from render_static.engine import StaticTemplateEngine
from render_static.origin import AppOrigin, Origin
from render_static.tests import bad_pattern, defines

APP1_STATIC_DIR = Path(__file__).parent / 'app1' / 'static'  # this dir does not exist and must be cleaned up
APP2_STATIC_DIR = Path(__file__).parent / 'app2' / 'static'  # this dir exists and is checked in
GLOBAL_STATIC_DIR = settings.STATIC_ROOT  # this dir does not exist and must be cleaned up
STATIC_TEMP_DIR = Path(__file__).parent / 'static_templates'
EXPECTED_DIR = Path(__file__).parent / 'expected'


USE_NODE_JS = True if shutil.which('node') else False

def get_url_mod():
    from render_static.tests import urls
    return urls


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
        from render_static.management.commands.render_static import get_parser
        self.assertTrue(isinstance(get_parser(), CommandParser))


class AppOriginTestCase(TestCase):

    def test_equality(self):
        test_app1 = apps.get_app_config('render_static_tests_app1')
        test_app2 = apps.get_app_config('render_static_tests_app2')

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
        - verifies that render_static accepts template arguments
    """
    def test_generate(self):
        call_command('render_static', 'app1/html/nominal1.html')
        self.assertEqual(len(os.listdir(APP1_STATIC_DIR)), 1)
        self.assertTrue(not APP2_STATIC_DIR.exists() or len(os.listdir(APP2_STATIC_DIR)) == 0)
        self.assertTrue(filecmp.cmp(
            APP1_STATIC_DIR / 'app1' / 'html' / 'nominal1.html',
            EXPECTED_DIR / 'nominal1.html',
            shallow=False
        ))
        call_command('render_static', 'app1/html/nominal2.html')
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
        call_command('render_static')
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
        call_command('render_static')
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'dest_override.html',
            EXPECTED_DIR / 'dest_override.html',
            shallow=False
        ))


@override_settings(STATIC_TEMPLATES={
    'ENGINES': [{
        'BACKEND': 'render_static.backends.StaticDjangoTemplates',
        'DIRS': [STATIC_TEMP_DIR],
        'OPTIONS': {
            'app_dir': 'custom_templates',
            'loaders': [
                'render_static.loaders.StaticFilesystemLoader',
                'render_static.loaders.StaticAppDirectoriesLoader'
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
        call_command('render_static', 'nominal_fs.html', 'nominal_fs2.html')
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
        'BACKEND': 'render_static.backends.StaticJinja2Templates',
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
        call_command('render_static')
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
        'BACKEND': 'render_static.backends.StaticJinja2Templates',
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
        call_command('render_static')
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
                'BACKEND': 'render_static.backends.StaticDjangoTemplates',
                'DIRS': [STATIC_TEMP_DIR],
                'APP_DIRS': True,
                'OPTIONS': {}
            }],
        })
        self.assertEqual(
            engine['StaticDjangoTemplates'].engine.loaders,
            [
                'render_static.loaders.StaticFilesystemLoader',
                'render_static.loaders.StaticAppDirectoriesLoader'
            ]
        )

        engine = StaticTemplateEngine({
            'ENGINES': [{
                'BACKEND': 'render_static.backends.StaticDjangoTemplates',
                'DIRS': [STATIC_TEMP_DIR],
                'APP_DIRS': False,
                'OPTIONS': {}
            }],
        })
        self.assertEqual(
            engine['StaticDjangoTemplates'].engine.loaders, ['render_static.loaders.StaticFilesystemLoader']
        )

    def test_app_dirs_error(self):
        """
        Configuring APP_DIRS and loader is an error.
        """
        engine = StaticTemplateEngine({
            'ENGINES': [{
                'BACKEND': 'render_static.backends.StaticDjangoTemplates',
                'DIRS': [STATIC_TEMP_DIR],
                'APP_DIRS': True,
                'OPTIONS': {
                    'loaders': ['render_static.loaders.StaticFilesystemLoader']
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
                'BACKEND': 'render_static.backends.StaticDjangoTemplates',
                'APP_DIRS': True
            },
            {
                'NAME': 'IDENTICAL',
                'BACKEND': 'render_static.backends.StaticJinja2Templates',
                'APP_DIRS': True
            }]
        })
        self.assertRaises(ImproperlyConfigured, lambda: engine.engines)

        engine = StaticTemplateEngine({
            'ENGINES': [{
                'NAME': 'IDENTICAL',
                'BACKEND': 'render_static.backends.StaticDjangoTemplates',
                'APP_DIRS': True
            },
            {
                'NAME': 'DIFFERENT',
                'BACKEND': 'render_static.backends.StaticJinja2Templates',
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
                'BACKEND': 'render_static.backends.StaticDjangoTemplates',
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
        'BACKEND': 'render_static.backends.StaticDjangoTemplates',
        'DIRS': [STATIC_TEMP_DIR],
        'OPTIONS': {
            'app_dir': 'custom_templates',
            'loaders': [
                'render_static.loaders.StaticFilesystemLoader',
                'render_static.loaders.StaticAppDirectoriesLoader'
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
        self.assertRaises(CommandError, lambda: call_command('render_static'))

    def test_render_default_static_root(self):
        call_command('render_static')
        self.assertTrue(filecmp.cmp(
            settings.STATIC_ROOT / 'nominal_fs.html',
            EXPECTED_DIR / 'nominal_fs.html',
            shallow=False
        ))

    def test_render_missing(self):
        self.assertRaises(
            CommandError,
            lambda: call_command('render_static', 'this/template/doesnt/exist.html')
        )


class GenerateNothing(BaseTestCase):

    def generate_nothing(self):
        """
        When no templates are configured, render_static should generate nothing and it should not
        raise
        """
        call_command('render_static')
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
        self.assertRaises(ImproperlyConfigured, lambda: call_command('render_static'))


@override_settings(STATIC_TEMPLATES={
    'ENGINES': [{
        'BACKEND': 'render_static.backends.StaticDjangoTemplates',
        'OPTIONS': {
            'app_dir': 'custom_templates',
            'loaders': [
                ('render_static.loaders.StaticLocMemLoader', {
                    'defines1.js': 'var defines = {\n{{ classes|classes_to_js:"  " }}};',
                    'defines2.js': 'var defines = {\n{{ modules|modules_to_js }}};',
                    'defines_error.js': 'var defines = {\n{{ classes|classes_to_js }}};'
                })
            ],
            'builtins': ['render_static.templatetags.render_static']
        },
    }],
    'templates': {
        'defines1.js': {
            'dest': GLOBAL_STATIC_DIR / 'defines1.js',
            'context': {
                'classes': [defines.MoreDefines, 'render_static.tests.defines.ExtendedDefines']
            }
        },
        'defines2.js': {
            'dest': GLOBAL_STATIC_DIR / 'defines2.js',
            'context': {
                'modules': [defines, 'render_static.tests.defines2']
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
        call_command('render_static', 'defines1.js')
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
        call_command('render_static', 'defines2.js')
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
        self.assertRaises(CommandError, lambda: call_command('render_static', 'defines_error.js'))

    [defines, 'render_static.tests.defines2']
    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'defines1.js': ('var defines = '
                                        '{\n{{ '
                                        '"render_static.tests.defines.MoreDefines,'
                                        'render_static.tests.defines.ExtendedDefines"|split:","'
                                        '|classes_to_js:"  " }}};'
                        ),
                        'defines2.js': ('var defines = '
                                        '{\n{{ '
                                        '"render_static.tests.defines '
                                        'render_static.tests.defines2"|split'
                                        '|modules_to_js:"  " }}};'
                        )
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }],
        'templates': {
            'defines1.js': {'dest': GLOBAL_STATIC_DIR / 'defines1.js'},
            'defines2.js': {'dest': GLOBAL_STATIC_DIR / 'defines2.js'}
        }
    })
    def test_split(self):
        call_command('render_static', 'defines1.js', 'defines2.js')
        self.assertEqual(
            self.diff_classes(
                js_file=GLOBAL_STATIC_DIR / 'defines1.js',
                py_classes=[defines.MoreDefines, defines.ExtendedDefines]
            ),
            {}
        )
        self.assertEqual(
            self.diff_modules(
                js_file=GLOBAL_STATIC_DIR / 'defines2.js',
                py_modules=['render_static.tests.defines', 'render_static.tests.defines2']
            ),
            {}
        )

    def tearDown(self):
        pass


class URLJavascriptMixin:

    url_js = None
    es5_mode = False

    def clear_placeholder_registries(self):
        from importlib import reload
        reload(placeholders)

    def exists(self, *args, **kwargs):
        return len(self.get_url_from_js(*args, **kwargs)) > 0

    def get_url_from_js(self, qname, kwargs=None, args=None):  # pragma: no cover
        if kwargs is None:
            kwargs = {}
        if args is None:
            args = []
        if USE_NODE_JS:
            shutil.copyfile(GLOBAL_STATIC_DIR/'urls.js', GLOBAL_STATIC_DIR / 'get_url.js')
            accessor_str = ''
            for comp in qname.split(':'):
                accessor_str += f'["{comp}"]'
            with open(GLOBAL_STATIC_DIR / 'get_url.js', 'a+') as tmp_js:
                if args:
                    tmp_js.write(
                        f'\ntry {{'
                        f'\n  console.log(urls{accessor_str}'
                        f'({json.dumps(kwargs, cls=BestEffortEncoder)},'
                        f'{json.dumps(args, cls=BestEffortEncoder)}));\n'
                        f'}} catch (error) {{}}\n'
                    )
                else:
                    tmp_js.write(
                        f'\ntry {{'
                        f'\n  console.log(urls{accessor_str}'
                        f'({json.dumps(kwargs, cls=BestEffortEncoder)}));\n'
                        f'}} catch (error) {{}}\n'
                    )

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
        try:
            return func(kwargs, args)
        except Exception:
            return ''

    def compare(
            self,
            qname,
            kwargs=None,
            args=None,
            object_hook=lambda dct: dct,
            args_hook=lambda args: args
    ):
        if kwargs is None:
            kwargs = {}
        if args is None:
            args = []
        resp = self.client.get(self.get_url_from_js(qname, kwargs, args))

        resp = resp.json(object_hook=object_hook)
        resp['args'] = args_hook(resp['args'])
        self.assertEqual({
                'request': reverse(qname, kwargs=kwargs, args=args),
                'args': args,
                'kwargs': kwargs
            },
            resp
        )

    @staticmethod
    def convert_to_id(dct, key='id'):
        if key in dct:
            dct[key] = uuid.UUID(dct[key])
        return dct

    @staticmethod
    def convert_to_int(dct, key):
        if key in dct:
            dct[key] = int(dct[key])
        return dct

    @staticmethod
    def convert_idx_to_type(arr, idx, typ):
        arr[idx] = typ(arr[idx])
        return arr


@override_settings(STATIC_TEMPLATES={
    'ENGINES': [{
        'BACKEND': 'render_static.backends.StaticDjangoTemplates',
        'OPTIONS': {
            'loaders': [
                ('render_static.loaders.StaticLocMemLoader', {
                    'urls.js': 'var urls = {\n{% urls_to_js es5=True%}};'
                })
            ],
            'builtins': ['render_static.templatetags.render_static']
        },
    }],
})
class URLSToJavascriptTest(URLJavascriptMixin, BaseTestCase):

    def setUp(self):
        self.clear_placeholder_registries()
        placeholders.register_variable_placeholder('strarg', 'a')
        placeholders.register_variable_placeholder('intarg', 0)
        placeholders.register_variable_placeholder('intarg', 0)

        placeholders.register_variable_placeholder('name', 'deadbeef')
        placeholders.register_variable_placeholder('name', 'name1')
        placeholders.register_variable_placeholder('name', 'deadbeef', app_name='app1')

        placeholders.register_unnamed_placeholders('re_path_unnamed', ['adf', 143])
        # repeat for cov
        placeholders.register_unnamed_placeholders('re_path_unnamed', ['adf', 143])
        placeholders.register_unnamed_placeholders(
            're_path_unnamed_solo',
            ['adf', 143],
            app_name='bogus_app'  # this should still work because all placeholders that match any
                                  # criteria are tried
        )
        # repeat for coverage
        placeholders.register_unnamed_placeholders(
            're_path_unnamed_solo',
            ['adf', 143],
            app_name='bogus_app'
        )

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': 'var urls = {\n{% urls_to_js %}};'
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
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

        call_command('render_static', 'urls.js')

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
        self.compare('sub1:app1_detail', {'id': uuid.uuid1()}, object_hook=self.convert_to_id)
        self.compare('sub1:custom_tst', {'year': 2021})
        self.compare('sub1:unreg_conv_tst', {'name': 'name2'})
        self.compare(
            'sub1:re_path_unnamed',
            args=['af', 5678],
            args_hook=lambda arr: self.convert_idx_to_type(arr, 1, int)
        )
        #################################################################

        #################################################################
        # app1 straight include 2
        qname = 'sub2:app1_pth'
        self.compare(qname)
        self.compare(qname, {'arg1': 143})  # emma
        self.compare(qname, {'arg1': 5678, 'arg2': 'xo'})
        self.compare('sub2:app1_detail', {'id': uuid.uuid1()}, object_hook=self.convert_to_id)
        self.compare('sub2:custom_tst', {'year': 1021})
        self.compare('sub2:unreg_conv_tst', {'name': 'name2'})
        self.compare(
            'sub2:re_path_unnamed',
            args=['af', 5678],
            args_hook=lambda arr: self.convert_idx_to_type(arr, 1, int)
        )
        #################################################################

        #################################################################
        # app1 include through app2
        qname = 'app2:app1:app1_pth'
        self.compare(qname)
        self.compare(qname, {'arg1': 1})
        self.compare(qname, {'arg1': 12, 'arg2': 'xo'})
        self.compare('app2:app1:app1_detail', {'id': uuid.uuid1()}, object_hook=self.convert_to_id)
        self.compare('app2:app1:custom_tst', {'year': 2999})
        self.compare('app2:app1:unreg_conv_tst', {'name': 'name1'})
        self.compare(
            'app2:app1:re_path_unnamed',
            args=['af', 5678],
            args_hook=lambda arr: self.convert_idx_to_type(arr, 1, int)
        )
        #################################################################

        #################################################################
        # app2 include w/ app_name namespace
        qname = 'app2:app2_pth'
        self.compare(qname)
        self.compare(qname, {'arg1': 'adf23'})
        self.compare(
            'app2:app2_pth_diff',
            {'arg2': 'this/is/a/path/', 'arg1': uuid.uuid1()},
            object_hook=lambda dct: self.convert_to_id(dct, 'arg1')
        )
        self.compare(
            'app2:app2_pth_diff',
            {'arg2': 'so/is/this', 'arg1': uuid.uuid1()},
            object_hook=lambda dct: self.convert_to_id(dct, 'arg1')
        )
        #################################################################

        #################################################################
        # re_paths

        self.compare('re_path_tst')
        self.compare('re_path_tst', {'strarg': 'DEMOPLY'})
        self.compare(
            're_path_tst',
            {'strarg': 'is', 'intarg': 1337},
            object_hook=lambda dct: self.convert_to_int(dct, 'intarg')
        )

        self.compare(
            're_path_unnamed',
            args=['af', 5678],
            args_hook=lambda arr: self.convert_idx_to_type(arr, 1, int)
        )

        self.compare(
            're_path_unnamed_solo',
            args=['daf', 7120],
            args_hook=lambda arr: self.convert_idx_to_type(arr, 1, int)
        )
        #################################################################

        #################################################################
        # app3 urls - these should be included into the null namespace
        qname = 'app3_i'
        self.compare('app3_idx')
        self.compare('app3_arg', {'arg1': 1})
        self.compare('unreg_conv_tst', {'name': 'name1'})
        #################################################################

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': 'var urls = {\n'
                                   '{% urls_to_js '
                                        'es5=True '
                                        'include=include '
                                        'exclude=exclude '
                                   '%}};'
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }],
        'templates': {
            'urls.js': {
                'context': {
                    'include': [
                        "path_tst",
                        "app2:app1",
                        "sub1:app1_detail",
                        "sub2:app1_pth"
                    ],
                    'exclude': [
                        "app2:app1:custom_tst",
                        "app2:app1:app1_detail",
                        "sub2:app1_pth"
                    ]
                }
            }
        }
    })
    def test_filtering(self):
        self.es5_mode = True
        self.url_js = None

        call_command('render_static', 'urls.js')

        self.assertFalse(self.exists('admin:index'))

        qname = 'path_tst'
        self.assertTrue(self.exists(qname))
        self.assertTrue(self.exists(qname, {'arg1': 1}))
        self.assertTrue(self.exists(qname, {'arg1': 12, 'arg2': 'xo'}))

        self.assertFalse(self.exists('app3_idx'))
        self.assertFalse(self.exists('app3_arg', {'arg1': 1}))

        qname = 'app2:app1:app1_pth'
        self.assertTrue(self.exists(qname))
        self.assertTrue(self.exists(qname, {'arg1': 1}))
        self.assertTrue(self.exists(qname, {'arg1': 12, 'arg2': 'xo'}))
        self.assertFalse(self.exists('app2:app1:app1_detail', {'id': uuid.uuid1()}))
        self.assertFalse(self.exists('app2:app1:custom_tst', {'year': 2999}))

        qname = 'sub1:app1_pth'
        self.assertFalse(self.exists(qname))
        self.assertFalse(self.exists(qname, {'arg1': 143}))  # emma
        self.assertFalse(self.exists(qname, {'arg1': 5678, 'arg2': 'xo'}))
        self.assertTrue(self.exists('sub1:app1_detail', {'id': uuid.uuid1()}))
        self.assertFalse(self.exists('sub1:custom_tst', {'year': 2021}))

        qname = 'sub2:app1_pth'
        self.assertFalse(self.exists(qname))
        self.assertFalse(self.exists(qname, {'arg1': 143}))  # emma
        self.assertFalse(self.exists(qname, {'arg1': 5678, 'arg2': 'xo'}))
        self.assertFalse(self.exists('sub2:app1_detail', {'id': uuid.uuid1()}))
        self.assertFalse(self.exists('sub2:custom_tst', {'year': 1021}))

        qname = 'app2:app2_pth'
        self.assertFalse(self.exists(qname))
        self.assertFalse(self.exists(qname, {'arg1': 'adf23'}))
        self.assertFalse(
            self.exists(
                'app2:app2_pth_diff',
                {'arg2': 'this/is/a/path/', 'arg1': uuid.uuid1()}
            )
        )
        self.assertFalse(
            self.exists(
                'app2:app2_pth_diff',
                {'arg2': 'so/is/this', 'arg1': uuid.uuid1()}
            )
        )

        self.assertFalse(self.exists('re_path_tst'))
        self.assertFalse(self.exists('re_path_tst', {'strarg': 'DEMOPLY'}))
        self.assertFalse(self.exists('re_path_tst', {'strarg': 'is', 'intarg': 1337}))
        self.assertFalse(self.exists('re_path_unnamed', args=['af', 5678]))
        self.assertFalse(self.exists('re_path_unnamed_solo', args=['daf', 7120]))

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': 'var urls = {\n'
                                   '{% urls_to_js '
                                        'es5=True '
                                        'include=include '
                                        'exclude=exclude '
                                   '%}};'
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }],
        'templates': {
            'urls.js': {
                'context': {
                    'exclude': [
                        "admin",
                        "app2:app1:custom_tst",
                        "app2:app1:app1_detail",
                        "sub2:app1_pth"
                    ]
                }
            }
        }
    })
    def test_filtering_excl_only(self):
        self.es5_mode = True
        self.url_js = None

        call_command('render_static', 'urls.js')

        self.assertFalse(self.exists('admin:index'))

        qname = 'path_tst'
        self.assertTrue(self.exists(qname))
        self.assertTrue(self.exists(qname, {'arg1': 1}))
        self.assertTrue(self.exists(qname, {'arg1': 12, 'arg2': 'xo'}))

        self.assertTrue(self.exists('app3_idx'))
        self.assertTrue(self.exists('app3_arg', {'arg1': 1}))

        qname = 'app2:app1:app1_pth'
        self.assertTrue(self.exists(qname))
        self.assertTrue(self.exists(qname, {'arg1': 1}))
        self.assertTrue(self.exists(qname, {'arg1': 12, 'arg2': 'xo'}))
        self.assertFalse(self.exists('app2:app1:app1_detail', {'id': uuid.uuid1()}))
        self.assertFalse(self.exists('app2:app1:custom_tst', {'year': 2999}))

        qname = 'sub1:app1_pth'
        self.assertTrue(self.exists(qname))
        self.assertTrue(self.exists(qname, {'arg1': 143}))  # emma
        self.assertTrue(self.exists(qname, {'arg1': 5678, 'arg2': 'xo'}))
        self.assertTrue(self.exists('sub1:app1_detail', {'id': uuid.uuid1()}))
        self.assertTrue(self.exists('sub1:custom_tst', {'year': 2021}))

        qname = 'sub2:app1_pth'
        self.assertFalse(self.exists(qname))
        self.assertFalse(self.exists(qname, {'arg1': 143}))  # emma
        self.assertFalse(self.exists(qname, {'arg1': 5678, 'arg2': 'xo'}))
        self.assertTrue(self.exists('sub2:app1_detail', {'id': uuid.uuid1()}))
        self.assertTrue(self.exists('sub2:custom_tst', {'year': 1021}))

        qname = 'app2:app2_pth'
        self.assertTrue(self.exists(qname))
        self.assertTrue(self.exists(qname, {'arg1': 'adf23'}))
        self.assertTrue(
            self.exists(
                'app2:app2_pth_diff',
                {'arg2': 'this/is/a/path/', 'arg1': uuid.uuid1()}
            )
        )
        self.assertTrue(
            self.exists(
                'app2:app2_pth_diff',
                {'arg2': 'so/is/this', 'arg1': uuid.uuid1()}
            )
        )

        self.assertTrue(self.exists('re_path_tst'))
        self.assertTrue(self.exists('re_path_tst', {'strarg': 'DEMOPLY'}))
        self.assertTrue(self.exists('re_path_tst', {'strarg': 'is', 'intarg': 1337}))
        self.assertTrue(self.exists('re_path_unnamed', args=['af', 5678]))
        self.assertTrue(self.exists('re_path_unnamed_solo', args=['daf', 7120]))

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': 'var urls = {\n'
                                   '{% urls_to_js '
                                        'url_conf=url_mod '
                                        'include=include '
                                        'exclude=exclude '
                                   '%}};'
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }],
        'templates': {
            'urls.js': {
                'context': {
                    'url_mod': get_url_mod(),
                    'include': [''],
                    'exclude': [
                        "admin",
                        "app2",
                        "sub2",
                        "sub1"
                    ]
                }
            }
        }
    })
    def test_filtering_null_ns_incl(self):
        self.es6_mode = True
        self.url_js = None

        call_command('render_static', 'urls.js')

        self.assertFalse(self.exists('admin:index'))

        qname = 'path_tst'
        self.assertTrue(self.exists(qname))
        self.assertTrue(self.exists(qname, {'arg1': 1}))
        self.assertTrue(self.exists(qname, {'arg1': 12, 'arg2': 'xo'}))

        self.assertTrue(self.exists('app3_idx'))
        self.assertTrue(self.exists('app3_arg', {'arg1': 1}))

        qname = 'app2:app1:app1_pth'
        self.assertFalse(self.exists(qname))
        self.assertFalse(self.exists(qname, {'arg1': 1}))
        self.assertFalse(self.exists(qname, {'arg1': 12, 'arg2': 'xo'}))
        self.assertFalse(self.exists('app2:app1:app1_detail', {'id': uuid.uuid1()}))
        self.assertFalse(self.exists('app2:app1:custom_tst', {'year': 2999}))

        qname = 'sub1:app1_pth'
        self.assertFalse(self.exists(qname))
        self.assertFalse(self.exists(qname, {'arg1': 143}))  # emma
        self.assertFalse(self.exists(qname, {'arg1': 5678, 'arg2': 'xo'}))
        self.assertFalse(self.exists('sub1:app1_detail', {'id': uuid.uuid1()}))
        self.assertFalse(self.exists('sub1:custom_tst', {'year': 2021}))

        qname = 'sub2:app1_pth'
        self.assertFalse(self.exists(qname))
        self.assertFalse(self.exists(qname, {'arg1': 143}))  # emma
        self.assertFalse(self.exists(qname, {'arg1': 5678, 'arg2': 'xo'}))
        self.assertFalse(self.exists('sub2:app1_detail', {'id': uuid.uuid1()}))
        self.assertFalse(self.exists('sub2:custom_tst', {'year': 1021}))

        qname = 'app2:app2_pth'
        self.assertFalse(self.exists(qname))
        self.assertFalse(self.exists(qname, {'arg1': 'adf23'}))
        self.assertFalse(
            self.exists(
                'app2:app2_pth_diff',
                {'arg2': 'this/is/a/path/', 'arg1': uuid.uuid1()}
            )
        )
        self.assertFalse(
            self.exists(
                'app2:app2_pth_diff',
                {'arg2': 'so/is/this', 'arg1': uuid.uuid1()}
            )
        )

        self.assertTrue(self.exists('re_path_tst'))
        self.assertTrue(self.exists('re_path_tst', {'strarg': 'DEMOPLY'}))
        self.assertTrue(self.exists('re_path_tst', {'strarg': 'is', 'intarg': 1337}))
        self.assertTrue(self.exists('re_path_unnamed', args=['af', 5678]))
        self.assertTrue(self.exists('re_path_unnamed_solo', args=['daf', 7120]))


    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': 'var urls = {\n'
                                   '{% urls_to_js '
                                        'url_conf="render_static.tests.urls" '
                                        'include=include '
                                        'exclude=exclude '
                                   '%}};'
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }],
        'templates': {
            'urls.js': {
                'context': {
                    'include': ['path_tst']
                }
            }
        }
    })
    def test_top_lvl_ns_incl(self):
        self.es6_mode = True
        self.url_js = None

        call_command('render_static', 'urls.js')

        self.assertFalse(self.exists('admin:index'))

        qname = 'path_tst'
        self.assertTrue(self.exists(qname))
        self.assertTrue(self.exists(qname, {'arg1': 1}))
        self.assertTrue(self.exists(qname, {'arg1': 12, 'arg2': 'xo'}))

        self.assertFalse(self.exists('app3_idx'))
        self.assertFalse(self.exists('app3_arg', {'arg1': 1}))

        qname = 'app2:app1:app1_pth'
        self.assertFalse(self.exists(qname))
        self.assertFalse(self.exists(qname, {'arg1': 1}))
        self.assertFalse(self.exists(qname, {'arg1': 12, 'arg2': 'xo'}))
        self.assertFalse(self.exists('app2:app1:app1_detail', {'id': uuid.uuid1()}))
        self.assertFalse(self.exists('app2:app1:custom_tst', {'year': 2999}))

        qname = 'sub1:app1_pth'
        self.assertFalse(self.exists(qname))
        self.assertFalse(self.exists(qname, {'arg1': 143}))  # emma
        self.assertFalse(self.exists(qname, {'arg1': 5678, 'arg2': 'xo'}))
        self.assertFalse(self.exists('sub1:app1_detail', {'id': uuid.uuid1()}))
        self.assertFalse(self.exists('sub1:custom_tst', {'year': 2021}))

        qname = 'sub2:app1_pth'
        self.assertFalse(self.exists(qname))
        self.assertFalse(self.exists(qname, {'arg1': 143}))  # emma
        self.assertFalse(self.exists(qname, {'arg1': 5678, 'arg2': 'xo'}))
        self.assertFalse(self.exists('sub2:app1_detail', {'id': uuid.uuid1()}))
        self.assertFalse(self.exists('sub2:custom_tst', {'year': 1021}))

        qname = 'app2:app2_pth'
        self.assertFalse(self.exists(qname))
        self.assertFalse(self.exists(qname, {'arg1': 'adf23'}))
        self.assertFalse(
            self.exists(
                'app2:app2_pth_diff',
                {'arg2': 'this/is/a/path/', 'arg1': uuid.uuid1()}
            )
        )
        self.assertFalse(
            self.exists(
                'app2:app2_pth_diff',
                {'arg2': 'so/is/this', 'arg1': uuid.uuid1()}
            )
        )

        self.assertFalse(self.exists('re_path_tst'))
        self.assertFalse(self.exists('re_path_tst', {'strarg': 'DEMOPLY'}))
        self.assertFalse(self.exists('re_path_tst', {'strarg': 'is', 'intarg': 1337}))
        self.assertFalse(self.exists('re_path_unnamed', args=['af', 5678]))
        self.assertFalse(self.exists('re_path_unnamed_solo', args=['daf', 7120]))

    # uncomment to not delete generated js
    #def tearDown(self):
    #    pass


class URLSToJavascriptOffNominalTest(URLJavascriptMixin, BaseTestCase):

    def setUp(self):
        self.clear_placeholder_registries()

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': 'var urls = {\n{% urls_to_js include=include %}};'
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }],
        'templates': {
            'urls.js': {
                'context': {
                    'include': ['unreg_conv_tst'],
                }
            }
        }
    })
    def test_no_placeholders(self):

        self.es6_mode = True
        self.url_js = None

        # this works even though its registered against a different app
        # all placeholders that match at least one criteria are tried
        self.assertRaises(CommandError, lambda: call_command('render_static', 'urls.js'))
        placeholders.register_variable_placeholder('name', 'name1', app_name='app1')
        placeholders.register_variable_placeholder('name', 'name1', app_name='app1')
        call_command('render_static', 'urls.js')
        self.compare('unreg_conv_tst', {'name': 'name1'})

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': 'var urls = {\n{% urls_to_js include=include %}};'
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }],
        'templates': {
            'urls.js': {
                'context': {
                    'include': ['sub1:re_path_unnamed'],
                }
            }
        }
    })
    def test_no_unnamed_placeholders(self):

        self.assertRaises(CommandError, lambda: call_command('render_static', 'urls.js'))
        placeholders.register_unnamed_placeholders('re_path_unnamed', [143, 'adf'])  # shouldnt work
        placeholders.register_unnamed_placeholders('re_path_unnamed', ['adf', 143])  # but this will
        call_command('render_static', 'urls.js')
        self.compare(
            'sub1:re_path_unnamed',
            args=['af', 5678],
            args_hook=lambda arr: self.convert_idx_to_type(arr, 1, int)
        )

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': 'var urls = {\n{% urls_to_js include=include %}};'
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }],
        'templates': {
            'urls.js': {
                'context': {
                    'include': ['sub1:re_path_unnamed'],
                }
            }
        }
    })
    def test_bad_only_bad_unnamed_placeholders(self):

        placeholders.register_unnamed_placeholders('re_path_unnamed', [])  # shouldnt work
        self.assertRaises(CommandError, lambda: call_command('render_static', 'urls.js'))

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': 'var urls = {\n{% urls_to_js url_conf=url_mod %}};'
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }],
        'templates': {
            'urls.js': {
                'context': {
                    'url_mod': placeholders,
                }
            }
        }
    })
    def test_no_urlpatterns(self):
        self.assertRaises(CommandError, lambda: call_command('render_static', 'urls.js'))

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': 'var urls = {\n{% urls_to_js url_conf=url_mod %}};'
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }],
        'templates': {
            'urls.js': {
                'context': {
                    'url_mod': bad_pattern,
                }
            }
        }
    })
    def test_unknown_pattern(self):
        self.assertRaises(CommandError, lambda: call_command('render_static', 'urls.js'))

    def test_register_bogus_converter(self):
        from render_static import placeholders as gen
        self.assertRaises(
            ValueError,
            lambda: placeholders.register_converter_placeholder('Not a converter type!', 1234)
        )

    # uncomment to not delete generated js
    #def tearDown(self):
    #    pass
