import contextlib
import filecmp
import os
import pickle
import shutil
import sys
from io import StringIO
from pathlib import Path

import pytest
from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError, call_command
from django.template.exceptions import TemplateDoesNotExist
from django.test import TestCase, override_settings

from render_static.context import resolve_context
from render_static.resource import resource
from render_static.engine import StaticTemplateEngine
from render_static.exceptions import InvalidContext
from render_static.origin import AppOrigin, Origin

from django_typer.management import get_command

APP1_STATIC_DIR = (
    Path(__file__).parent / "app1" / "static"
)  # this dir does not exist and must be cleaned up
APP2_STATIC_DIR = (
    Path(__file__).parent / "app2" / "static"
)  # this dir exists and is checked in
ENUM_STATIC_DIR = (
    Path(__file__).parent / "enum_app" / "static"
)  # this dir does not exist
GLOBAL_STATIC_DIR = (
    settings.STATIC_ROOT
)  # this dir does not exist and must be cleaned up
STATIC_TEMP_DIR = Path(__file__).parent / "static_templates"
STATIC_TEMP_DIR2 = Path(__file__).parent / "static_templates2"
EXPECTED_DIR = Path(__file__).parent / "expected"
ENUM_DIR = Path(__file__).parent / "enum"
LOCAL_STATIC_DIR = Path(__file__).parent / "local_static"

# create pickle files each time, in case python pickle format changes between python versions
BAD_PICKLE = Path(__file__).parent / "resources" / "bad.pickle"
NOT_A_DICT_PICKLE = Path(__file__).parent / "resources" / "not_a_dict.pickle"
CONTEXT_PICKLE = Path(__file__).parent / "resources" / "context.pickle"


try:
    # weird issue where cant just import jinja2 b/c leftover __pycache__
    # allows it to "import"
    from jinja2 import environment

    jinja2 = True
except ImportError:
    jinja2 = False


def empty_or_dne(directory):
    if os.path.exists(str(directory)):
        return len(os.listdir(directory)) == 0
    return True


class AppOriginTestCase(TestCase):
    def test_equality(self):
        test_app1 = apps.get_app_config("tests_app1")
        test_app2 = apps.get_app_config("tests_app2")

        origin1 = AppOrigin(
            name="/path/to/tmpl.html", template_name="to/tmpl.html", app=test_app1
        )
        origin2 = AppOrigin(
            name="/path/to/tmpl.html", template_name="to/tmpl.html", app=test_app1
        )
        origin3 = Origin(name="/path/to/tmpl.html", template_name="to/tmpl.html")
        origin4 = AppOrigin(
            name="/path/to/tmpl.html", template_name="to/tmpl.html", app=test_app2
        )
        origin5 = AppOrigin(
            name="/path/tmpl.html", template_name="tmpl.html", app=test_app2
        )
        origin6 = AppOrigin(name="/path/to/tmpl.html", template_name="tmpl.html")
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
        APP2_STATIC_DIR / "app1",
        APP2_STATIC_DIR / "app2",
        APP2_STATIC_DIR / "exclusive",
        ENUM_STATIC_DIR,
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
        call_command("renderstatic", "app1/html/nominal1.html")
        self.assertEqual(len(os.listdir(APP1_STATIC_DIR)), 1)
        self.assertTrue(
            not APP2_STATIC_DIR.exists() or len(os.listdir(APP2_STATIC_DIR)) == 0
        )
        self.assertTrue(
            filecmp.cmp(
                APP1_STATIC_DIR / "app1" / "html" / "nominal1.html",
                EXPECTED_DIR / "nominal1.html",
                shallow=False,
            )
        )
        call_command("renderstatic", "app1/html/nominal2.html")
        self.assertEqual(len(os.listdir(APP1_STATIC_DIR)), 1)
        self.assertEqual(len(os.listdir(APP2_STATIC_DIR)), 1)
        self.assertTrue(
            filecmp.cmp(
                APP2_STATIC_DIR / "app1" / "html" / "nominal2.html",
                EXPECTED_DIR / "nominal2.html",
                shallow=False,
            )
        )

    # def tearDown(self):
    #     pass


def generate_context1():
    return {"to": "world", "punc": "!"}


def generate_context2():
    return {"greeting": "Hello", "to": "World"}


def invalid_context_return():
    return ["garbage"]


