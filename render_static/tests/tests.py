import filecmp
import inspect
import json
import os
import shutil
import subprocess
import traceback
import uuid
from pathlib import Path
from time import perf_counter
import pickle

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
from django.urls.exceptions import NoReverseMatch
from django.utils.module_loading import import_string
from render_static import placeholders, resolve_context, resource
from render_static.backends import StaticDjangoTemplates, StaticJinja2Templates
from render_static.engine import StaticTemplateEngine
from render_static.exceptions import InvalidContext
from render_static.javascript import JavaScriptGenerator
from render_static.loaders.jinja2 import StaticFileSystemLoader
from render_static.origin import AppOrigin, Origin
from render_static.tests import bad_pattern, defines
from render_static.url_tree import ClassURLWriter

APP1_STATIC_DIR = Path(__file__).parent / 'app1' / 'static'  # this dir does not exist and must be cleaned up
APP2_STATIC_DIR = Path(__file__).parent / 'app2' / 'static'  # this dir exists and is checked in
GLOBAL_STATIC_DIR = settings.STATIC_ROOT  # this dir does not exist and must be cleaned up
STATIC_TEMP_DIR = Path(__file__).parent / 'static_templates'
STATIC_TEMP_DIR2 = Path(__file__).parent / 'static_templates2'
EXPECTED_DIR = Path(__file__).parent / 'expected'

BAD_PICKLE = Path(__file__).parent / 'resources' / 'bad.pickle'
NOT_A_DICT_PICKLE = Path(__file__).parent / 'resources' / 'not_a_dict.pickle'
CONTEXT_PICKLE = Path(__file__).parent / 'resources' / 'context.pickle'

USE_NODE_JS = True if shutil.which('node') else False


def empty_or_dne(directory):
    if os.path.exists(str(directory)):
        return len(os.listdir(directory)) == 0
    return True


class BadVisitor:
    pass


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
        from render_static.management.commands.renderstatic import get_parser
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
        APP2_STATIC_DIR / 'app2',
        APP2_STATIC_DIR / 'exclusive'
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
        call_command('renderstatic', 'app1/html/nominal1.html')
        self.assertEqual(len(os.listdir(APP1_STATIC_DIR)), 1)
        self.assertTrue(not APP2_STATIC_DIR.exists() or len(os.listdir(APP2_STATIC_DIR)) == 0)
        self.assertTrue(filecmp.cmp(
            APP1_STATIC_DIR / 'app1' / 'html' / 'nominal1.html',
            EXPECTED_DIR / 'nominal1.html',
            shallow=False
        ))
        call_command('renderstatic', 'app1/html/nominal2.html')
        self.assertEqual(len(os.listdir(APP1_STATIC_DIR)), 1)
        self.assertEqual(len(os.listdir(APP2_STATIC_DIR)), 1)
        self.assertTrue(filecmp.cmp(
            APP2_STATIC_DIR / 'app1' / 'html' / 'nominal2.html',
            EXPECTED_DIR / 'nominal2.html',
            shallow=False
        ))

    # def tearDown(self):
    #     pass


def generate_context1():
    return {
        'to': 'world',
        'punc': '!'
    }


def generate_context2():
    return {
        'greeting': 'Hello',
        'to': 'World'
    }


def invalid_context_return():
    return ['garbage']


