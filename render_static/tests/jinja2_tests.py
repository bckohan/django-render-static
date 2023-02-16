import filecmp
import os

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError, call_command
from django.template.exceptions import TemplateDoesNotExist
from django.template.utils import InvalidTemplateEngineError
from django.test import TestCase, override_settings
from django.urls import reverse
from render_static.backends import StaticDjangoTemplates, StaticJinja2Templates
from render_static.engine import StaticTemplateEngine
from render_static.loaders.jinja2 import (
    StaticDictLoader,
    StaticFileSystemLoader,
)
from render_static.tests import defines
from render_static.tests.js_tests import (
    ClassURLWriter,
    DefinesToJavascriptTest,
    URLJavascriptMixin,
)
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


@override_settings(STATIC_TEMPLATES={
    'ENGINES': [{
        'BACKEND': 'render_static.backends.StaticJinja2Templates',
        'OPTIONS': {
            'app_dir': 'custom_templates',
            'loader': StaticDictLoader({
                'defines1.js':
                    'var defines = '
                    '{\n{{ classes_to_js(classes, "  ") }}};'
                    '\nconsole.log(JSON.stringify(defines));',
                'defines2.js':
                    'var defines = '
                    '{\n{{ modules_to_js(modules) }}};'
                    '\nconsole.log(JSON.stringify(defines));',
                'defines_error.js':
                    'var defines = '
                    '{\n{{ classes_to_js(classes) }}};'
                    '\nconsole.log(JSON.stringify(defines));'
            })
        },
    }],
    'templates': {
        'defines1.js': {
            'dest': GLOBAL_STATIC_DIR / 'defines1.js',
            'context': {
                'classes': [
                    defines.MoreDefines,
                    'render_static.tests.defines.ExtendedDefines'
                ]
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
class Jinja2DefinesToJavascriptTest(DefinesToJavascriptTest):

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticJinja2Templates',
            'OPTIONS': {
                'loader': StaticDictLoader({
                    'defines1.js': (
                            'var defines = {\n{{'
                            'classes_to_js(['
                            '"render_static.tests.defines.MoreDefines",'
                            '"render_static.tests.defines.ExtendedDefines"'
                            '], "  ") }}};'
                            '\nconsole.log(JSON.stringify(defines));'
                    ),
                    'defines2.js': (
                            'var defines = {\n{{ modules_to_js(['
                            '"render_static.tests.defines",'
                            '"render_static.tests.defines2"], "  ") }}};'
                            '\nconsole.log(JSON.stringify(defines));'
                    )
                })
            },
        }],
        'templates': {
            'defines1.js': {'dest': GLOBAL_STATIC_DIR / 'defines1.js'},
            'defines2.js': {'dest': GLOBAL_STATIC_DIR / 'defines2.js'}
        }
    })
    def test_split(self):
        # we have to call the super class like this or else its decorator
        # override will override this one
        super().test_split.__wrapped__(self)


@override_settings(
    INSTALLED_APPS=[
        'render_static.tests.chain',
        'render_static.tests.spa',
        'render_static',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.sites',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'django.contrib.admin'
    ],
    ROOT_URLCONF='render_static.tests.urls_bug_13',
    STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticJinja2Templates',
            'OPTIONS': {
                'loader': StaticDictLoader({
                    'urls.js': (
                        '{{ urls_to_js() }}'
                    )
                })
            }
        }],
        'templates': {'urls.js': {'context': {}}}
    }
)
class Jinja2URLTestCases(URLJavascriptMixin, BaseTestCase):

    def setUp(self):
        self.clear_placeholder_registries()

    def test_urls_to_js(self, es5=False):
        self.es6_mode = not es5
        self.url_js = None
        self.class_mode = ClassURLWriter.class_name_

        call_command('renderstatic', 'urls.js')
        for name, kwargs in [
            ('spa1:qry', {'toparg': 1, 'arg': 3}),
            ('spa1:qry', {'toparg': 2}),
            ('spa2:qry', {'arg': 2}),
            ('spa2:qry', {}),
            ('chain:spa:qry', {'top': 'a5', 'chain': 'slug'}),
            ('chain:spa:qry', {'top': 'a5', 'chain': 'str', 'arg': 100}),
            ('chain:spa:index', {'top': 'a5', 'chain': 'str'}),
            ('chain_re:spa_re:qry', {'top': 'a5', 'chain': 'slug'}),
            ('chain_re:spa_re:qry', {'top': 'a5', 'chain': 'str', 'arg': 100}),
            ('chain_re:spa_re:index', {'top': 'a5', 'chain': 'str'}),
            ('noslash:spa:qry', {'top': 'a5', 'chain': 'slug'}),
            ('noslash:spa:qry', {'top': 'a5', 'chain': 'str', 'arg': 100}),
            ('noslash:spa:index', {'top': 'a5', 'chain': 'str'}),
        ]:
            self.assertEqual(
                reverse(name, kwargs=kwargs),
                self.get_url_from_js(name, kwargs)
            )

    @override_settings(
        INSTALLED_APPS=[
            'render_static.tests.chain',
            'render_static.tests.spa',
            'render_static',
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'django.contrib.sessions',
            'django.contrib.sites',
            'django.contrib.messages',
            'django.contrib.staticfiles',
            'django.contrib.admin'
        ],
        ROOT_URLCONF='render_static.tests.urls_bug_13',
        STATIC_TEMPLATES={
            'ENGINES': [{
                'BACKEND': 'render_static.backends.StaticJinja2Templates',
                'OPTIONS': {
                    'loader': StaticDictLoader({
                        'urls.js': (
                            '{{ urls_to_js(es5=True) }}'
                        )
                    })
                }
            }],
            'templates': {'urls.js': {'context': {}}}
        }
    )
    def test_urls_to_js_es5(self):
        self.test_urls_to_js(es5=True)