class ConfigTestCase(TestCase):
    """
    Verifies configuration errors are reported as expected and that default loaders are created.
    """

    def test_default_loaders(self):
        """
        When no loaders specified, usage of app directories loaders is togged by APP_DIRS
        """
        engine = StaticTemplateEngine(
            {
                "ENGINES": [
                    {
                        "BACKEND": "render_static.backends.StaticDjangoTemplates",
                        "DIRS": [STATIC_TEMP_DIR],
                        "APP_DIRS": True,
                        "OPTIONS": {},
                    }
                ],
            }
        )
        self.assertEqual(
            engine["StaticDjangoTemplates"].engine.loaders,
            [
                "render_static.loaders.StaticFilesystemLoader",
                "render_static.loaders.StaticAppDirectoriesLoader",
            ],
        )

        engine = StaticTemplateEngine(
            {
                "ENGINES": [
                    {
                        "BACKEND": "render_static.backends.StaticDjangoTemplates",
                        "DIRS": [STATIC_TEMP_DIR],
                        "APP_DIRS": False,
                        "OPTIONS": {},
                    }
                ],
            }
        )
        self.assertEqual(
            engine["StaticDjangoTemplates"].engine.loaders,
            ["render_static.loaders.StaticFilesystemLoader"],
        )

    def test_app_dirs_error(self):
        """
        Configuring APP_DIRS and loader is an error.
        """
        engine = StaticTemplateEngine(
            {
                "ENGINES": [
                    {
                        "BACKEND": "render_static.backends.StaticDjangoTemplates",
                        "DIRS": [STATIC_TEMP_DIR],
                        "APP_DIRS": True,
                        "OPTIONS": {
                            "loaders": ["render_static.loaders.StaticFilesystemLoader"]
                        },
                    }
                ]
            }
        )
        self.assertRaises(ImproperlyConfigured, lambda: engine.engines)

    def test_dest_error(self):
        """
        Dest must be an absolute path in ether string or Path form.
        """
        engine = StaticTemplateEngine(
            {
                "templates": {
                    "nominal_fs.html": {"dest": [GLOBAL_STATIC_DIR / "nominal_fs.html"]}
                }
            }
        )
        self.assertRaises(ImproperlyConfigured, lambda: engine.templates)

        engine = StaticTemplateEngine(
            {"templates": {"nominal_fs.html": {"dest": "./nominal_fs.html"}}}
        )
        self.assertRaises(ImproperlyConfigured, lambda: engine.templates)

    def test_context_error(self):
        """
        Context must be a dictionary.
        """
        engine = StaticTemplateEngine({"context": [0]})
        self.assertRaises(ImproperlyConfigured, lambda: engine.context)

        engine = StaticTemplateEngine(
            {
                "templates": {
                    "nominal_fs.html": {
                        "dest": GLOBAL_STATIC_DIR / "nominal_fs.html",
                        "context": [0],
                    }
                }
            }
        )
        self.assertRaises(ImproperlyConfigured, lambda: engine.templates)

    def test_no_settings(self):
        """
        Change in v2 - this no longer raises when STATIC_TEMPLATES setting is not present
        """
        StaticTemplateEngine()

    @override_settings(
        STATIC_ROOT=None,
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "DIRS": [STATIC_TEMP_DIR],
                    "OPTIONS": {
                        "loaders": ["render_static.loaders.StaticFilesystemBatchLoader"]
                    },
                }
            ]
        },
    )
    def test_no_destination(self):
        """
        If no  setting is present we should raise.
        """
        self.assertRaises(
            CommandError, lambda: call_command("renderstatic", "nominal_fs.html")
        )

    def test_unrecognized_settings(self):
        """
        Unrecognized configuration keys should raise.
        """
        engine = StaticTemplateEngine({"unknown_key": 0, "bad": "value"})
        self.assertRaises(ImproperlyConfigured, lambda: engine.config)

        engine = StaticTemplateEngine(
            {
                "templates": {
                    "nominal_fs.html": {
                        "dest": GLOBAL_STATIC_DIR / "nominal_fs.html",
                        "context": {},
                        "unrecognized_key": "bad",
                    }
                }
            }
        )
        self.assertRaises(ImproperlyConfigured, lambda: engine.templates)

    def test_backends(self):
        """
        Backends must exist.
        """
        engine = StaticTemplateEngine({"ENGINES": [{"BACKEND": 0}]})
        self.assertRaises(ImproperlyConfigured, lambda: engine.engines)

    def test_allow_dot_modifiers(self):
        engine = StaticTemplateEngine(
            {
                "ENGINES": [
                    {
                        "BACKEND": "render_static.backends.StaticDjangoTemplates",
                        "APP_DIRS": True,
                    }
                ],
                "templates": {"../app1/html/nominal1.html": {}},
            }
        )
        self.assertRaises(
            TemplateDoesNotExist,
            lambda: engine.render_to_disk("../app1/html/nominal1.html"),
        )

    def test_suspicious_selector_fs(self):
        engine = StaticTemplateEngine(
            {
                "ENGINES": [
                    {
                        "BACKEND": "render_static.backends.StaticDjangoTemplates",
                        "DIRS": [STATIC_TEMP_DIR],
                        "OPTIONS": {
                            "loaders": [
                                "render_static.loaders.StaticFilesystemBatchLoader"
                            ]
                        },
                    }
                ]
            }
        )
        self.assertRaises(
            TemplateDoesNotExist,
            lambda: engine.render_to_disk(
                "../static_templates2/exclusive/template1.html"
            ),
        )

    def test_suspicious_selector_appdirs(self):
        engine = StaticTemplateEngine(
            {
                "ENGINES": [
                    {
                        "BACKEND": "render_static.backends.StaticDjangoTemplates",
                        "OPTIONS": {
                            "loaders": [
                                "render_static.loaders.StaticAppDirectoriesBatchLoader"
                            ]
                        },
                    }
                ]
            }
        )
        self.assertRaises(
            TemplateDoesNotExist,
            lambda: engine.render_to_disk("../custom_templates/nominal_fs.html"),
        )

    def test_no_selector_templates_found(self):
        engine = StaticTemplateEngine(
            {
                "ENGINES": [
                    {
                        "BACKEND": "render_static.backends.StaticDjangoTemplates",
                        "OPTIONS": {
                            "loaders": [
                                "render_static.loaders.StaticAppDirectoriesBatchLoader"
                            ]
                        },
                    }
                ]
            }
        )
        self.assertRaises(TemplateDoesNotExist, lambda: engine.render_to_disk("*.css"))

    # def tearDown(self):
    #     pass