@override_settings(STATIC_TEMPLATES={
    'context': 'tests.generate_context1',
    'templates': {
        'app1/html/hello.html': {
            'context': generate_context2,
        }
    }
})
class CallableContextTestCase(BaseTestCase):
    """
    Tests that show callable contexts work as expected.
    """
    def test_nominal_generate(self):
        call_command('renderstatic')
        self.assertTrue(filecmp.cmp(
            APP1_STATIC_DIR / 'app1' / 'html' / 'hello.html',
            EXPECTED_DIR / 'ctx_override.html',
            shallow=False
        ))

    @override_settings(STATIC_TEMPLATES={
        'templates': {
            'app1/html/hello.html': {
                'context': 'does.not.exist'
            }
        }
    })
    def test_off_nominal_tmpl(self):
        self.assertRaises(ImproperlyConfigured, lambda: call_command('renderstatic'))
        
    @override_settings(STATIC_TEMPLATES={
        'context': invalid_context_return,
        'templates': {
            'app1/html/hello.html': {}
        }
    })
    def test_off_nominal_global(self):
        self.assertRaises(CommandError, lambda: call_command('renderstatic'))

    #def tearDown(self):
    #    pass


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
    Tests that per template contexts override global contexts and that the global context is also
    used.
    """
    def test_generate(self):
        call_command('renderstatic')
        self.assertTrue(filecmp.cmp(
            APP1_STATIC_DIR / 'app1' / 'html' / 'hello.html',
            EXPECTED_DIR / 'ctx_override.html',
            shallow=False
        ))


@override_settings(STATIC_TEMPLATES={
    'context': {
        'title': 'TEST'
    },
    'templates': {
        'app1/html/inheritance.html': {}
    }
})
class TemplateInheritanceTestCase(BaseTestCase):
    """
    Tests that template inheritance is working correctly. Static templates lightly touches the
    template engines so its not impossible that template resolution could be effected.
    """

    def test_django_templates(self):
        """
        Tests that template inheritance is working for the static django template engine.
        """
        call_command('renderstatic')
        self.assertTrue(filecmp.cmp(
            APP2_STATIC_DIR / 'app1' / 'html' / 'inheritance.html',
            EXPECTED_DIR / 'inheritance.html',
            shallow=False
        ))

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticJinja2Templates',
            'APP_DIRS': True
        }],
        'templates': {
            'app2/html/inheritance.html': {}
        }
    })
    def test_jinja2_templates(self):
        """
        Tests that template inheritance is working for the static Jinja2 template engine.
        """
        call_command('renderstatic')
        self.assertTrue(filecmp.cmp(
            APP2_STATIC_DIR / 'app2' / 'html' / 'inheritance.html',
            EXPECTED_DIR / 'inheritance_jinja2.html',
            shallow=False
        ))


@override_settings(STATIC_TEMPLATES={
    'ENGINES': [{
        'BACKEND': 'render_static.backends.StaticDjangoTemplates',
        'DIRS': [STATIC_TEMP_DIR],
        'OPTIONS': {
            'loaders': [
                'render_static.loaders.StaticFilesystemBatchLoader',
                'render_static.loaders.StaticAppDirectoriesBatchLoader'
            ]
        },
    }]
})
class BatchFileSystemRenderTestCase(BaseTestCase):
    """
    Tests that exercise the batch template loaders.
    """

    def test_batch_filesystem_render1(self):
        call_command('renderstatic', 'batch_fs*')
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'batch_fs_test0.html',
            EXPECTED_DIR / 'nominal_fs.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'batch_fs_test1.html',
            EXPECTED_DIR / 'nominal_fs.html',
            shallow=False
        ))
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR)), 2)

    def test_batch_filesystem_render2(self):
        call_command('renderstatic', '**/batch_fs*')
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'batch_fs_test0.html',
            EXPECTED_DIR / 'nominal_fs.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'batch_fs_test1.html',
            EXPECTED_DIR / 'nominal_fs.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'subdir' / 'batch_fs_test2.html',
            EXPECTED_DIR / 'nominal1.html',
            shallow=False
        ))
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR)), 3)

    # def tearDown(self):
    #    pass


@override_settings(STATIC_TEMPLATES={
    'ENGINES': [{
        'BACKEND': 'render_static.backends.StaticDjangoTemplates',
        'DIRS': [STATIC_TEMP_DIR, STATIC_TEMP_DIR2],
        'OPTIONS': {
            'loaders': [
                'render_static.loaders.StaticFilesystemBatchLoader',
                'render_static.loaders.StaticAppDirectoriesBatchLoader'
            ]
        },
    }]
})
class TemplatePreferenceFSTestCase(BaseTestCase):
    """
    Tests that load preferences flag works as described and that destinations also work as
    described:

        - first_loader
        - first_preference

    Do the right files get picked and do they go to the expected locations?
    """

    def test_nopref(self):
        call_command('renderstatic', 'exclusive/*')
        self.validate_nopref()

    def validate_nopref(self):
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template1.html',
            EXPECTED_DIR / 'glb_template1.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template2.html',
            EXPECTED_DIR / 'glb_template2.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template3.html',
            EXPECTED_DIR / 'glb_template3.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template4.html',
            EXPECTED_DIR / 'glb2_template4.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            APP2_STATIC_DIR / 'exclusive' / 'template5.html',
            EXPECTED_DIR / 'app2_template5.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            APP1_STATIC_DIR / 'exclusive' / 'template6.html',
            EXPECTED_DIR / 'app1_template6.html',
            shallow=False
        ))
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR / 'exclusive')), 4)
        self.assertEqual(len(os.listdir(APP2_STATIC_DIR / 'exclusive')), 1)
        self.assertEqual(len(os.listdir(APP1_STATIC_DIR / 'exclusive')), 1)

    def test_first_loader(self):
        call_command('renderstatic', 'exclusive/*', first_loader=True)
        self.validate_first_loader()

    def validate_first_loader(self):
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template1.html',
            EXPECTED_DIR / 'glb_template1.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template2.html',
            EXPECTED_DIR / 'glb_template2.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template3.html',
            EXPECTED_DIR / 'glb_template3.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template4.html',
            EXPECTED_DIR / 'glb2_template4.html',
            shallow=False
        ))
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR / 'exclusive')), 4)
        self.assertTrue(empty_or_dne(APP1_STATIC_DIR))
        self.assertTrue(empty_or_dne(APP2_STATIC_DIR))

    def test_first_pref(self):
        call_command('renderstatic', 'exclusive/*', first_preference=True)
        self.validate_first_pref()

    def validate_first_pref(self):
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template1.html',
            EXPECTED_DIR / 'glb_template1.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template2.html',
            EXPECTED_DIR / 'glb_template2.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template3.html',
            EXPECTED_DIR / 'glb_template3.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            APP1_STATIC_DIR / 'exclusive' / 'template6.html',
            EXPECTED_DIR / 'app1_template6.html',
            shallow=False
        ))
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR / 'exclusive')), 3)
        self.assertEqual(len(os.listdir(APP1_STATIC_DIR / 'exclusive')), 1)
        self.assertTrue(empty_or_dne(APP2_STATIC_DIR))

    def test_first_loader_and_pref(self):
        call_command('renderstatic', 'exclusive/*', first_loader=True, first_preference=True)
        self.validate_first_load_and_pref()

    def validate_first_load_and_pref(self):
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template1.html',
            EXPECTED_DIR / 'glb_template1.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template2.html',
            EXPECTED_DIR / 'glb_template2.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template3.html',
            EXPECTED_DIR / 'glb_template3.html',
            shallow=False
        ))
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR / 'exclusive')), 3)
        self.assertTrue(empty_or_dne(APP1_STATIC_DIR))
        self.assertTrue(empty_or_dne(APP2_STATIC_DIR))

    def test_batch_destination_override(self):
        call_command('renderstatic', 'exclusive/*', destination=GLOBAL_STATIC_DIR)
        self.validate_batch_destination_override()

    def validate_batch_destination_override(self):
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template1.html',
            EXPECTED_DIR / 'glb_template1.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template2.html',
            EXPECTED_DIR / 'glb_template2.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template3.html',
            EXPECTED_DIR / 'glb_template3.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template4.html',
            EXPECTED_DIR / 'glb2_template4.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template5.html',
            EXPECTED_DIR / 'app2_template5.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template6.html',
            EXPECTED_DIR / 'app1_template6.html',
            shallow=False
        ))
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR / 'exclusive')), 6)

    # def tearDown(self):
    #    pass


@override_settings(STATIC_TEMPLATES={
    'ENGINES': [{
        'BACKEND': 'render_static.backends.StaticDjangoTemplates',
        'DIRS': [STATIC_TEMP_DIR, STATIC_TEMP_DIR2],
        'OPTIONS': {
            'loaders': [
                'render_static.loaders.StaticAppDirectoriesBatchLoader',
                'render_static.loaders.StaticFilesystemBatchLoader'
            ]
        },
    }]
})
class TemplatePreferenceAPPSTestCase(BaseTestCase):
    """
    Tests that load preferences flag works as described and that destinations also work as
    described, for the app directories loader.

        - first_loader
        - first_preference

    Do the right files get picked and do they go to the expected locations?
    """

    def test_nopref(self):
        call_command('renderstatic', 'exclusive/*')
        self.validate_nopref()

    def validate_nopref(self):
        self.assertTrue(filecmp.cmp(
            APP1_STATIC_DIR / 'exclusive' / 'template1.html',
            EXPECTED_DIR / 'app1_template1.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            APP2_STATIC_DIR / 'exclusive' / 'template2.html',
            EXPECTED_DIR / 'app2_template2.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template3.html',
            EXPECTED_DIR / 'glb_template3.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template4.html',
            EXPECTED_DIR / 'glb2_template4.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            APP2_STATIC_DIR / 'exclusive' / 'template5.html',
            EXPECTED_DIR / 'app2_template5.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            APP1_STATIC_DIR / 'exclusive' / 'template6.html',
            EXPECTED_DIR / 'app1_template6.html',
            shallow=False
        ))
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR / 'exclusive')), 2)
        self.assertEqual(len(os.listdir(APP2_STATIC_DIR / 'exclusive')), 2)
        self.assertEqual(len(os.listdir(APP1_STATIC_DIR / 'exclusive')), 2)

    def test_first_loader(self):
        call_command('renderstatic', 'exclusive/*', first_loader=True)
        self.validate_first_loader()

    def validate_first_loader(self):
        self.assertTrue(filecmp.cmp(
            APP1_STATIC_DIR / 'exclusive' / 'template1.html',
            EXPECTED_DIR / 'app1_template1.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            APP2_STATIC_DIR / 'exclusive' / 'template2.html',
            EXPECTED_DIR / 'app2_template2.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            APP2_STATIC_DIR / 'exclusive' / 'template5.html',
            EXPECTED_DIR / 'app2_template5.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            APP1_STATIC_DIR / 'exclusive' / 'template6.html',
            EXPECTED_DIR / 'app1_template6.html',
            shallow=False
        ))
        self.assertEqual(len(os.listdir(APP1_STATIC_DIR / 'exclusive')), 2)
        self.assertEqual(len(os.listdir(APP2_STATIC_DIR / 'exclusive')), 2)
        self.assertTrue(empty_or_dne(GLOBAL_STATIC_DIR))

    def test_first_pref(self):
        call_command('renderstatic', 'exclusive/*', first_preference=True)
        self.validate_first_pref()

    def validate_first_pref(self):
        self.assertTrue(filecmp.cmp(
            APP1_STATIC_DIR / 'exclusive' / 'template1.html',
            EXPECTED_DIR / 'app1_template1.html',
            shallow=False
        ))

        # app2's template is resolved because selection criteria only counts for resolving template
        # names, so template2.html is picked - but then when the template name is resolved to a file
        # the app loader has precedence and picks the app2 template over the filesystem one.
        # this is expected, if a little confusing - these options are for corner cases anyway.
        self.assertTrue(filecmp.cmp(
            APP2_STATIC_DIR / 'exclusive' / 'template2.html',
            EXPECTED_DIR / 'app2_template2.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template3.html',
            EXPECTED_DIR / 'glb_template3.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            APP1_STATIC_DIR / 'exclusive' / 'template6.html',
            EXPECTED_DIR / 'app1_template6.html',
            shallow=False
        ))
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR / 'exclusive')), 1)
        self.assertEqual(len(os.listdir(APP1_STATIC_DIR / 'exclusive')), 2)
        self.assertEqual(len(os.listdir(APP2_STATIC_DIR / 'exclusive')), 1)

    def test_first_loader_and_pref(self):
        call_command('renderstatic', 'exclusive/*', first_loader=True, first_preference=True)
        self.validate_first_load_and_pref()

    def validate_first_load_and_pref(self):
        self.assertTrue(filecmp.cmp(
            APP1_STATIC_DIR / 'exclusive' / 'template1.html',
            EXPECTED_DIR / 'app1_template1.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            APP1_STATIC_DIR / 'exclusive' / 'template6.html',
            EXPECTED_DIR / 'app1_template6.html',
            shallow=False
        ))
        self.assertEqual(len(os.listdir(APP1_STATIC_DIR / 'exclusive')), 2)
        self.assertTrue(empty_or_dne(GLOBAL_STATIC_DIR))
        self.assertTrue(empty_or_dne(APP2_STATIC_DIR))

    def test_batch_destination_override(self):
        call_command('renderstatic', 'exclusive/*', destination=GLOBAL_STATIC_DIR)
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template1.html',
            EXPECTED_DIR / 'app1_template1.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template2.html',
            EXPECTED_DIR / 'app2_template2.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template3.html',
            EXPECTED_DIR / 'glb_template3.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template4.html',
            EXPECTED_DIR / 'glb2_template4.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template5.html',
            EXPECTED_DIR / 'app2_template5.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template6.html',
            EXPECTED_DIR / 'app1_template6.html',
            shallow=False
        ))
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR / 'exclusive')), 6)

    # def tearDown(self):
    #     pass


@override_settings(STATIC_TEMPLATES={
    'ENGINES': [{
        'BACKEND': 'render_static.backends.StaticDjangoTemplates',
        'NAME': 'Engine0',
        'OPTIONS': {
            'loaders': [
                'render_static.loaders.StaticAppDirectoriesBatchLoader'
            ]
        },
    }, {
        'BACKEND': 'render_static.backends.StaticDjangoTemplates',
        'NAME': 'Engine1',
        'DIRS': [STATIC_TEMP_DIR, STATIC_TEMP_DIR2],
        'OPTIONS': {
            'loaders': [
                'render_static.loaders.StaticFilesystemBatchLoader'
            ]
        },
    }]
})
class TemplateEnginePreferenceTestCase(TemplatePreferenceAPPSTestCase):
    """
    Tests that load preferences flag works as described and that destinations also work as
    described, for multiple engines.

        - first_engine
        - first_loader
        - first_preference

    Do the right files get picked and do they go to the expected locations?
    """

    def test_nopref(self):
        call_command('renderstatic', 'exclusive/*')
        self.validate_nopref()

    def test_first_loader(self):
        call_command('renderstatic', 'exclusive/*', first_engine=True)
        self.validate_first_loader()

    def test_first_pref(self):
        call_command('renderstatic', 'exclusive/*', first_preference=True)
        self.validate_first_pref()

    def validate_first_pref(self):
        self.assertTrue(filecmp.cmp(
            APP1_STATIC_DIR / 'exclusive' / 'template1.html',
            EXPECTED_DIR / 'app1_template1.html',
            shallow=False
        ))

        # I don't understand why the file system one is picked, but this is corner case behavior
        # and it only really matters that this remains consistent
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template2.html',
            EXPECTED_DIR / 'glb_template2.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'exclusive' / 'template3.html',
            EXPECTED_DIR / 'glb_template3.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            APP1_STATIC_DIR / 'exclusive' / 'template6.html',
            EXPECTED_DIR / 'app1_template6.html',
            shallow=False
        ))
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR / 'exclusive')), 2)
        self.assertEqual(len(os.listdir(APP1_STATIC_DIR / 'exclusive')), 2)
        self.assertTrue(empty_or_dne(APP2_STATIC_DIR))

    def test_first_loader_and_pref(self):
        call_command('renderstatic', 'exclusive/*', first_engine=True, first_preference=True)
        self.validate_first_load_and_pref()

    # def tearDown(self):
    #    pass


@override_settings(STATIC_TEMPLATES={
    'ENGINES': [{
        'BACKEND': 'render_static.backends.StaticJinja2Templates',
        'DIRS': [STATIC_TEMP_DIR, STATIC_TEMP_DIR2],
        'APP_DIRS': True,
        'OPTIONS': {
            'app_dir': 'static_templates'
        },
    }]
})
class TemplatePreferenceJinjaTestCase(TemplatePreferenceFSTestCase):
    """
    This config should be almost functionality equivalent to the base tests. The template dont have
    any actual template logic in them so jinja2 will render them as well.

    The main difference is that there's only one loader so first_loader doesnt do anything and
    first_pref is the same as having both flags set.
    """

    def validate_first_pref(self):
        self.validate_first_load_and_pref()

    def validate_first_loader(self):
        self.validate_nopref()

    # def tearDown(self):
    #    pass


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
    Tests that destination can be overridden for app directory loaded templates and that dest can be
    a string path
    """
    def test_generate(self):
        call_command('renderstatic')
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
        call_command('renderstatic', 'nominal_fs.html', 'nominal_fs2.html')
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
        'nominal.jinja2': {
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
        call_command('renderstatic')
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
            'OPTIONS': {
                'loader': StaticFileSystemLoader(STATIC_TEMP_DIR)
            }
        }],
        'templates': {
            'nominal.jinja2': {
                'dest': GLOBAL_STATIC_DIR / 'nominal_jinja2.html'
            }
        }
    })
    def test_fs_loader(self):
        call_command('renderstatic')
        self.assertTrue(empty_or_dne(APP1_STATIC_DIR))
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR)), 1)
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'nominal_jinja2.html',
            EXPECTED_DIR / 'nominal_jinja2.html',
            shallow=False
        ))
        self.assertRaises(CommandError, lambda: call_command('renderstatic', 'bogus.tmpl'))


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
        call_command('renderstatic')
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
            engine['StaticDjangoTemplates'].engine.loaders,
            ['render_static.loaders.StaticFilesystemLoader']
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
            'context': [0]
        })
        self.assertRaises(ImproperlyConfigured, lambda: engine.context)

        engine = StaticTemplateEngine({
            'templates': {
                'nominal_fs.html': {
                    'dest': GLOBAL_STATIC_DIR / 'nominal_fs.html',
                    'context': [0]
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

    @override_settings(
        STATIC_ROOT=None,
        STATIC_TEMPLATES={
            'ENGINES': [{
                'BACKEND': 'render_static.backends.StaticDjangoTemplates',
                'DIRS': [STATIC_TEMP_DIR],
                'OPTIONS': {
                    'loaders': [
                        'render_static.loaders.StaticFilesystemBatchLoader'
                    ]
                },
            }]
        }
    )
    def test_no_destination(self):
        """
        If no  setting is present we should raise.
        """
        self.assertRaises(
            CommandError,
            lambda: call_command('renderstatic', 'nominal_fs.html')
        )

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

    def test_suspicious_selector_fs(self):
        engine = StaticTemplateEngine({
            'ENGINES': [{
                'BACKEND': 'render_static.backends.StaticDjangoTemplates',
                'DIRS': [STATIC_TEMP_DIR],
                'OPTIONS': {
                    'loaders': [
                        'render_static.loaders.StaticFilesystemBatchLoader'
                    ]
                },
            }]
        })
        self.assertRaises(
            TemplateDoesNotExist,
            lambda: engine.render_to_disk('../static_templates2/exclusive/template1.html')
        )

    def test_suspicious_selector_appdirs(self):
        engine = StaticTemplateEngine({
            'ENGINES': [{
                'BACKEND': 'render_static.backends.StaticDjangoTemplates',
                'OPTIONS': {
                    'loaders': [
                        'render_static.loaders.StaticAppDirectoriesBatchLoader'
                    ]
                },
            }]
        })
        self.assertRaises(
            TemplateDoesNotExist,
            lambda: engine.render_to_disk('../custom_templates/nominal_fs.html')
        )

    def test_suspicious_selector_jinja2_appdirs(self):
        engine = StaticTemplateEngine({
            'ENGINES': [{
                'BACKEND': 'render_static.backends.StaticJinja2Templates',
                'APP_DIRS': True
            }]
        })
        self.assertRaises(
            TemplateDoesNotExist,
            lambda: engine.render_to_disk('../custom_templates/nominal_fs.html')
        )

    def test_no_selector_templates_found(self):
        engine = StaticTemplateEngine({
            'ENGINES': [{
                'BACKEND': 'render_static.backends.StaticDjangoTemplates',
                'OPTIONS': {
                    'loaders': [
                        'render_static.loaders.StaticAppDirectoriesBatchLoader'
                    ]
                },
            }]
        })
        self.assertRaises(
            TemplateDoesNotExist,
            lambda: engine.render_to_disk('*.css')
        )

    # def tearDown(self):
    #     pass


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
        self.assertRaises(CommandError, lambda: call_command('renderstatic'))

    def test_render_default_static_root(self):
        call_command('renderstatic')
        self.assertTrue(filecmp.cmp(
            settings.STATIC_ROOT / 'nominal_fs.html',
            EXPECTED_DIR / 'nominal_fs.html',
            shallow=False
        ))

    def test_render_missing(self):
        self.assertRaises(
            CommandError,
            lambda: call_command('renderstatic', 'this/template/doesnt/exist.html')
        )


class GenerateNothing(BaseTestCase):

    def generate_nothing(self):
        """
        When no templates are configured, render_static should generate nothing and it should not
        raise
        """
        call_command('renderstatic')
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
        self.assertRaises(ImproperlyConfigured, lambda: call_command('renderstatic'))


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
        call_command('renderstatic', 'defines1.js')
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
        call_command('renderstatic', 'defines2.js')
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
        self.assertRaises(CommandError, lambda: call_command('renderstatic', 'defines_error.js'))

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
        call_command('renderstatic', 'defines1.js', 'defines2.js')
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

    # def tearDown(self):
    #     pass


class URLJavascriptMixin:

    url_js = None
    es5_mode = False
    class_mode = None
    legacy_args = False

    def clear_placeholder_registries(self):
        from importlib import reload
        reload(placeholders)

    def exists(self, *args, **kwargs):
        return len(self.get_url_from_js(*args, **kwargs)) > 0

    class TestJSGenerator(JavaScriptGenerator):

        class_mode = None
        legacy_args = False  # generate code that uses separate arguments to js reverse calls
        catch = True

        def __init__(self, class_mode=None, catch=True, legacy_args=False, **kwargs):
            self.class_mode = class_mode
            self.catch = catch
            self.legacy_args = legacy_args
            super().__init__(**kwargs)

        def generate(self, qname, kwargs=None, args=None, query=None):
            def do_gen():
                yield 'try {' if self.catch else ''
                self.indent()
                if self.class_mode:
                    yield f'const urls = new {self.class_mode}();'
                    yield 'console.log('
                    self.indent()
                    yield f'urls.reverse('
                    self.indent()
                    yield f'"{qname}",{"" if self.legacy_args else " {"}'
                else:
                    accessor_str = ''.join([f'["{comp}"]' for comp in qname.split(':')])
                    yield 'console.log('
                    self.indent()
                    yield f'urls{accessor_str}({"" if self.legacy_args else "{"}'
                    self.indent()
                yield f'{"" if self.legacy_args else "kwargs: "}' \
                      f'{json.dumps(kwargs, cls=BestEffortEncoder)}{"," if args or query else ""}'
                if args:
                    yield f'{"" if self.legacy_args else "args: "}' \
                          f'{json.dumps(args, cls=BestEffortEncoder)}{"," if query else ""}'
                if query:
                    yield f'{"" if self.legacy_args else "query: "}' \
                          f'{json.dumps(query, cls=BestEffortEncoder)}'
                self.outdent(2)
                yield f'{"" if self.legacy_args else "}"}));'
                if self.catch:
                    self.outdent()
                    yield '} catch (error) {}'

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
            url_path=GLOBAL_STATIC_DIR / 'urls.js'
    ):  # pragma: no cover
        if kwargs is None:
            kwargs = {}
        if args is None:
            args = []
        if query is None:
            query = {}
        if js_generator is None:
            js_generator = URLJavascriptMixin.TestJSGenerator(
                self.class_mode,
                legacy_args=self.legacy_args
            )
        tmp_file_pth = GLOBAL_STATIC_DIR / f'get_{url_path.stem}.js'

        if USE_NODE_JS:
            shutil.copyfile(url_path, tmp_file_pth)
            with open(tmp_file_pth, 'a+') as tmp_js:
                for line in js_generator.generate(qname, kwargs, args, query):
                    tmp_js.write(f'{line}')
            try:
                return subprocess.check_output([
                    'node',
                    tmp_file_pth
                ], stderr=subprocess.STDOUT).decode('UTF-8').strip()
            except subprocess.CalledProcessError as cp_err:
                if cp_err.stderr:
                    return cp_err.stderr.decode('UTF-8').strip()
                elif cp_err.output:
                    return cp_err.output.decode('UTF-8').strip()
                elif cp_err.stdout:
                    return cp_err.stdout.decode('UTF-8').strip()
                return ''

        if self.url_js is None:
            with open(url_path, 'r') as jf:
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
                            Use only for tiny scripts! Importing babel.py for the first time - this
                            can take some time. Please note that currently Javascript 6 in Js2Py is
                            unstable and slow. Use only for tiny scripts!'
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
            query=None,
            object_hook=lambda dct: dct,
            args_hook=lambda args: args,
            url_path=GLOBAL_STATIC_DIR / 'urls.js'
    ):
        if kwargs is None:
            kwargs = {}
        if args is None:
            args = []
        if query is None or not self.class_mode:
            query = {}

        tst_pth = self.get_url_from_js(qname, kwargs, args, query, url_path=url_path)
        resp = self.client.get(tst_pth)

        resp = resp.json(object_hook=object_hook)
        resp['args'] = args_hook(resp['args'])
        self.assertEqual({
                'request': reverse(qname, kwargs=kwargs, args=args),
                'args': args,
                'kwargs': kwargs,
                'query': query
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
    def convert_to_int_list(dct, key):
        if key in dct:
            dct[key] = [int(val) for val in dct[key]]
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
    }]
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
                        'urls.js': '{% urls_to_js visitor="render_static.ClassURLWriter" %}'
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }],
    })
    def test_full_url_dump_class_es6(self):
        """
        This ES6 test is horrendously slow when not using node for reasons mentioned by the Js2Py
        warning
        """
        self.class_mode = ClassURLWriter.class_name_
        self.test_full_url_dump(es5=False)
        self.class_mode = None

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': '{% urls_to_js visitor="render_static.ClassURLWriter" %}'
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }],
    })
    def test_full_url_dump_class_es6_legacy_args(self):
        """
        Test class code with legacy arguments specified individually - may be deprecated in 2.0
        """
        self.class_mode = ClassURLWriter.class_name_
        self.legacy_args = True
        self.test_full_url_dump(es5=False)
        self.class_mode = None
        self.legacy_args = False

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': 'var urls = {\n'
                                   '{% urls_to_js include=include %}'
                                   '\n};'
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }],
        'context': {
            'include': ['admin']
        }
    })
    def test_admin_urls(self):
        """
        Admin urls should work out-of-box - just check that it doesnt raise
        """
        call_command('renderstatic', 'urls.js')
        self.assertTrue(True)

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': '{% urls_to_js visitor="render_static.ClassURLWriter" es5=True%}'
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }],
    })
    def test_full_url_dump_class(self):
        """
        This ES6 test is horrendously slow when not using node for reasons mentioned by the Js2Py
        warning
        """
        self.class_mode = ClassURLWriter.class_name_
        self.test_full_url_dump(es5=True)
        self.class_mode = None

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': '{% urls_to_js visitor="render_static.ClassURLWriter" es5=True%}'
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }],
    })
    def test_full_url_dump_class_legacy_args(self):
        """
        This ES6 test is horrendously slow when not using node for reasons mentioned by the Js2Py
        warning
        """
        self.class_mode = ClassURLWriter.class_name_
        self.legacy_args = True
        self.test_full_url_dump(es5=True)
        self.class_mode = None
        self.legacy_args = False

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
    def test_full_url_dump_es6_legacy_args(self):
        """
        Test legacy argument signature - args specified individually on url() calls in javascript.
        """
        self.legacy_args = True
        self.test_full_url_dump(es5=False)
        self.legacy_args = False

    def test_full_url_dump_legacy_args(self, es5=True):
        self.legacy_args = True
        self.test_full_url_dump(es5=False)
        self.legacy_args = False

    def test_full_url_dump(self, es5=True):
        self.es5_mode = es5
        self.url_js = None

        call_command('renderstatic', 'urls.js')

        #################################################################
        # root urls
        qname = 'path_tst'
        self.compare(qname)
        self.compare(
            qname,
            {'arg1': 1},
            query={'intq1': 0, 'str': 'aadf'} if not self.legacy_args else {},
            object_hook=lambda dct: self.convert_to_int(dct, 'intq1')
        )
        self.compare(qname, {'arg1': 12, 'arg2': 'xo'})
        #################################################################

        #################################################################
        # app1 straight include 1
        qname = 'sub1:app1_pth'
        self.compare(qname)
        self.compare(qname, {'arg1': 143})  # emma
        self.compare(
            qname,
            {'arg1': 5678, 'arg2': 'xo'},
            query={'intq1': '0', 'intq2': '2'} if not self.legacy_args else {},
        )
        self.compare('sub1:app1_detail', {'id': uuid.uuid1()}, object_hook=self.convert_to_id)
        self.compare('sub1:custom_tst', {'year': 2021})
        self.compare('sub1:unreg_conv_tst', {'name': 'name2'})
        self.compare(
            'sub1:re_path_unnamed',
            args=['af', 5678],
            query={'intq1': '0', 'intq2': '2'} if not self.legacy_args else {},
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

        self.compare(
            're_path_tst',
            query={'pre': 'A', 'list1': ['0', '3', '4'], 'post': 'B'} if not self.legacy_args else {}
        )
        self.compare('re_path_tst', {'strarg': 'DEMOPLY'})
        self.compare(
            're_path_tst',
            {'strarg': 'is', 'intarg': 1337},
            query={
                'pre': 'A', 'list1': ['0', '3', '4'], 'intarg': 237
            } if not self.legacy_args else {},
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
        self.compare('app3_idx')
        self.compare(
            'app3_arg',
            {'arg1': 1},
            query={
                'list1': ['0', '3', '4'], 'intarg': [0, 2, 5], 'post': 'A'
            } if not self.legacy_args else {},
            object_hook=lambda dct: self.convert_to_int_list(dct, 'intarg')
        )
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

        call_command('renderstatic', 'urls.js')

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

        call_command('renderstatic', 'urls.js')

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

        call_command('renderstatic', 'urls.js')

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

        call_command('renderstatic', 'urls.js')

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
    # def tearDown(self):
    #    pass


@override_settings(
    ROOT_URLCONF='render_static.tests.urls2',
    STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': ('{% urls_to_js '
                                    'visitor="render_static.ClassURLWriter" '
                                    'include=include '
                                    '%}')
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }],
        'templates': {'urls.js': {'context': {'include': ['default']}}}
    }
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

        call_command('renderstatic', 'urls.js')
        self.compare('default', kwargs={'def': 'named'})
        self.compare('default', args=['unnamed'])

    def test_command_deprecation(self):
        """
        Tests: https://github.com/bckohan/django-render-static/issues/8
        :return:
        """
        import warnings
        self.es6_mode = True
        self.url_js = None
        self.class_mode = ClassURLWriter.class_name_

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            call_command('render_static', 'urls.js')
            self.assertTrue(issubclass(w[-1].category, DeprecationWarning))

        self.compare('default', kwargs={'def': 'named'})
        self.compare('default', args=['unnamed'])

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': ('{% urls_to_js '
                                    'visitor="render_static.ClassURLWriter" '
                                    'include=include '
                                    '%}')
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }],
        'templates': {'urls.js': {'context': {'include': ['no_capture']}}}
    })
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

        placeholders.register_unnamed_placeholders('no_capture', ['0000'])
        call_command('renderstatic', 'urls.js')
        self.compare('no_capture', args=['5555'])

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': ('{% urls_to_js '
                                    'visitor="render_static.ClassURLWriter" '
                                    'include=include '
                                    '%}')
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }],
        'templates': {'urls.js': {'context': {'include': ['special']}}}
    })
    def test_named_unnamed_conflation1(self):
        """
        https://github.com/bckohan/django-render-static/issues/9
        """
        self.es6_mode = True
        self.url_js = None
        self.class_mode = ClassURLWriter.class_name_

        self.assertRaises(CommandError, lambda: call_command('renderstatic', 'urls.js'))

        placeholders.register_variable_placeholder('choice', 'first')
        placeholders.register_variable_placeholder('choice1', 'second')
        self.assertRaises(CommandError, lambda: call_command('renderstatic', 'urls.js'))
        placeholders.register_unnamed_placeholders('special', ['third'])

        call_command('renderstatic', 'urls.js')
        self.compare('special', {'choice': 'second'})
        self.compare('special', {'choice': 'second', 'choice1': 'first'})
        self.compare('special', args=['third'])

    @override_settings(
        ROOT_URLCONF='render_static.tests.urls3',
        STATIC_TEMPLATES={
            'context': {'include': ['default']},
            'ENGINES': [{
                'BACKEND': 'render_static.backends.StaticDjangoTemplates',
                'OPTIONS': {
                    'loaders': [
                        ('render_static.loaders.StaticLocMemLoader', {
                            'urls.js': ('{% urls_to_js '
                                        'visitor="render_static.ClassURLWriter" '
                                        'include=include '
                                        '%}')
                        })
                    ],
                    'builtins': ['render_static.templatetags.render_static']
                },
            }],
            'templates': {'urls.js': {'context': {'include': ['special']}}}
        }
    )
    def test_named_unnamed_conflation2(self):
        """
        https://github.com/bckohan/django-render-static/issues/9
        """
        self.es6_mode = True
        self.url_js = None
        self.class_mode = ClassURLWriter.class_name_

        self.assertRaises(CommandError, lambda: call_command('renderstatic', 'urls.js'))

        placeholders.register_variable_placeholder('choice', 'first')
        placeholders.register_variable_placeholder('choice1', 'second')
        self.assertRaises(CommandError, lambda: call_command('renderstatic', 'urls.js'))
        placeholders.register_unnamed_placeholders('special', ['third'])

        call_command('renderstatic', 'urls.js')
        self.compare('special', {'choice': 'second'})
        self.compare('special', {'choice': 'second', 'choice1': 'first'})
        self.compare('special', args=['third'])

    @override_settings(
        ROOT_URLCONF='render_static.tests.urls4',
        STATIC_TEMPLATES={
            'context': {'include': ['default']},
            'ENGINES': [{
                'BACKEND': 'render_static.backends.StaticDjangoTemplates',
                'OPTIONS': {
                    'loaders': [
                        ('render_static.loaders.StaticLocMemLoader', {
                            'urls.js': '{% urls_to_js visitor="render_static.ClassURLWriter" %}'
                        })
                    ],
                    'builtins': ['render_static.templatetags.render_static']
                },
            }]
        }
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

        placeholders.register_variable_placeholder('choice', 'first')
        placeholders.register_unnamed_placeholders('special', ['first'])
        call_command('renderstatic', 'urls.js')

        with open(GLOBAL_STATIC_DIR / 'urls.js', 'r') as urls:
            if 'reverse matched unexpected pattern' not in urls.read():
                self.compare('special', kwargs={'choice': 'first'})  # pragma: no cover
                self.compare('special', args=['first'])  # pragma: no cover

        self.assertTrue(True)

    @override_settings(
        STATIC_TEMPLATES={
            'context': {'include': ['bad_mix']},
            'ENGINES': [{
                'BACKEND': 'render_static.backends.StaticDjangoTemplates',
                'OPTIONS': {
                    'loaders': [
                        ('render_static.loaders.StaticLocMemLoader', {
                            'urls.js': '{% urls_to_js '
                                       'visitor="render_static.ClassURLWriter" '
                                       'include=include %}'
                        })
                    ],
                    'builtins': ['render_static.templatetags.render_static']
                },
            }]
        }
    )
    def test_named_unnamed_bad_mix(self):
        """
        Mix of named and unnamed arguments should not be reversible!
        """
        self.es6_mode = True
        self.url_js = None
        self.class_mode = ClassURLWriter.class_name_

        placeholders.register_variable_placeholder('named', '1111')
        placeholders.register_unnamed_placeholders('bad_mix', ['unnamed'])
        call_command('renderstatic', 'urls.js')

        with open(GLOBAL_STATIC_DIR / 'urls.js', 'r') as urls:
            self.assertTrue('this path may not be reversible' in urls.read())

        self.assertRaises(
            ValueError,
            lambda: reverse(
                'bad_mix',
                kwargs={'named': '1111'}, args=['unnamed'])
        )
        self.assertRaises(NoReverseMatch, lambda: reverse('bad_mix', kwargs={'named': '1111'}))

    @override_settings(
        STATIC_TEMPLATES={
            'context': {'include': ['bad_mix2']},
            'ENGINES': [{
                'BACKEND': 'render_static.backends.StaticDjangoTemplates',
                'OPTIONS': {
                    'loaders': [
                        ('render_static.loaders.StaticLocMemLoader', {
                            'urls.js': '{% urls_to_js '
                                       'visitor="render_static.ClassURLWriter" '
                                       'include=include %}'
                        })
                    ],
                    'builtins': ['render_static.templatetags.render_static']
                },
            }]
        }
    )
    def test_named_unnamed_bad_mix2(self):
        """
        Mix of named and unnamed arguments should not be reversible!
        """
        self.es6_mode = True
        self.url_js = None
        self.class_mode = ClassURLWriter.class_name_

        placeholders.register_variable_placeholder('named', '1111')
        placeholders.register_unnamed_placeholders('bad_mix2', ['unnamed'])
        self.assertRaises(CommandError, lambda: call_command('renderstatic', 'urls.js'))

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': ('{% urls_to_js '
                                    'visitor="render_static.ClassURLWriter" '
                                    'include=include '
                                    '%}')
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }],
        'templates': {'urls.js': {'context': {'include': ['complex']}}}
    })
    def test_complexity_boundary(self):
        """
        https://github.com/bckohan/django-render-static/issues/10

        For URLs with lots of unregistered arguments, the reversal attempts may produce an explosion
        of complexity. Check that the failsafe is working.
        :return:
        """
        self.es6_mode = True
        self.class_mode = ClassURLWriter.class_name_
        self.url_js = None

        t1 = perf_counter()
        tb_str = ''
        try:
            call_command('renderstatic', 'urls.js')
        except Exception as complexity_error:
            tb_str = traceback.format_exc()
            t2 = perf_counter()

        self.assertTrue('ReversalLimitHit' in tb_str)

        # very generous reversal timing threshold of 20 seconds - anecdotally the default limit of
        # 2**15 should be hit in about 3 seconds.
        self.assertTrue(t2-t1 < 20)

        placeholders.register_variable_placeholder('one', '666')
        placeholders.register_variable_placeholder('two', '666')
        placeholders.register_variable_placeholder('three', '666')
        placeholders.register_variable_placeholder('four', '666')
        placeholders.register_variable_placeholder('five', '666')
        placeholders.register_variable_placeholder('six', '666')
        placeholders.register_variable_placeholder('seven', '666')
        placeholders.register_variable_placeholder('eight', '666')

        call_command('renderstatic', 'urls.js')

        self.compare(
            'complex',
            {
                'one': 666,
                'two': 666,
                'three': 666,
                'four': 666,
                'five': 666,
                'six': 666,
                'seven': 666,
                'eight': 666,
            }
        )

    # uncomment to not delete generated js
    # def tearDown(self):
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
        self.assertRaises(CommandError, lambda: call_command('renderstatic', 'urls.js'))
        placeholders.register_variable_placeholder('name', 'does_not_match', app_name='app1')
        self.assertRaises(CommandError, lambda: call_command('renderstatic', 'urls.js'))
        placeholders.register_variable_placeholder('name', 'name1', app_name='app1')
        placeholders.register_variable_placeholder('name', 'name1', app_name='app1')
        call_command('renderstatic', 'urls.js')
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

        self.assertRaises(CommandError, lambda: call_command('renderstatic', 'urls.js'))
        placeholders.register_unnamed_placeholders('re_path_unnamed', [143, 'adf'])  # shouldnt work
        placeholders.register_unnamed_placeholders('re_path_unnamed', ['adf', 143])  # but this will
        call_command('renderstatic', 'urls.js')
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
        self.assertRaises(CommandError, lambda: call_command('renderstatic', 'urls.js'))

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js':
                            '{% urls_to_js visitor="render_static.tests.tests.BadVisitor" %};'
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }]
    })
    def test_bad_visitor_type(self):
        self.assertRaises(CommandError, lambda: call_command('renderstatic', 'urls.js'))

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
        self.assertRaises(CommandError, lambda: call_command('renderstatic', 'urls.js'))

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
        self.assertRaises(CommandError, lambda: call_command('renderstatic', 'urls.js'))

    def test_register_bogus_converter(self):
        self.assertRaises(
            ValueError,
            lambda: placeholders.register_converter_placeholder('Not a converter type!', 1234)
        )

    # uncomment to not delete generated js
    #def tearDown(self):
    #    pass


