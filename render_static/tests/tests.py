import filecmp
import os
import pickle
import shutil
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from render_static import resolve_context, resource
from render_static.engine import StaticTemplateEngine
from render_static.exceptions import InvalidContext
from render_static.origin import AppOrigin, Origin

APP1_STATIC_DIR = Path(__file__).parent / 'app1' / 'static'  # this dir does not exist and must be cleaned up
APP2_STATIC_DIR = Path(__file__).parent / 'app2' / 'static'  # this dir exists and is checked in
GLOBAL_STATIC_DIR = settings.STATIC_ROOT  # this dir does not exist and must be cleaned up
STATIC_TEMP_DIR = Path(__file__).parent / 'static_templates'
STATIC_TEMP_DIR2 = Path(__file__).parent / 'static_templates2'
EXPECTED_DIR = Path(__file__).parent / 'expected'
ENUM_DIR = Path(__file__).parent / 'enum'
LOCAL_STATIC_DIR = Path(__file__).parent / 'local_static'

# create pickle files each time, in case python pickle format changes between python versions
BAD_PICKLE = Path(__file__).parent / 'resources' / 'bad.pickle'
NOT_A_DICT_PICKLE = Path(__file__).parent / 'resources' / 'not_a_dict.pickle'
CONTEXT_PICKLE = Path(__file__).parent / 'resources' / 'context.pickle'


def empty_or_dne(directory):
    if os.path.exists(str(directory)):
        return len(os.listdir(directory)) == 0
    return True


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
        LOCAL_STATIC_DIR,
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

    #def tearDown(self):
    #    pass


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


class TestEnums(BaseTestCase):

    def setUp(self):
        """
        from django.core.management import call_command
        files = Path(ENUM_DIR / 'migrations').glob('*.py')
        for file in files:
            if str(file).endswith('__init__.py'):
                continue
            os.remove(file)
        call_command('makemigrations', 'render_static_tests_enum')
        call_command('migrate')
        """

    def test_enum_base_fields(self):
        """
        Test that the Enum metaclass picks the correct database field type for
        each enum.
        """
        from render_static.tests.enum.models import EnumTester
        tester = EnumTester.objects.create()