@override_settings(STATIC_TEMPLATES={
    'ENGINES': [{
        'BACKEND': 'render_static.backends.StaticJinja2Templates',
        'APP_DIRS': True,
        'OPTIONS': {
            'autoescape': False
        }
    }],
    'templates': ['app1/*.js']
})
class Jinja2WildCardLoaderTestCase(BaseTestCase):
    """
    Tests that glob patterns work as template selectors.
    """
    def test_wildcards(self):
        call_command('renderstatic')
        self.assertEqual(len(os.listdir(APP2_STATIC_DIR / 'app1')), 3)
        for source, dest in [
            (
                APP2_STATIC_DIR / 'app1' / 'glob1.js',
                EXPECTED_DIR / 'wildcard_test.js'
            ),
            (
                APP2_STATIC_DIR / 'app1' / 'glob2.js',
                EXPECTED_DIR / 'wildcard_test.js'
            ),
            (
                APP2_STATIC_DIR / 'app1' / 'other.js',
                EXPECTED_DIR / 'wildcard_test.js'
            ),
        ]:
            self.assertTrue(filecmp.cmp(source, dest, shallow=False))

    @override_settings(STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticJinja2Templates',
            'APP_DIRS': True,
            'OPTIONS': {
                'autoescape': False
            }
        }],
        'templates': ['app1/glob*.js']
    })
    def test_wildcards2(self):
        call_command('renderstatic')
        self.assertEqual(len(os.listdir(APP2_STATIC_DIR / 'app1')), 2)
        for source, dest in [
            (
                APP2_STATIC_DIR / 'app1' / 'glob1.js',
                EXPECTED_DIR / 'wildcard_test.js'
            ),
            (
                APP2_STATIC_DIR / 'app1' / 'glob2.js',
                EXPECTED_DIR / 'wildcard_test.js'
            ),
        ]:
            self.assertTrue(filecmp.cmp(source, dest, shallow=False))