@override_settings(
    STATIC_TEMPLATES={
        "context": "tests.test_core.generate_context1",
        "templates": {
            "app1/html/hello.html": {
                "context": generate_context2,
            }
        },
    }
)
class CallableContextTestCase(BaseTestCase):
    """
    Tests that show callable contexts work as expected.
    """

    def test_nominal_generate(self):
        call_command("renderstatic")
        self.assertTrue(
            filecmp.cmp(
                APP1_STATIC_DIR / "app1" / "html" / "hello.html",
                EXPECTED_DIR / "ctx_override.html",
                shallow=False,
            )
        )

    @override_settings(
        STATIC_TEMPLATES={
            "templates": {"app1/html/hello.html": {"context": "does.not.exist"}}
        }
    )
    def test_off_nominal_tmpl(self):
        self.assertRaises(ImproperlyConfigured, lambda: call_command("renderstatic"))

    @override_settings(
        STATIC_TEMPLATES={
            "context": invalid_context_return,
            "templates": {"app1/html/hello.html": {}},
        }
    )
    def test_off_nominal_global(self):
        self.assertRaises(CommandError, lambda: call_command("renderstatic"))

    # def tearDown(self):
    #    pass


@override_settings(
    STATIC_TEMPLATES={
        "context": {"to": "world", "punc": "!"},
        "templates": {
            "app1/html/hello.html": {
                "context": {"greeting": "Hello", "to": "World"},
            }
        },
    }
)
class ContextOverrideTestCase(BaseTestCase):
    """
    Tests that per template contexts override global contexts and that the global context is also
    used.
    """

    def test_generate(self):
        call_command("renderstatic")
        self.assertTrue(
            filecmp.cmp(
                APP1_STATIC_DIR / "app1" / "html" / "hello.html",
                EXPECTED_DIR / "ctx_override.html",
                shallow=False,
            )
        )

    # def tearDown(self):
    #    pass


@override_settings(
    STATIC_TEMPLATES={
        "ENGINES": [
            {
                "BACKEND": "render_static.backends.StaticDjangoTemplates",
                "DIRS": [STATIC_TEMP_DIR],
                "OPTIONS": {
                    "loaders": [
                        "render_static.loaders.StaticFilesystemBatchLoader",
                        "render_static.loaders.StaticAppDirectoriesBatchLoader",
                    ]
                },
            }
        ]
    }
)
class BatchFileSystemRenderTestCase(BaseTestCase):
    """
    Tests that exercise the batch template loaders.
    """

    def test_batch_filesystem_render1(self):
        call_command("renderstatic", "batch_fs*")
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "batch_fs_test0.html",
                EXPECTED_DIR / "nominal_fs.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "batch_fs_test1.html",
                EXPECTED_DIR / "nominal_fs.html",
                shallow=False,
            )
        )
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR)), 2)

    def test_batch_filesystem_render2(self):
        call_command("renderstatic", "**/batch_fs*")
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "batch_fs_test0.html",
                EXPECTED_DIR / "nominal_fs.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "batch_fs_test1.html",
                EXPECTED_DIR / "nominal_fs.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "subdir" / "batch_fs_test2.html",
                EXPECTED_DIR / "nominal1.html",
                shallow=False,
            )
        )
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR)), 3)

    # def tearDown(self):
    #    pass


@override_settings(
    STATIC_TEMPLATES={
        "ENGINES": [
            {
                "BACKEND": "render_static.backends.StaticDjangoTemplates",
                "DIRS": [STATIC_TEMP_DIR, STATIC_TEMP_DIR2],
                "OPTIONS": {
                    "loaders": [
                        "render_static.loaders.StaticFilesystemBatchLoader",
                        "render_static.loaders.StaticAppDirectoriesBatchLoader",
                    ]
                },
            }
        ]
    }
)
class TemplatePreferenceFSTestCase(BaseTestCase):
    """
    Tests that load preferences flag works as described and that destinations also work as
    described:

        - first_loader
        - first_preference

    Do the right files get picked and do they go to the expected locations?
    """

    def test_nopref(self):
        call_command("renderstatic", "exclusive/*")
        self.validate_nopref()

    def validate_nopref(self):
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template1.html",
                EXPECTED_DIR / "glb_template1.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template2.html",
                EXPECTED_DIR / "glb_template2.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template3.html",
                EXPECTED_DIR / "glb_template3.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template4.html",
                EXPECTED_DIR / "glb2_template4.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                APP2_STATIC_DIR / "exclusive" / "template5.html",
                EXPECTED_DIR / "app2_template5.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                APP1_STATIC_DIR / "exclusive" / "template6.html",
                EXPECTED_DIR / "app1_template6.html",
                shallow=False,
            )
        )
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR / "exclusive")), 4)
        self.assertEqual(len(os.listdir(APP2_STATIC_DIR / "exclusive")), 1)
        self.assertEqual(len(os.listdir(APP1_STATIC_DIR / "exclusive")), 1)

    def test_first_loader(self):
        call_command("renderstatic", "exclusive/*", first_loader=True)
        self.validate_first_loader()

    def validate_first_loader(self):
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template1.html",
                EXPECTED_DIR / "glb_template1.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template2.html",
                EXPECTED_DIR / "glb_template2.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template3.html",
                EXPECTED_DIR / "glb_template3.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template4.html",
                EXPECTED_DIR / "glb2_template4.html",
                shallow=False,
            )
        )
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR / "exclusive")), 4)
        self.assertTrue(empty_or_dne(APP1_STATIC_DIR))
        self.assertTrue(empty_or_dne(APP2_STATIC_DIR))

    def test_first_pref(self):
        call_command("renderstatic", "exclusive/*", first_preference=True)
        self.validate_first_pref()

    def validate_first_pref(self):
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template1.html",
                EXPECTED_DIR / "glb_template1.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template2.html",
                EXPECTED_DIR / "glb_template2.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template3.html",
                EXPECTED_DIR / "glb_template3.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                APP1_STATIC_DIR / "exclusive" / "template6.html",
                EXPECTED_DIR / "app1_template6.html",
                shallow=False,
            )
        )
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR / "exclusive")), 3)
        self.assertEqual(len(os.listdir(APP1_STATIC_DIR / "exclusive")), 1)
        self.assertTrue(empty_or_dne(APP2_STATIC_DIR))

    def test_first_loader_and_pref(self):
        call_command(
            "renderstatic", "exclusive/*", first_loader=True, first_preference=True
        )
        self.validate_first_load_and_pref()

    def validate_first_load_and_pref(self):
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template1.html",
                EXPECTED_DIR / "glb_template1.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template2.html",
                EXPECTED_DIR / "glb_template2.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template3.html",
                EXPECTED_DIR / "glb_template3.html",
                shallow=False,
            )
        )
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR / "exclusive")), 3)
        self.assertTrue(empty_or_dne(APP1_STATIC_DIR))
        self.assertTrue(empty_or_dne(APP2_STATIC_DIR))

    def test_batch_destination_override(self):
        call_command("renderstatic", "exclusive/*", destination=GLOBAL_STATIC_DIR)
        self.validate_batch_destination_override()

    def validate_batch_destination_override(self):
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template1.html",
                EXPECTED_DIR / "glb_template1.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template2.html",
                EXPECTED_DIR / "glb_template2.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template3.html",
                EXPECTED_DIR / "glb_template3.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template4.html",
                EXPECTED_DIR / "glb2_template4.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template5.html",
                EXPECTED_DIR / "app2_template5.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template6.html",
                EXPECTED_DIR / "app1_template6.html",
                shallow=False,
            )
        )
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR / "exclusive")), 6)

    # def tearDown(self):
    #    pass


