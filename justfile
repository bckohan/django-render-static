set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]
set unstable := true
set script-interpreter := ['uv', 'run', '--script']

export PYTHONPATH := source_directory()

[private]
default:
    @just --list --list-submodules

[script]
manage *COMMAND:
    import os
    import sys
    import shlex
    from pathlib import Path
    from django.core import management
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")
    management.execute_from_command_line(["just manage", *shlex.split("{{ COMMAND }}")])

# install the uv package manager
[linux]
[macos]
install-uv:
    curl -LsSf https://astral.sh/uv/install.sh | sh

# install the uv package manager
[windows]
install-uv:
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# setup the venv and pre-commit hooks
setup python="python":
    uv venv -p {{ python }}
    @just run pre-commit install

# install git pre-commit hooks
install-precommit:
    @just run pre-commit install

# update and install development dependencies
install *OPTS:
    uv sync --all-extras {{ OPTS }}
    @just run pre-commit install

# install without extra dependencies
install-basic:
    uv sync

# install documentation dependencies
install-docs:
    uv sync --group docs --all-extras

# lock to specific python and versions of given dependencies
test-lock +PACKAGES:
    uv add {{ PACKAGES }}

# run static type checking
check-types:
    @just run mypy
    @just run pyright

# run package checks
check-package:
    @just run pip check

# remove doc build artifacts
[script]
clean-docs:
    import shutil
    shutil.rmtree('./doc/build', ignore_errors=True)

# remove the virtual environment
[script]
clean-env:
    import shutil
    import sys
    shutil.rmtree(".venv", ignore_errors=True)

# remove all git ignored files
clean-git-ignored:
    git clean -fdX

# remove all non repository artifacts
clean: clean-docs clean-git-ignored clean-env

# build html documentation
build-docs-html: install-docs
    @just run sphinx-build --fresh-env --builder html --doctree-dir ./doc/build/doctrees ./doc/source ./doc/build/html

[script]
_open-pdf-docs:
    import webbrowser
    webbrowser.open(f"file://{Path('./doc/build/pdf/django-typer.pdf').absolute()}")

# build pdf documentation
build-docs-pdf: install-docs
    @just run sphinx-build --fresh-env --builder latex --doctree-dir ./doc/build/doctrees ./doc/source ./doc/build/pdf
    make -C ./doc/build/pdf
    @just _open_pdf-docs

# build the docs
build-docs: build-docs-html

# build src package and wheel
build:
    uv build

# open the html documentation
[script]
open-docs:
    import os
    import webbrowser
    webbrowser.open(f'file://{os.getcwd()}/doc/build/html/index.html')

# build and open the documentation
docs: build-docs-html open-docs

# serve the documentation, with auto-reload
docs-live: install-docs
    @just run sphinx-autobuild doc/source doc/build --open-browser --watch src --port 8000 --delay 1

_link_check:
    -uv run sphinx-build -b linkcheck -Q -D linkcheck_timeout=10 ./doc/source ./doc/build

# check the documentation links for broken links
[script]
check-docs-links: _link_check
    import os
    import sys
    import json
    from pathlib import Path
    # The json output isn't valid, so we have to fix it before we can process.
    data = json.loads(f"[{','.join((Path(os.getcwd()) / 'doc/build/output.json').read_text().splitlines())}]")
    broken_links = [link for link in data if link["status"] not in {"working", "redirected", "unchecked", "ignored"}]
    if broken_links:
        for link in broken_links:
            print(f"[{link['status']}] {link['filename']}:{link['lineno']} -> {link['uri']}", file=sys.stderr)
        sys.exit(1)

# lint the documentation
check-docs:
    @just run doc8 --ignore-path ./doc/build --max-line-length 100 -q ./doc

# lint the code
check-lint:
    @just run ruff check --select I
    @just run ruff check

# check if the code needs formatting
check-format:
    @just run ruff format --check

# check that the readme renders
check-readme:
    @just run python -m readme_renderer ./README.md -o /tmp/README.html

# sort the python imports
sort-imports:
    @just run ruff check --fix --select I

# format the code and sort imports
format: sort-imports
    just --fmt --unstable
    @just run ruff format

# sort the imports and fix linting issues
lint: sort-imports
    @just run ruff check --fix

# fix formatting, linting issues and import sorting
fix: lint format

# run all static checks
check: check-lint check-format check-types check-package check-docs check-docs-links check-readme

# run all tests
test-all:
    uv run --all-extras pytest --cov-append
    uv run --extra PyYAML --extra Jinja2 pytest --cov-append

# run tests
test *TESTS:
    uv run --all-extras pytest --cov-append {{ TESTS }}

# run the pre-commit checks
precommit:
    @just run pre-commit

# erase any coverage data
coverage-erase:
    @just run coverage erase

# generate the test coverage report
coverage:
    @just run coverage combine --keep *.coverage
    @just run coverage report
    @just run coverage xml

# run the command in the virtual environment
run +ARGS:
    uv run {{ ARGS }}

# validate the given version string against the lib version
[script]
validate_version VERSION:
    import re
    import tomllib
    import render_static
    from packaging.version import Version
    raw_version = "{{ VERSION }}".lstrip("v")
    version_obj = Version(raw_version)
    # the version should be normalized
    assert str(version_obj) == raw_version
    # make sure all places the version appears agree
    assert raw_version == tomllib.load(open('pyproject.toml', 'rb'))['project']['version']
    assert raw_version == render_static.__version__
    print(raw_version)

# issue a relase for the given semver string (e.g. 2.1.0)
release VERSION:
    @just validate_version v{{ VERSION }}
    git tag -s v{{ VERSION }} -m "{{ VERSION }} Release"
    git push origin v{{ VERSION }}