class URLSToJavascriptParametersTest(URLJavascriptMixin, BaseTestCase):

    def setUp(self):
        self.clear_placeholder_registries()
        placeholders.register_unnamed_placeholders('re_path_unnamed', ['adf', 143])

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': '{% urls_to_js '
                                   'visitor="render_static.ClassURLWriter" '
                                   'es5=True '
                                   'raise_on_not_found=False '
                                   'indent=None '
                                   'include=include '
                                   '%}',
                        'urls2.js': '{% urls_to_js '
                                   'visitor="render_static.ClassURLWriter" '
                                   'es5=True '
                                   'raise_on_not_found=True '
                                   'indent="" '
                                   'include=include '
                                   '%}',
                        'urls3.js': 'var urls = {\n{% urls_to_js '
                                   'es5=True '
                                   'raise_on_not_found=False '
                                   'indent=None '
                                   'include=include '
                                   '%}}\n',
                        'urls4.js': 'var urls = {\n{% urls_to_js '
                                    'es5=True '
                                    'raise_on_not_found=True '
                                    'indent="" '
                                    'include=include '
                                    '%}};\n',
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }],
        'templates': {
            'urls.js': {'context': {'include': ['path_tst', 're_path_unnamed']}},
            'urls2.js': {'context': {'include': ['path_tst', 're_path_unnamed']}},
            'urls3.js': {'context': {'include': ['path_tst', 're_path_unnamed']}},
            'urls4.js': {'context': {'include': ['path_tst', 're_path_unnamed']}}
        }
    })
    def test_class_parameters_es5(self):

        self.es6_mode = False
        self.class_mode = ClassURLWriter.class_name_
        call_command('renderstatic')
        js_ret = self.get_url_from_js(
            'doest_not_exist',
            js_generator=URLJavascriptMixin.TestJSGenerator(
                class_mode=self.class_mode,
                catch=False
            )
        )
        self.assertFalse('TypeError' in js_ret)
        self.compare('path_tst')
        self.compare('path_tst', {'arg1': 1})
        self.compare('path_tst', {'arg1': 12, 'arg2': 'xo'})

        up2 = GLOBAL_STATIC_DIR/'urls2.js'
        js_ret2 = self.get_url_from_js(
            'doest_not_exist',
            url_path=up2,
            js_generator=URLJavascriptMixin.TestJSGenerator(
                class_mode=self.class_mode,
                catch=False
            )
        )
        self.assertTrue('TypeError' in js_ret2)

        js_ret2_1 = self.get_url_from_js(
            'path_tst',
            kwargs={'arg1': 12, 'arg2': 'xo', 'invalid': 0},
            url_path=up2,
            js_generator=URLJavascriptMixin.TestJSGenerator(
                class_mode=self.class_mode,
                catch=False
            )
        )
        self.assertTrue('TypeError' in js_ret2_1)
        self.compare('path_tst', url_path=up2)
        self.compare('path_tst', {'arg1': 1}, url_path=up2)
        self.compare('path_tst', {'arg1': 12, 'arg2': 'xo'}, url_path=up2)

        self.class_mode = None

        up3 = GLOBAL_STATIC_DIR/'urls3.js'
        js_ret3 = self.get_url_from_js(
            'path_tst',
            kwargs={'arg1': 12, 'arg2': 'xo', 'invalid': 0},
            url_path=up3,
            js_generator=URLJavascriptMixin.TestJSGenerator(catch=False)
        )
        self.assertFalse('TypeError' in js_ret3)
        self.compare('path_tst', url_path=up3)
        self.compare('path_tst', {'arg1': 1}, url_path=up3)
        self.compare('path_tst', {'arg1': 12, 'arg2': 'xo'}, url_path=up3)

        up4 = GLOBAL_STATIC_DIR/'urls4.js'
        js_ret4 = self.get_url_from_js(
            'path_tst',
            kwargs={'arg1': 12, 'arg2': 'xo', 'invalid': 0},
            url_path=up4,
            js_generator=URLJavascriptMixin.TestJSGenerator(catch=False)
        )
        self.assertTrue('TypeError' in js_ret4)
        self.compare('path_tst', url_path=up4)
        self.compare('path_tst', {'arg1': 1}, url_path=up4)
        self.compare('path_tst', {'arg1': 12, 'arg2': 'xo'}, url_path=up4)

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': '{% urls_to_js '
                                   'visitor="render_static.ClassURLWriter" '
                                   'raise_on_not_found=False '
                                   'indent=None '
                                   'include=include '
                                   '%}',
                        'urls2.js': '{% urls_to_js '
                                   'visitor="render_static.ClassURLWriter" '
                                   'raise_on_not_found=True '
                                   'indent="" '
                                   'include=include '
                                   '%}',
                        'urls3.js': 'var urls = {\n{% urls_to_js '
                                   'raise_on_not_found=False '
                                   'indent=None '
                                   'include=include '
                                   '%}}\n',
                        'urls4.js': 'var urls = {\n{% urls_to_js '
                                    'raise_on_not_found=True '
                                    'indent="" '
                                    'include=include '
                                    '%}};\n',
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }],
        'templates': {
            'urls.js': {'context': {'include': ['path_tst', 're_path_unnamed']}},
            'urls2.js': {'context': {'include': ['path_tst', 're_path_unnamed']}},
            'urls3.js': {'context': {'include': ['path_tst', 're_path_unnamed']}},
            'urls4.js': {'context': {'include': ['path_tst', 're_path_unnamed']}}
        }
    })
    def test_class_parameters_es6(self):

        self.es6_mode = True
        self.class_mode = ClassURLWriter.class_name_
        call_command('renderstatic')
        js_ret = self.get_url_from_js(
            'doest_not_exist',
            js_generator=URLJavascriptMixin.TestJSGenerator(
                class_mode=self.class_mode,
                catch=False
            )
        )
        self.assertFalse('TypeError' in js_ret)
        self.compare('path_tst')
        self.compare('path_tst', {'arg1': 1})
        self.compare('path_tst', {'arg1': 12, 'arg2': 'xo'})

        up2 = GLOBAL_STATIC_DIR/'urls2.js'
        js_ret2 = self.get_url_from_js(
            'doest_not_exist',
            url_path=up2,
            js_generator=URLJavascriptMixin.TestJSGenerator(
                class_mode=self.class_mode,
                catch=False
            )
        )
        self.assertTrue('TypeError' in js_ret2)

        js_ret2_1 = self.get_url_from_js(
            'path_tst',
            kwargs={'arg1': 12, 'arg2': 'xo', 'invalid': 0},
            url_path=up2,
            js_generator=URLJavascriptMixin.TestJSGenerator(
                class_mode=self.class_mode,
                catch=False
            )
        )
        self.assertTrue('TypeError' in js_ret2_1)
        self.compare('path_tst', url_path=up2)
        self.compare('path_tst', {'arg1': 1}, url_path=up2)
        self.compare('path_tst', {'arg1': 12, 'arg2': 'xo'}, url_path=up2)

        self.class_mode = None

        up3 = GLOBAL_STATIC_DIR/'urls3.js'
        js_ret3 = self.get_url_from_js(
            'path_tst',
            kwargs={'arg1': 12, 'arg2': 'xo', 'invalid': 0},
            url_path=up3,
            js_generator=URLJavascriptMixin.TestJSGenerator(catch=False)
        )
        self.assertFalse('TypeError' in js_ret3)
        self.compare('path_tst', url_path=up3)
        self.compare('path_tst', {'arg1': 1}, url_path=up3)
        self.compare('path_tst', {'arg1': 12, 'arg2': 'xo'}, url_path=up3)

        up4 = GLOBAL_STATIC_DIR/'urls4.js'
        js_ret4 = self.get_url_from_js(
            'path_tst',
            kwargs={'arg1': 12, 'arg2': 'xo', 'invalid': 0},
            url_path=up4,
            js_generator=URLJavascriptMixin.TestJSGenerator(catch=False)
        )
        self.assertTrue('TypeError' in js_ret4)
        self.compare('path_tst', url_path=up4)
        self.compare('path_tst', {'arg1': 1}, url_path=up4)
        self.compare('path_tst', {'arg1': 12, 'arg2': 'xo'}, url_path=up4)

    # uncomment to not delete generated js
    # def tearDown(self):
    #    pass