@override_settings(
    STATIC_TEMPLATES={
        "ENGINES": [
            {
                "BACKEND": "render_static.backends.StaticDjangoTemplates",
                "DIRS": [STATIC_TEMP_DIR, STATIC_TEMP_DIR2],
                "OPTIONS": {
                    "loaders": [
                        "render_static.loaders.StaticAppDirectoriesBatchLoader",
                        "render_static.loaders.StaticFilesystemBatchLoader",
                    ]
                },
            }
        ]
    }
)
class TemplatePreferenceAPPSTestCase(BaseTestCase):
    """
    Tests that load preferences flag works as described and that destinations also work as
    described, for the app directories loader.

        - first_loader
        - first_preference

    Do the right files get picked and do they go to the expected locations?
    """

    def test_nopref(self):
        call_command("renderstatic", "exclusive/*")
        self.validate_nopref()

    def validate_nopref(self):
        self.assertTrue(
            filecmp.cmp(
                APP1_STATIC_DIR / "exclusive" / "template1.html",
                EXPECTED_DIR / "app1_template1.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                APP2_STATIC_DIR / "exclusive" / "template2.html",
                EXPECTED_DIR / "app2_template2.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template3.html",
                EXPECTED_DIR / "glb_template3.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template4.html",
                EXPECTED_DIR / "glb2_template4.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                APP2_STATIC_DIR / "exclusive" / "template5.html",
                EXPECTED_DIR / "app2_template5.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                APP1_STATIC_DIR / "exclusive" / "template6.html",
                EXPECTED_DIR / "app1_template6.html",
                shallow=False,
            )
        )
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR / "exclusive")), 2)
        self.assertEqual(len(os.listdir(APP2_STATIC_DIR / "exclusive")), 2)
        self.assertEqual(len(os.listdir(APP1_STATIC_DIR / "exclusive")), 2)

    def test_first_loader(self):
        call_command("renderstatic", "exclusive/*", first_loader=True)
        self.validate_first_loader()

    def validate_first_loader(self):
        self.assertTrue(
            filecmp.cmp(
                APP1_STATIC_DIR / "exclusive" / "template1.html",
                EXPECTED_DIR / "app1_template1.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                APP2_STATIC_DIR / "exclusive" / "template2.html",
                EXPECTED_DIR / "app2_template2.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                APP2_STATIC_DIR / "exclusive" / "template5.html",
                EXPECTED_DIR / "app2_template5.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                APP1_STATIC_DIR / "exclusive" / "template6.html",
                EXPECTED_DIR / "app1_template6.html",
                shallow=False,
            )
        )
        self.assertEqual(len(os.listdir(APP1_STATIC_DIR / "exclusive")), 2)
        self.assertEqual(len(os.listdir(APP2_STATIC_DIR / "exclusive")), 2)
        self.assertTrue(empty_or_dne(GLOBAL_STATIC_DIR))

    def test_first_pref(self):
        call_command("renderstatic", "exclusive/*", first_preference=True)
        self.validate_first_pref()

    def validate_first_pref(self):
        self.assertTrue(
            filecmp.cmp(
                APP1_STATIC_DIR / "exclusive" / "template1.html",
                EXPECTED_DIR / "app1_template1.html",
                shallow=False,
            )
        )

        # app2's template is resolved because selection criteria only counts for resolving template
        # names, so template2.html is picked - but then when the template name is resolved to a file
        # the app loader has precedence and picks the app2 template over the filesystem one.
        # this is expected, if a little confusing - these options are for corner cases anyway.
        self.assertTrue(
            filecmp.cmp(
                APP2_STATIC_DIR / "exclusive" / "template2.html",
                EXPECTED_DIR / "app2_template2.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template3.html",
                EXPECTED_DIR / "glb_template3.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                APP1_STATIC_DIR / "exclusive" / "template6.html",
                EXPECTED_DIR / "app1_template6.html",
                shallow=False,
            )
        )
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR / "exclusive")), 1)
        self.assertEqual(len(os.listdir(APP1_STATIC_DIR / "exclusive")), 2)
        self.assertEqual(len(os.listdir(APP2_STATIC_DIR / "exclusive")), 1)

    def test_first_loader_and_pref(self):
        call_command(
            "renderstatic", "exclusive/*", first_loader=True, first_preference=True
        )
        self.validate_first_load_and_pref()

    def validate_first_load_and_pref(self):
        self.assertTrue(
            filecmp.cmp(
                APP1_STATIC_DIR / "exclusive" / "template1.html",
                EXPECTED_DIR / "app1_template1.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                APP1_STATIC_DIR / "exclusive" / "template6.html",
                EXPECTED_DIR / "app1_template6.html",
                shallow=False,
            )
        )
        self.assertEqual(len(os.listdir(APP1_STATIC_DIR / "exclusive")), 2)
        self.assertTrue(empty_or_dne(GLOBAL_STATIC_DIR))
        self.assertTrue(empty_or_dne(APP2_STATIC_DIR))

    def test_batch_destination_override(self):
        call_command("renderstatic", "exclusive/*", destination=GLOBAL_STATIC_DIR)
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template1.html",
                EXPECTED_DIR / "app1_template1.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template2.html",
                EXPECTED_DIR / "app2_template2.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template3.html",
                EXPECTED_DIR / "glb_template3.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template4.html",
                EXPECTED_DIR / "glb2_template4.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template5.html",
                EXPECTED_DIR / "app2_template5.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template6.html",
                EXPECTED_DIR / "app1_template6.html",
                shallow=False,
            )
        )
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR / "exclusive")), 6)

    # def tearDown(self):
    #     pass


