# Contributing

Contributions are encouraged and welcome!! Please use the issue page to submit feature requests or
bug reports. Issues with attached PRs will be given priority and have a much higher likelihood of
acceptance. Please also open an issue and associate it with any submitted PRs.

We are actively seeking additional maintainers. If you're interested, please
[contact me](https://github.com/bckohan).


## Installation

### Install Just

We provide a platform independent justfile with recipes for all the development tasks. You should [install just](https://just.systems/man/en/installation.html) if it is not on your system already.

`django-render-static` uses [Poetry](https://python-poetry.org/) for environment, package, and dependency management. ``just init`` will install the necessary build tooling if you do not already have it:

```shell
just init
just install
```

### External Dependencies

Some of the tests require [npm](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm)
to be installed.


## Documentation

`django-render-static` documentation is generated using [Sphinx](https://www.sphinx-doc.org) with the [furo](https://github.com/pradyunsg/furo) theme. Any new feature PRs must provide updated documentation for the features added. To build the docs run doc8 to check for formatting issues then run Sphinx:

```bash
just docs  # builds docs
just check-docs  # lint the docs
just check-docs-links  # check for broken links in the docs
```

Run the docs with auto rebuild using:

```bash
just docs-live
```


## Static Analysis

`django-render-static` uses [Pylint](https://www.pylint.org/) for Python linting and
[mypy](http://mypy-lang.org/) for type checking. Header imports are also standardized using
[isort](https://pycqa.github.io/isort/). Before any PR is accepted the following must be run, and
static analysis tools should not produce any errors or warnings. Disabling certain errors or
warnings where justified is acceptable:

```shell
./check.sh
poetry run python -m readme_renderer ./README.md
```

## Static Analysis

`django-render-static` uses [ruff](https://docs.astral.sh/ruff/) for Python linting, header import standardization and code formatting. [mypy](http://mypy-lang.org/) and [pyright](https://github.com/microsoft/pyright) are used for static type checking. Before any PR is accepted the following must be run, and static analysis tools should not produce any errors or warnings. Disabling certain errors or warnings where justified is acceptable:

To fix formatting and linting problems that are fixable run:

```bash
just fix
```

To run all static analysis without automated fixing you can run:

```bash
just check
```

## Running Tests

`django-render-static` is set up to use [pytest](https://docs.pytest.org) to run unit tests. All the tests are housed in `tests`. Before a PR is accepted, all tests must be passing and the code coverage must be at 100%. A small number of exempted error handling branches are acceptable.

To run the full suite:

```shell
just test-all
```

To run a single test, or group of tests in a class:

```shell
just test <path_to_tests_file>::ClassName::FunctionName
```

For instance, to run all tests in DefinesToJavascriptTest, and then just the test_classes_to_js test you would do:

```shell
just test tests/test_js.py::DefinesToJavascriptTest
just test tests/test_js.py::DefinesToJavascriptTest::test_classes_to_js
```


## Versioning

django-render-static strictly adheres to [semantic versioning](https://semver.org).


## Just Recipes

```
build                    # build docs and package
build-docs               # build the docs
build-docs-html          # build html documentation
build-docs-pdf           # build pdf documentation
build-sdist              # build the source distribution
build-wheel              # build the wheel distribution
check                    # run all static checks
check-docs               # lint the documentation
check-docs-links         # check the documentation links for broken links
check-format             # check if the code needs formatting
check-lint               # lint the code
check-package            # run package checks
check-readme             # check that the readme renders
check-types              # run static type checking
clean                    # remove all non repository artifacts
clean-docs               # remove doc build artifacts
clean-env                # remove the virtual environment
clean-git-ignored        # remove all git ignored files
coverage                 # generate the test coverage report
default                  # list all available commands
docs                     # build and open the documentation
docs-live                # serve the documentation, with auto-reload
fix                      # fix formatting, linting issues and import sorting
format                   # format the code and sort imports
init python="python"     # install build tooling
install *OPTS            # update and install development dependencies
install-docs             # install documentation dependencies
install-precommit        # install git pre-commit hooks
lint                     # sort the imports and fix linting issues
open-docs                # open the html documentation
pin-dependency +PACKAGES # install a dependency to a specific version e.g. just pin-dependency Django~=5.1.0
precommit                # run the pre-commit checks
run +ARGS                # run the command in the virtual environment
sort-imports             # sort the python imports
test *TESTS              # run tests
test-all                 # run all tests
```