@override_settings(
    ROOT_URLCONF='render_static.tests.js_reverse_urls',
    STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': '{% urls_to_js '
                                   'visitor="render_static.ClassURLWriter" '
                                   'exclude="exclude_namespace"|split '
                                   '%};'
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }]
    }
)
class DjangoJSReverseTest(URLJavascriptMixin, BaseTestCase):
    """
    Run additional tests pilfered from django-js-reverse for the hell of it.
    https://github.com/ierror/django-js-reverse/blob/master/django_js_reverse/tests/test_urls.py
    """

    def setUp(self):
        self.clear_placeholder_registries()

    def test_js_reverse_urls(self, es6=True):
        self.es5_mode = False
        self.url_js = None
        self.class_mode = ClassURLWriter.class_name_

        call_command('render_static', 'urls.js')

    # uncomment to not delete generated js
    # def tearDown(self):
    #    pass


class TestContextResolution(BaseTestCase):

    def setUp(self):
        super().setUp()
        with open(BAD_PICKLE, 'w') as bp:
            bp.write('not pickle content')
        with open(NOT_A_DICT_PICKLE, 'wb') as bp:
            pickle.dump(['bad context'], bp)
        with open(CONTEXT_PICKLE, 'wb') as cp:
            pickle.dump({'context': 'pickle'}, cp)

    def test_pickle_context(self):
        self.assertEqual(
            resolve_context(Path(__file__).parent / 'resources' / 'context.pickle'),
            {'context': 'pickle'}
        )

    def test_json_context(self):
        self.assertEqual(
            resolve_context(str(Path(__file__).parent / 'resources' / 'context.json')),
            {'context': 'json'}
        )

    def test_yaml_context(self):
        self.assertEqual(
            resolve_context(str(Path(__file__).parent / 'resources' / 'context.yaml')),
            {'context': 'yaml'}
        )

    def test_python_context(self):
        self.assertEqual(
            resolve_context(Path(__file__).parent / 'resources' / 'context.py'),
            {'context': 'python'}
        )

    def test_pickle_context_resource(self):
        self.assertEqual(
            resolve_context(resource('render_static.tests.resources', 'context.pickle')),
            {'context': 'pickle'}
        )

    def test_json_context_resource(self):
        self.assertEqual(
            resolve_context(resource('render_static.tests.resources', 'context.json')),
            {'context': 'json'}
        )
        from render_static.tests import resources
        self.assertEqual(
            resolve_context(resource(resources, 'context.json')),
            {'context': 'json'}
        )

    def test_python_context_resource(self):
        self.assertEqual(
            resolve_context(resource('render_static.tests.resources', 'context.py')),
            {'context': 'python'}
        )

    def test_python_context_embedded_import(self):
        self.assertEqual(
            resolve_context('render_static.tests.resources.context_embedded.context'),
            {'context': 'embedded'}
        )
        self.assertEqual(
            resolve_context('render_static.tests.resources.context_embedded.get_context'),
            {'context': 'embedded_callable'}
        )

    def test_bad_contexts(self):
        self.assertRaises(
            InvalidContext,
            lambda: resolve_context('render_static.tests.resources.context_embedded.not_a_dict')
        )
        self.assertRaises(
            InvalidContext,
            lambda: resolve_context(resource('render_static.tests.resources', 'bad.pickle'))
        )
        self.assertRaises(
            InvalidContext,
            lambda: resolve_context(resource('render_static.tests.resources', 'not_a_dict.pickle'))
        )
        self.assertRaises(
            InvalidContext,
            lambda: resolve_context(resource('render_static.tests.resources', 'bad_code.py'))
        )
        self.assertRaises(
            InvalidContext,
            lambda: resolve_context(str(Path(__file__).parent / 'resources' / 'bad.yaml')),
        )
        self.assertRaises(
            InvalidContext,
            lambda: resolve_context(str(Path(__file__).parent / 'resources' / 'bad.json')),
        )
        self.assertRaises(
            InvalidContext,
            lambda: resolve_context(resource('render_static.tests.resources', 'dne'))
        )

        self.assertRaises(
            InvalidContext,
            lambda: resolve_context(resource('render_static.tests.dne', 'dne'))
        )

    def tearDown(self):
        super().tearDown()
        os.remove(BAD_PICKLE)
        os.remove(NOT_A_DICT_PICKLE)
        os.remove(CONTEXT_PICKLE)


"""
@override_settings(
    ROOT_URLCONF='render_static.tests.ex_urls',
    STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls_simple.js': 'var urls = {\n{% urls_to_js exclude="admin"|split %}};'
                    }),
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls_class.js': '{% urls_to_js visitor="render_static.ClassURLWriter" '
                                         'exclude="admin"|split%}'
                    })
                ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }],
        'templates': {
            'urls_simple.js': {},
            'urls_class.js': {}
        }
    }
)
class GenerateExampleCode(BaseTestCase):

    def test_generate_examples(self):
        call_command('renderstatic')

    # uncomment to not delete generated js
    def tearDown(self):
        pass
"""