@override_settings(
    STATIC_TEMPLATES={
        "ENGINES": [
            {
                "BACKEND": "render_static.backends.StaticDjangoTemplates",
                "NAME": "Engine0",
                "OPTIONS": {
                    "loaders": ["render_static.loaders.StaticAppDirectoriesBatchLoader"]
                },
            },
            {
                "BACKEND": "render_static.backends.StaticDjangoTemplates",
                "NAME": "Engine1",
                "DIRS": [STATIC_TEMP_DIR, STATIC_TEMP_DIR2],
                "OPTIONS": {
                    "loaders": ["render_static.loaders.StaticFilesystemBatchLoader"]
                },
            },
        ]
    }
)
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
        call_command("renderstatic", "exclusive/*")
        self.validate_nopref()

    def test_first_loader(self):
        call_command("renderstatic", "exclusive/*", first_engine=True)
        self.validate_first_loader()

    def test_first_pref(self):
        call_command("renderstatic", "exclusive/*", first_preference=True)
        self.validate_first_pref()

    def validate_first_pref(self):
        self.assertTrue(
            filecmp.cmp(
                APP1_STATIC_DIR / "exclusive" / "template1.html",
                EXPECTED_DIR / "app1_template1.html",
                shallow=False,
            )
        )

        # I don't understand why the file system one is picked, but this is corner case behavior
        # and it only really matters that this remains consistent
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template2.html",
                EXPECTED_DIR / "glb_template2.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "exclusive" / "template3.html",
                EXPECTED_DIR / "glb_template3.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                APP1_STATIC_DIR / "exclusive" / "template6.html",
                EXPECTED_DIR / "app1_template6.html",
                shallow=False,
            )
        )
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR / "exclusive")), 2)
        self.assertEqual(len(os.listdir(APP1_STATIC_DIR / "exclusive")), 2)
        self.assertTrue(empty_or_dne(APP2_STATIC_DIR))

    def test_first_loader_and_pref(self):
        call_command(
            "renderstatic", "exclusive/*", first_engine=True, first_preference=True
        )
        self.validate_first_load_and_pref()

    # def tearDown(self):
    #    pass


@override_settings(
    STATIC_TEMPLATES={
        "context": {"to": "world", "punc": "!", "greeting": "Bye"},
        "templates": {
            "app1/html/hello.html": {
                "dest": str(GLOBAL_STATIC_DIR / "dest_override.html")
            }
        },
    }
)
class DestOverrideTestCase(BaseTestCase):
    """
    Tests that destination can be overridden for app directory loaded templates and that dest can be
    a string path
    """

    def test_generate(self):
        call_command("renderstatic")
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "dest_override.html",
                EXPECTED_DIR / "dest_override.html",
                shallow=False,
            )
        )


