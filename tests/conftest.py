import os
import sys

import pytest
from django import VERSION
from packaging.version import parse as parse_version


def pytest_configure(config: pytest.Config) -> None:
    if os.getenv("GITHUB_ACTIONS") == "true":
        # verify that the environment is set up correctly - this is used in CI to make
        # sure we're testing against the dependencies we think we are
        expected_python = os.getenv("TEST_PYTHON_VERSION")
        expected_django = os.getenv("TEST_DJANGO_VERSION", "").removeprefix("dj")
        if expected_django.isdigit():
            expected_django = ".".join(expected_django)

        if expected_python:
            expected_python = parse_version(expected_python)
            if sys.version_info[:2] != (expected_python.major, expected_python.minor):
                raise pytest.UsageError(
                    f"Python Version Mismatch: {sys.version_info[:2]} != "
                    f"{expected_python}"
                )

        if expected_django:
            dj_actual = VERSION[:2]
            expected_django = parse_version(expected_django)
            dj_expected = (expected_django.major, expected_django.minor)
            if dj_actual != dj_expected:
                raise pytest.UsageError(
                    f"Django Version Mismatch: {dj_actual} != {expected_django}"
                )
