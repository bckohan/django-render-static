import pytest
from django.test import override_settings

try:
    from render_static.backends.jinja2 import StaticJinja2Templates
    from render_static.loaders.jinja2 import StaticFileSystemBatchLoader
except ImportError:
    pytest.skip(allow_module_level=True, reason="Jinja2 is not installed")


from .test_batch import TestBatch, BATCH_TEMPLATES


@override_settings(
    STATIC_TEMPLATES={
        "ENGINES": [
            {
                "BACKEND": "render_static.backends.jinja2.StaticJinja2Templates",
                "OPTIONS": {
                    "loader": StaticFileSystemBatchLoader(searchpath=BATCH_TEMPLATES)
                },
            }
        ]
    }
)
class TestBatchJinja2(TestBatch):
    pass