@override_settings(
    STATIC_TEMPLATES={
        "ENGINES": [
            {
                "BACKEND": "render_static.backends.StaticDjangoTemplates",
                "DIRS": [STATIC_TEMP_DIR],
                "OPTIONS": {
                    "app_dir": "custom_templates",
                    "loaders": [
                        "render_static.loaders.StaticFilesystemLoader",
                        "render_static.loaders.StaticAppDirectoriesLoader",
                    ],
                },
            }
        ],
        "templates": {
            "nominal_fs.html": {"dest": GLOBAL_STATIC_DIR / "nominal_fs.html"}
        },
    }
)
class FSLoaderTestCase(BaseTestCase):
    to_remove = BaseTestCase.to_remove + [APP2_STATIC_DIR / "nominal_fs2.html"]

    """
    Tests:
        - Filesystem loader
        - That loader order determines precedence
        - That app directory static template dirs can be configured @ the backend level
    """

    def test_generate(self):
        call_command("renderstatic", "nominal_fs.html", "nominal_fs2.html")
        self.assertFalse(APP1_STATIC_DIR.exists())
        self.assertEqual(len(os.listdir(APP2_STATIC_DIR)), 1)
        self.assertEqual(len(os.listdir(GLOBAL_STATIC_DIR)), 1)
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "nominal_fs.html",
                EXPECTED_DIR / "nominal_fs.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                APP2_STATIC_DIR / "nominal_fs2.html",
                EXPECTED_DIR / "nominal_fs2.html",
                shallow=False,
            )
        )


@override_settings(STATIC_TEMPLATES=None)
class DirectRenderTestCase(BaseTestCase):
    def test_override_context(self):
        engine = StaticTemplateEngine(
            {
                "context": {"to": "world", "punc": "!"},
                "templates": {
                    "app1/html/hello.html": {
                        "context": {"greeting": "Hello", "to": "World"},
                    }
                },
            }
        )
        engine.render_to_disk("app1/html/hello.html", context={"punc": "."})
        self.assertTrue(
            filecmp.cmp(
                APP1_STATIC_DIR / "app1/html/hello.html",
                EXPECTED_DIR / "ctx_override2.html",
                shallow=False,
            )
        )

    def test_override_dest(self):
        engine = StaticTemplateEngine(
            {
                "context": {"to": "world", "punc": "!", "greeting": "Bye"},
                "templates": {"app1/html/hello.html": {}},
            }
        )
        engine.render_to_disk(
            "app1/html/hello.html", dest=str(GLOBAL_STATIC_DIR / "override_dest.html")
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "override_dest.html",
                EXPECTED_DIR / "dest_override.html",
                shallow=False,
            )
        )


@override_settings(
    STATIC_TEMPLATES={
        "ENGINES": [
            {
                "BACKEND": "render_static.backends.StaticDjangoTemplates",
                "DIRS": [STATIC_TEMP_DIR],
                "OPTIONS": {
                    "app_dir": "custom_templates",
                    "loaders": [
                        "render_static.loaders.StaticFilesystemLoader",
                        "render_static.loaders.StaticAppDirectoriesLoader",
                    ],
                },
            }
        ],
        "templates": {"nominal_fs.html": {}},
    }
)
class RenderErrorsTestCase(BaseTestCase):
    @override_settings(STATIC_ROOT=None)
    def test_render_no_dest(self):
        self.assertRaises(CommandError, lambda: call_command("renderstatic"))

    def test_render_default_static_root(self):
        call_command("renderstatic")
        self.assertTrue(
            filecmp.cmp(
                settings.STATIC_ROOT / "nominal_fs.html",
                EXPECTED_DIR / "nominal_fs.html",
                shallow=False,
            )
        )

    def test_render_missing(self):
        self.assertRaises(
            CommandError,
            lambda: call_command("renderstatic", "this/template/doesnt/exist.html"),
        )


class GenerateNothing(BaseTestCase):
    def generate_nothing(self):
        """
        When no templates are configured, render_static should generate nothing and it should not
        raise
        """
        call_command("renderstatic")
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
        # change in v2 - this no longer throws an exception
        call_command("renderstatic")


class TestContextResolution(BaseTestCase):
    def setUp(self):
        super().setUp()
        with open(BAD_PICKLE, "w") as bp:
            bp.write("not pickle content")
        with open(NOT_A_DICT_PICKLE, "wb") as bp:
            pickle.dump(["bad context"], bp)
        with open(CONTEXT_PICKLE, "wb") as cp:
            pickle.dump({"context": "pickle"}, cp)

    def test_pickle_context(self):
        self.assertEqual(
            resolve_context(Path(__file__).parent / "resources" / "context.pickle"),
            {"context": "pickle"},
        )

    def test_json_context(self):
        self.assertEqual(
            resolve_context(str(Path(__file__).parent / "resources" / "context.json")),
            {"context": "json"},
        )

    def test_python_context(self):
        self.assertEqual(
            resolve_context(Path(__file__).parent / "resources" / "context.py"),
            {"context": "python"},
        )

    def test_module_context(self):
        from tests import context

        self.assertEqual(
            resolve_context(context),
            {
                "VARIABLE1": "value1",
                "other_variable": "value2",
            },
        )

    def test_module_import_context(self):
        self.assertEqual(
            resolve_context("tests.context"),
            {
                "VARIABLE1": "value1",
                "other_variable": "value2",
            },
        )

    def test_pickle_context_resource(self):
        self.assertEqual(
            resolve_context(resource("tests.resources", "context.pickle")),
            {"context": "pickle"},
        )

    def test_json_context_resource(self):
        self.assertEqual(
            resolve_context(resource("tests.resources", "context.json")),
            {"context": "json"},
        )
        from tests import resources

        self.assertEqual(
            resolve_context(resource(resources, "context.json")), {"context": "json"}
        )

    def test_python_context_resource(self):
        self.assertEqual(
            resolve_context(resource("tests.resources", "context.py")),
            {"context": "python"},
        )

    def test_python_context_embedded_import(self):
        self.assertEqual(
            resolve_context("tests.resources.context_embedded.context"),
            {"context": "embedded"},
        )
        self.assertEqual(
            resolve_context("tests.resources.context_embedded.get_context"),
            {"context": "embedded_callable"},
        )

    def test_bad_contexts(self):
        self.assertRaises(
            InvalidContext,
            lambda: resolve_context("tests.resources.context_embedded.not_a_dict"),
        )
        self.assertRaises(
            InvalidContext,
            lambda: resolve_context(resource("tests.resources", "bad.pickle")),
        )
        self.assertRaises(
            InvalidContext,
            lambda: resolve_context(resource("tests.resources", "not_a_dict.pickle")),
        )
        self.assertRaises(
            InvalidContext,
            lambda: resolve_context(resource("tests.resources", "bad_code.py")),
        )
        self.assertRaises(
            InvalidContext,
            lambda: resolve_context(
                str(Path(__file__).parent / "resources" / "bad.yaml")
            ),
        )
        self.assertRaises(
            InvalidContext,
            lambda: resolve_context(
                str(Path(__file__).parent / "resources" / "bad.json")
            ),
        )
        self.assertRaises(
            InvalidContext,
            lambda: resolve_context(resource("tests.resources", "dne")),
        )

        self.assertRaises(
            InvalidContext,
            lambda: resolve_context(resource("tests.dne", "dne")),
        )

    def tearDown(self):
        super().tearDown()
        os.remove(BAD_PICKLE)
        os.remove(NOT_A_DICT_PICKLE)
        os.remove(CONTEXT_PICKLE)


