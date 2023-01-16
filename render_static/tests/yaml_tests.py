# pragma: no cover
from render_static.tests.tests import (
    BaseTestCase,
    resolve_context,
    APP1_STATIC_DIR,
    EXPECTED_DIR
)
import filecmp
from pathlib import Path
from django.test import override_settings
from django.core.management import call_command
import pytest

pytest.importorskip("yaml")


class TestYAMLContext(BaseTestCase):

    def test_yaml_context(self):
        self.assertEqual(
            resolve_context(
                str(Path(__file__).parent / 'resources' / 'context.yaml')
            ),
            {'context': 'yaml'}
        )


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
class TestYAMLContextOverride(BaseTestCase):
    """
    Tests that per template contexts override global contexts and that the
    global context is also used.
    """

    def test_command_line_override(self):
        call_command(
            'renderstatic',
            context=str(Path(__file__).parent / 'resources' / 'override.yaml')
        )
        self.assertTrue(filecmp.cmp(
            APP1_STATIC_DIR / 'app1' / 'html' / 'hello.html',
            EXPECTED_DIR / 'ctx_override_cmdline.html',
            shallow=False
        ))
