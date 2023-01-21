import filecmp
import os

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError, call_command
from django.template.exceptions import TemplateDoesNotExist
from django.template.utils import InvalidTemplateEngineError
from django.test import TestCase, override_settings
from render_static.backends import StaticDjangoTemplates, StaticJinja2Templates
from render_static.engine import StaticTemplateEngine
from render_static.loaders.jinja2 import StaticFileSystemLoader
from render_static.tests.tests import (
    APP1_STATIC_DIR,
    APP2_STATIC_DIR,
    EXPECTED_DIR,
    GLOBAL_STATIC_DIR,
    STATIC_TEMP_DIR,
    STATIC_TEMP_DIR2,
    BaseTestCase,
    TemplatePreferenceFSTestCase,
    empty_or_dne,
    generate_context1,
    generate_context2,
)

jinja2 = pytest.importorskip("jinja2")


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
    Tests that template inheritance is working correctly. Static templates
    lightly touches the template engines so its not impossible that template
    resolution could be effected.
    """

    def test_django_templates(self):
        """
        Tests that template inheritance is working for the static django
        template engine.
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
        Tests that template inheritance is working for the static Jinja2
        template engine.
        """
        call_command('renderstatic')
        self.assertTrue(filecmp.cmp(
            APP2_STATIC_DIR / 'app2' / 'html' / 'inheritance.html',
            EXPECTED_DIR / 'inheritance_jinja2.html',
            shallow=False
        ))


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
    This config should be almost functionality equivalent to the base tests.
    The template dont have any actual template logic in them so jinja2 will
    render them as well.

    The main difference is that there's only one loader so first_loader doesn't
    do anything and first_pref is the same as having both flags set.
    """

    def validate_first_pref(self):
        self.validate_first_load_and_pref()

    def validate_first_loader(self):
        self.validate_nopref()

    # def tearDown(self):
    #    pass


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


@override_settings(STATIC_TEMPLATES={
    'ENGINES': [{
        'BACKEND': 'render_static.backends.StaticJinja2Templates',
        'OPTIONS': {
            'loader': StaticFileSystemLoader(STATIC_TEMP_DIR)
        }
    }],
    'templates': [
        ['multi_test.jinja2', {
            'context': {'file': 1},
            'dest': GLOBAL_STATIC_DIR / 'multi_1_jinja2.html'
        }],
        ['multi_test.jinja2', {
            'context': {'file': 2},
            'dest': GLOBAL_STATIC_DIR / 'multi_2_jinja2.html'
        }],

    ]
})
class MultipleDestinationsTestCase(BaseTestCase):
    """
    Jinja2 tests of one template to multiple destinations.
    """
    def test_generate(self):
        """
        Tests that a single template can be specified multiple times and
        rendered to separate locations with separate contexts.
        """
        call_command('renderstatic')
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'multi_1_jinja2.html',
            EXPECTED_DIR / 'multi_1_jinja2.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'multi_2_jinja2.html',
            EXPECTED_DIR / 'multi_2_jinja2.html',
            shallow=False
        ))

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticJinja2Templates',
            'OPTIONS': {
                'loader': StaticFileSystemLoader(STATIC_TEMP_DIR)
            }
        }],
        'context': {
            'file': 1,
        },
        'templates': [
            (
                'multi_test.jinja2', {}
            ),
        ]
    })
    def test_empty(self):
        """
        Tests that empty context works
        """
        call_command('renderstatic')
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'multi_test.jinja2',
            EXPECTED_DIR / 'multi_1_jinja2.html',
            shallow=False
        ))

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticJinja2Templates',
            'OPTIONS': {
                'loader': StaticFileSystemLoader(STATIC_TEMP_DIR)
            }
        }],
        'context': {
            'file': 1,
        },
        'templates': [
            (
                'multi_test.jinja2', None
            ),
        ]
    })
    def test_none(self):
        """
        Tests that a None context is treated as an empty context
        """
        self.test_empty()

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticJinja2Templates',
            'OPTIONS': {
                'loader': StaticFileSystemLoader(STATIC_TEMP_DIR)
            }
        }],
        'context': {
            'file': 1,
        },
        'templates': [('multi_test.jinja2',)]
    })
    def test_one_tuple(self):
        """
        Tests that a one-length tuple works and uses the default config.
        """
        self.test_empty()

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticJinja2Templates',
            'OPTIONS': {
                'loader': StaticFileSystemLoader(STATIC_TEMP_DIR)
            }
        }],
        'context': {
            'file': 2
        },
        'templates': [
            'multi_test.jinja2',
            (
                'multi_test.jinja2',
                {
                    'context': {'file': 1},
                    'dest': GLOBAL_STATIC_DIR / 'multi_1_jinja2.html'
                }
            )
        ]
    })
    def test_mixed_list(self):
        """
        Test that templates definition can be a list with a mix of
        acceptable types.
        """
        call_command('renderstatic')
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'multi_1_jinja2.html',
            EXPECTED_DIR / 'multi_1_jinja2.html',
            shallow=False
        ))
        self.assertTrue(filecmp.cmp(
            GLOBAL_STATIC_DIR / 'multi_test.jinja2',
            EXPECTED_DIR / 'multi_2_jinja2.html',
            shallow=False
        ))

    # def tearDown(self):
    #     pass

"""
class TestTemplateTagsAndFilters(BaseTestCase):

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticJinja2Templates',
            'OPTIONS': {
                'loader': Sta
            }
        }],
        'templates': [
            ['multi_test.jinja2', {
                'context': {'file': 1},
                'dest': GLOBAL_STATIC_DIR / 'multi_1_jinja2.html'
            }],
            ['multi_test.jinja2', {
                'context': {'file': 2},
                'dest': GLOBAL_STATIC_DIR / 'multi_2_jinja2.html'
            }],

        ]
    })
    def test_urls_to_js(self):
        pass
"""