@override_settings(
    STATIC_TEMPLATES={
        "templates": [
            (
                "app1/html/hello.html",
                {
                    "context": {"greeting": "HELLO", "to": "WORLD"},
                    "dest": GLOBAL_STATIC_DIR / "HELLO_U.html",
                },
            ),
            (
                "app1/html/hello.html",
                {
                    "context": {"greeting": "hello", "to": "world"},
                    "dest": GLOBAL_STATIC_DIR / "hello_l.html",
                },
            ),
        ]
    }
)
class MultipleDestinationsTestCase(BaseTestCase):
    """
    Tests that the same template may be configured to render to multiple
    destinations using different contexts when `templates` is configured as a
    list instead of a dictionary (added - v2.0.0).
    """

    def test_generate(self):
        call_command("renderstatic")
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "HELLO_U.html",
                EXPECTED_DIR / "HELLO_U.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "hello_l.html",
                EXPECTED_DIR / "hello_l.html",
                shallow=False,
            )
        )

    @override_settings(
        STATIC_TEMPLATES={
            "context": {**generate_context1(), **generate_context2()},
            "templates": [
                ("app1/html/hello.html", {}),
            ],
        }
    )
    def test_empty(self):
        call_command("renderstatic")
        self.assertTrue(
            filecmp.cmp(
                APP1_STATIC_DIR / "app1" / "html" / "hello.html",
                EXPECTED_DIR / "ctx_override.html",
                shallow=False,
            )
        )

    @override_settings(
        STATIC_TEMPLATES={
            "context": {**generate_context1(), **generate_context2()},
            "templates": [
                ("app1/html/hello.html", None),
            ],
        }
    )
    def test_none(self):
        call_command("renderstatic")
        self.assertTrue(
            filecmp.cmp(
                APP1_STATIC_DIR / "app1" / "html" / "hello.html",
                EXPECTED_DIR / "ctx_override.html",
                shallow=False,
            )
        )

    @override_settings(
        STATIC_TEMPLATES={
            "context": {**generate_context1(), **generate_context2()},
            "templates": [("app1/html/hello.html",)],
        }
    )
    def test_one_tuple(self):
        call_command("renderstatic")
        self.assertTrue(
            filecmp.cmp(
                APP1_STATIC_DIR / "app1" / "html" / "hello.html",
                EXPECTED_DIR / "ctx_override.html",
                shallow=False,
            )
        )

    @override_settings(
        STATIC_TEMPLATES={
            "context": {**generate_context1(), **generate_context2()},
            "templates": [
                "app1/html/hello.html",
                (
                    "app1/html/hello.html",
                    {
                        "context": {"greeting": "hello", "to": "world", "punc": ""},
                        "dest": GLOBAL_STATIC_DIR / "hello_l.html",
                    },
                ),
            ],
        }
    )
    def test_mixed_list(self):
        call_command("renderstatic")
        self.assertTrue(
            filecmp.cmp(
                APP1_STATIC_DIR / "app1" / "html" / "hello.html",
                EXPECTED_DIR / "ctx_override.html",
                shallow=False,
            )
        )
        self.assertTrue(
            filecmp.cmp(
                GLOBAL_STATIC_DIR / "hello_l.html",
                EXPECTED_DIR / "hello_l.html",
                shallow=False,
            )
        )

    # def tearDown(self):
    #     pass


class TranspilerTagTestCase(BaseTestCase):
    def test_invalid_args(self):
        from render_static.templatetags.render_static import transpiler_tag

        with self.assertRaises(ValueError):

            @transpiler_tag(func=True)
            def transpiler1():  # pragma: no cover
                pass  # pragma: no cover


BATCH_RENDER_TEMPLATES = [
    (
        "batch_test/**/*",
        {
            "context": {
                "site_name": "my_site",
                "variable1": "var1 value",
                "variable2": 2,
                "sub_dir": "resources",
            },
            "dest": GLOBAL_STATIC_DIR,
        },
    ),
    (
        "batch_test/{{ site_name }}",
        {
            "context": {"site_name": "my_site"},
            "dest": GLOBAL_STATIC_DIR / "batch_test" / "{{ site_name }}",
        },
    ),
    (
        "batch_test/{{ site_name }}/{{ sub_dir }}",
        {
            "context": {"site_name": "my_site", "sub_dir": "resources"},
            "dest": GLOBAL_STATIC_DIR
            / "batch_test"
            / "{{ site_name }}"
            / "{{ sub_dir }}",
        },
    ),
]


