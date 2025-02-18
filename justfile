set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]
set unstable := true

# list all available commands
default:
    @just --list

# install build tooling
init python="python":
    pip install pipx
    pipx ensurepath
    pipx install poetry
    poetry env use {{ python }}
    poetry run pip install --upgrade pip setuptools wheel

# install git pre-commit hooks
install-precommit:
    poetry run pre-commit install

# update and install development dependencies
install *OPTS:
    poetry lock
    poetry install -E PyYAML -E Jinja2 {{ OPTS }}
    poetry run pre-commit install

# install documentation dependencies
install-docs:
    poetry lock
    poetry install --with docs

# install a dependency to a specific version e.g. just pin-dependency Django~=5.1.0
pin-dependency +PACKAGES:
    poetry run pip install -U {{ PACKAGES }}

# run static type checking
check-types:
    poetry run mypy render_static
    poetry run pyright

# run package checks
check-package:
    poetry check
    poetry run pip check

# remove doc build artifacts
clean-docs:
    python -c "import shutil; shutil.rmtree('./doc/build', ignore_errors=True)"

# remove the virtual environment
clean-env:
    python -c "import shutil, sys; shutil.rmtree(sys.argv[1], ignore_errors=True)" $(poetry env info --path)

# remove all git ignored files
clean-git-ignored:
    git clean -fdX

# remove all non repository artifacts
clean: clean-docs clean-env clean-git-ignored

# build html documentation
build-docs-html: install-docs
    poetry run sphinx-build --fresh-env --builder html --doctree-dir ./doc/build/doctrees ./doc/source ./doc/build/html

# build pdf documentation
build-docs-pdf: install-docs
    poetry run sphinx-build --fresh-env --builder latexpdf --doctree-dir ./doc/build/doctrees ./doc/source ./doc/build/pdf

# build the docs
build-docs: build-docs-html

# build the wheel distribution
build-wheel:
    poetry build -f wheel

# build the source distribution
build-sdist:
    poetry build -f sdist

# build docs and package
build: build-docs-html
    poetry build

# open the html documentation
open-docs:
    poetry run python -c "import webbrowser; webbrowser.open('file://$(pwd)/doc/build/html/index.html')"

# build and open the documentation
docs: build-docs-html open-docs

# serve the documentation, with auto-reload
docs-live:
    poetry run sphinx-autobuild doc/source doc/build --open-browser --watch render_static --port 8000 --delay 1

# check the documentation links for broken links
check-docs-links:
    -poetry run sphinx-build -b linkcheck -Q -D linkcheck_timeout=10 ./doc/source ./doc/build
    poetry run python ./doc/broken_links.py

# lint the documentation
check-docs:
    poetry run doc8 --ignore-path ./doc/build --max-line-length 100 -q ./doc

# lint the code
check-lint:
    poetry run ruff check --select I
    poetry run ruff check

# check if the code needs formatting
check-format:
    poetry run ruff format --check

# check that the readme renders
check-readme:
    poetry run python -m readme_renderer ./README.md -o /tmp/README.html

# sort the python imports
sort-imports:
    poetry run ruff check --fix --select I

# format the code and sort imports
format: sort-imports
    just --fmt --unstable
    poetry run ruff format

# sort the imports and fix linting issues
lint: sort-imports
    poetry run ruff check --fix

# fix formatting, linting issues and import sorting
fix: lint format

# run all static checks
check: check-lint check-format check-types check-package check-docs check-docs-links check-readme

# run all tests
test-all:
    poetry run pytest --cov-append
    poetry run pip uninstall -y jinja2 pyyaml
    poetry run pytest --cov-append
    poetry install -E PyYAML -E Jinja2

# run tests
test *TESTS:
    poetry run pytest --cov-append {{ TESTS }}

# run the pre-commit checks
precommit:
    poetry run pre-commit

# generate the test coverage report
coverage:
    poetry run coverage combine --keep *.coverage
    poetry run coverage report
    poetry run coverage xml

# run the command in the virtual environment
run +ARGS:
    poetry run {{ ARGS }}
