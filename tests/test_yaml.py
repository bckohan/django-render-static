# pragma: no cover
import filecmp
from pathlib import Path

import pytest
from django.core.management import call_command
from django.test import override_settings
from render_static.context import InvalidContext
from tests.test_core import (
    APP1_STATIC_DIR,
    EXPECTED_DIR,
    BaseTestCase,
    resolve_context,
)

try:
    import yaml
except ImportError:
    yaml = None


class TestYAMLContext(BaseTestCase):
    @pytest.mark.skipif(not yaml, reason="PyYAML is not installed")
    def test_yaml_context(self):
        self.assertEqual(
            resolve_context(str(Path(__file__).parent / "resources" / "context.yaml")),
            {"context": "yaml"},
        )

    @pytest.mark.skipif(yaml is not None, reason="PyYAML is installed")
    def test_yaml_uninstalled_context(self):
        with self.assertRaises(InvalidContext):
            resolve_context(str(Path(__file__).parent / "resources" / "context.yaml"))


@pytest.mark.skipif(not yaml, reason="PyYAML is not installed")
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
class TestYAMLContextOverride(BaseTestCase):
    """
    Tests that per template contexts override global contexts and that the
    global context is also used.
    """

    def test_command_line_override(self):
        call_command(
            "renderstatic",
            context=str(Path(__file__).parent / "resources" / "override.yaml"),
        )
        self.assertTrue(
            filecmp.cmp(
                APP1_STATIC_DIR / "app1" / "html" / "hello.html",
                EXPECTED_DIR / "ctx_override_cmdline.html",
                shallow=False,
            )
        )


@pytest.mark.skipif(yaml, reason="PyYAML is installed")
class TestYAMLMissingImport(BaseTestCase):
    """
    Tests that per template contexts override global contexts and that the
    global context is also used.
    """

    def test_no_yaml_error_on_load(self):
        from render_static.context import yaml_load

        with self.assertRaises(ImportError):
            yaml_load()