@override_settings(STATIC_TEMPLATES={"templates": BATCH_RENDER_TEMPLATES})
class BatchRenderTestCase(BaseTestCase):
    """
    Tests that batches of files can be rendered to paths that
    are also templates.
    """

    def test_render_empty_dir_template(self):
        call_command("renderstatic", "batch_test/{{ site_name }}")
        batch_test = GLOBAL_STATIC_DIR / "batch_test"
        my_site = batch_test / "my_site"
        self.assertTrue(batch_test.is_dir())
        self.assertTrue(my_site.is_dir())

    def test_render_empty_dir_template_multi_level(self):
        call_command("renderstatic", "batch_test/{{ site_name }}/{{ sub_dir }}")
        batch_test = GLOBAL_STATIC_DIR / "batch_test"
        my_site = batch_test / "my_site"
        resources = my_site / "resources"
        self.assertTrue(batch_test.is_dir())
        self.assertTrue(my_site.is_dir())
        self.assertTrue(resources.is_dir())

    def test_batch_render_path_templates(self):
        call_command("renderstatic", "batch_test/**/*")
        batch_test = GLOBAL_STATIC_DIR / "batch_test"
        my_site = batch_test / "my_site"
        resources = my_site / "resources"

        self.assertTrue(batch_test.is_dir())
        self.assertTrue((batch_test / "__init__.py").is_file())
        self.assertTrue(my_site.is_dir())
        self.assertTrue((my_site / "__init__.py").is_file())
        self.assertTrue(resources.is_dir())

        file1 = my_site / "file1.py"
        file2 = my_site / "file2.html"

        self.assertTrue(file1.is_file())
        self.assertTrue(file2.is_file())

        self.assertEqual(file1.read_text().strip(), "var1 value")
        self.assertEqual(file2.read_text().strip(), "2")

    # def tearDown(self):
    #     pass


class TestTabCompletion(BaseTestCase):
    def test_tab_completion(self):
        shellcompletion = get_command("shellcompletion")
        shellcompletion.init(shell="zsh")
        completions = shellcompletion.complete("renderstatic ")
        for expected in [
            "app1/html/base.html",
            "app1/html/hello.html",
            "app1/html/nominal2.html",
            "examples/enums.js",
        ]:
            self.assertTrue(expected.replace("/", os.sep) in completions)

        completions = shellcompletion.complete("renderstatic app1")

        for expected in [
            "app1/html/base.html",
            "app1/html/hello.html",
            "app1/html/nominal2.html",
        ]:
            self.assertTrue(expected.replace("/", os.sep) in completions)
        self.assertFalse("examples/enums.js".replace("/", os.sep) in completions)

        completions = shellcompletion.complete("renderstatic adfa3")
        self.assertEqual(completions.strip(), "")

        completions = shellcompletion.complete(
            f"renderstatic app1{os.sep}html{os.sep}base.html "
        )
        for expected in [
            "app1/html/hello.html",
            "app1/html/nominal2.html",
            "examples/enums.js",
        ]:
            self.assertTrue(expected.replace("/", os.sep) in completions)
        self.assertFalse("app1/html/base.html".replace("/", os.sep) in completions)

    @override_settings(
        STATIC_TEMPLATES={
            "ENGINES": [
                {
                    "BACKEND": "render_static.backends.StaticDjangoTemplates",
                    "OPTIONS": {
                        "loaders": [
                            (
                                "render_static.loaders.StaticLocMemLoader",
                                {
                                    "app1/urls.js": "a",
                                    "app1/enums.js": "b",
                                    "app1/examples/readme_url_usage.js": "c",
                                    "base.html": "d",
                                },
                            ),
                            "render_static.loaders.StaticAppDirectoriesBatchLoader",
                        ]
                    },
                }
            ],
            "templates": ["urls.js", "examples/readme_url_usage.js"],
        },
    )
    def test_loc_mem_completion(self):
        shellcompletion = get_command("shellcompletion")
        shellcompletion.init(shell="zsh")
        completions = shellcompletion.complete("renderstatic ")
        for expected in [
            "app1/html/base.html",
            "app1/html/hello.html",
            "app1/html/nominal2.html",
            "examples/enums.js",
            "base.html",
            "examples/enums.js",
        ]:
            self.assertTrue(expected.replace("/", os.sep) in completions)

        for expected in [
            "app1/urls.js",
            "app1/enums.js",
            "app1/examples/readme_url_usage.js",
        ]:
            self.assertTrue(expected in completions)

        completions = shellcompletion.complete("renderstatic app1/h")
        for expected in [
            f"app1/html{os.sep}base.html",
            f"app1/html{os.sep}hello.html",
            f"app1/html{os.sep}nominal2.html",
        ]:
            self.assertTrue(expected in completions)
        for expected in [
            "app1/urls.js",
            "examples/enums.js",
            "app1/examples/readme_url_usage.js",
            "examples/enums.js",
        ]:
            self.assertFalse(expected.replace("/", os.sep) in completions)


def test_batch_loader_mixin_not_impl():
    from render_static.loaders.mixins import BatchLoaderMixin

    try:
        BatchLoaderMixin().get_dirs()
        assert (  # pragma: no cover
            False
        ), 'BatchLoaderMixin.get_dirs() should raise "NotImplementedError"'
    except NotImplementedError:
        pass
