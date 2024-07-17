from pathlib import Path

from django.core.management import call_command
from django.test import override_settings
from .test_core import BaseTestCase, GLOBAL_STATIC_DIR

BATCH_TEMPLATES = Path(__file__).parent / "batch_templates"

context = {"variable": "template_rendered!"}


@override_settings(
    STATIC_TEMPLATES={
        "ENGINES": [
            {
                "BACKEND": "render_static.backends.StaticDjangoTemplates",
                "DIRS": [BATCH_TEMPLATES],
                "APP_DIRS": False,
                "OPTIONS": {
                    "loaders": ["render_static.loaders.StaticFilesystemBatchLoader"]
                },
            }
        ]
    }
)
class TestBatch(BaseTestCase):
    def check_file(self, filename, rendered=True, exists=True):
        filename = GLOBAL_STATIC_DIR / filename
        if exists:
            self.assertTrue(filename.is_file())
            if rendered:
                self.assertEqual(
                    filename.read_text().strip(),
                    f"{filename.name}: {context['variable']}",
                )
            else:
                self.assertEqual(
                    filename.read_text().strip(), f"{filename.name}: {{{{ variable }}}}"
                )
        else:
            self.assertFalse(filename.is_file())

    def test_batch_glob_all_render_all(self):
        call_command(
            "renderstatic",
            "**/*",
            destination=GLOBAL_STATIC_DIR,
            context="tests.test_batch.context",
        )

        self.check_file("file.txt")
        self.check_file("folder1/file1_1.txt")
        self.check_file("folder1/file1_2.txt")
        self.check_file("folder2/file2_1.txt")
        self.check_file("folder2/file2_2.txt")

    def test_batch_glob_some_render_all(self):
        call_command(
            "renderstatic",
            "folder1/**",
            destination=GLOBAL_STATIC_DIR,
            context="tests.test_batch.context",
        )

        self.check_file("file.txt", exists=False)
        self.check_file("folder1/file1_1.txt")
        self.check_file("folder1/file1_2.txt")
        self.check_file("folder2/file2_1.txt", exists=False)
        self.check_file("folder2/file2_2.txt", exists=False)

    def test_batch_glob_all_exclude_some(self):
        call_command(
            "renderstatic",
            "**/*",
            destination=GLOBAL_STATIC_DIR,
            context="tests.test_batch.context",
            exclude=[BATCH_TEMPLATES / "file.txt", BATCH_TEMPLATES / "folder1"],
        )

        self.check_file("file.txt", exists=False)
        self.check_file("folder1/file1_1.txt", exists=False)
        self.check_file("folder1/file1_2.txt", exists=False)
        self.check_file("folder2/file2_1.txt")
        self.check_file("folder2/file2_2.txt")

    def test_batch_glob_all_exclude_some_no_render(self):
        call_command(
            "renderstatic",
            "**/*",
            destination=GLOBAL_STATIC_DIR,
            context="tests.test_batch.context",
            exclude=[BATCH_TEMPLATES / "folder2"],
        )
        call_command(
            "renderstatic",
            "folder2/*",
            destination=GLOBAL_STATIC_DIR,
            context="tests.test_batch.context",
            no_render_contents=True,
        )

        self.check_file("file.txt")
        self.check_file("folder1/file1_1.txt")
        self.check_file("folder1/file1_2.txt")
        self.check_file("folder2/file2_1.txt", rendered=False)
        self.check_file("folder2/file2_2.txt", rendered=False)
