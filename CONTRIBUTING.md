# Contributing

Contributions are welcome!! Please use the issue page to submit feature requests or
bug reports. Issues with attached PRs will be given priority and have a much higher likelihood of acceptance. Please also open an issue and associate it with any submitted PRs.

We are actively seeking additional maintainers. If you're interested, please
[contact me](https://github.com/bckohan).

## Installation

### Install Just

We provide a platform independent justfile with recipes for all the development tasks. You should [install just](https://just.systems/man/en/installation.html) if it is not on your system already.

`django-render-static` uses [uv](https://docs.astral.sh/uv) for environment, package, and dependency management. ``just setup`` will install the necessary build tooling if you do not already have it:

```shell
just setup <optional python version>
```

### External Dependencies

Some of the tests require [npm](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm) to be installed.


## Documentation

`django-render-static` documentation is generated using [Sphinx](https://www.sphinx-doc.org) with the [furo](https://github.com/pradyunsg/furo) theme. Any new feature PRs must provide updated documentation for the features added. To build the docs run doc8 to check for formatting issues then run Sphinx:

```sh
just docs  # builds docs
just check-docs  # lint the docs
just check-docs-links  # check for broken links in the docs
```

Run the docs with auto rebuild using:

```sh
just docs-live
```


## Static Analysis

`django-render-static` uses [ruff](https://docs.astral.sh/ruff) for Python linting, formatting and import sorting. Both [mypy](http://mypy-lang.org/) and [pyright](https://github.com/microsoft/pyright) are used for static type checking. Before any PR is accepted the following must be run, and static analysis tools should not produce any errors or warnings. Disabling certain errors or warnings where justified is acceptable:

```shell
just check
```

To fix formatting and linting problems that are fixable run:

```sh
just fix
```

## Running Tests

`django-render-static` is set up to use [pytest](https://docs.pytest.org) to run unit tests. All the tests are housed in `tests`. Before a PR is accepted, all tests must be passing and the code coverage must be at 100%. A small number of exempted error handling branches are acceptable.

To run the full suite in an isolated virtual environment with only the minimal test dependencies installed you should use ``test-all``:

```sh
just test-all
```
To run the full test suite against a specific python/django you can pass sync options to ``test-all``. This requires the djXX dependency groups. For example to run against python 3.11 on Django 5.2.x:

```sh
just test-all -p 3.11 --group dj52
```

The other test commands will use the current synced virtual environment. To run a single test, or group of tests in a class:

```sh
just install  # install the default dev environment if you haven't
just test <path_to_tests_file>::ClassName::FunctionName
```

For instance, to run all tests in DefinesToJavascriptTest, and then just the test_classes_to_js test you would do:

```shell
just test tests/test_js.py::DefinesToJavascriptTest
just test tests/test_js.py::DefinesToJavascriptTest::test_classes_to_js
```

### Debugging tests

To debug a test use the ``debug-test`` recipe:

```sh
just debug-test <path_to_tests_file>::ClassName::FunctionName
```

This will set a breakpoint at the start of the test.

To run specific tests or debug tests against specific Python or Django versions you must first sync:

```sh
just install -p 3.11 --group dj52
just test -k test_classes_to_js
just debug-test -k test_classes_to_js
```


## Versioning

We strictly adhere to [semantic versioning](https://semver.org).

## Issuing Releases

The release workflow is triggered by tag creation. You must have [git tag signing enabled](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits). Our justfile has a release shortcut:

```sh
    just release x.x.x
```

## Just Recipes

```
build                        # build src package and wheel
build-docs                   # build the docs
build-docs-html              # build html documentation
build-docs-pdf               # build pdf documentation
check *ENV                   # run all static checks
check-all *ENV               # run all checks including documentation link checking and zizmor
check-docs *ENV              # lint the documentation
check-docs-links             # check the documentation links for broken links
check-format *ENV            # check if the code needs formatting
check-lint *ENV              # lint the code
check-package                # run package checks
check-readme *ENV            # check that the readme renders
check-types *ENV             # run all static type checking
check-types-isolated *ENV    # run all static type checking in an isolated environment
check-types-mypy *ENV        # run static type checking with mypy
check-types-pyright *ENV     # run static type checking with pyright
clean                        # remove all non repository artifacts
clean-docs                   # remove doc build artifacts
clean-env                    # remove the virtual environment
clean-git-ignored            # remove all git ignored files
coverage                     # generate the test coverage report
coverage-erase               # erase any coverage data
debug-test *TESTS            # debug a test (project venv)
docs                         # build and open the documentation
docs-live                    # serve the documentation, with auto-reload
fetch-refs LIB               # fetch the intersphinx references for the given package
fix *ENV                     # fix formatting, linting issues and import sorting
format *ENV                  # format the code and sort imports
install *OPTS="--all-extras" # update and install development dependencies
install-basic                # install without extra dependencies
install-precommit            # install git pre-commit hooks
install-uv                   # install the uv package manager
lint *ENV                    # sort the imports and fix linting issues
manage *COMMAND              # run django-admin
open-docs                    # open the html documentation
precommit                    # run the pre-commit checks
release VERSION              # issue a release for the given semver string (e.g. 2.1.0)
run +ARGS                    # run the command in the virtual environment
setup python="python"        # setup the venv and pre-commit hooks
sort-imports *ENV            # sort the python imports
test *TESTS                  # run specific tests (project venv)
test-all *ENV                # run all tests (isolated venvs)
validate_version VERSION     # validate the given version string against the lib version
zizmor                       # run zizmor security analysis of CI
```
