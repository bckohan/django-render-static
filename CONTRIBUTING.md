# Contributing

Contributions are encouraged and welcome!! Please use the issue page to submit feature requests or
bug reports. Issues with attached PRs will be given priority and have a much higher likelihood of
acceptance. Please also open an issue and associate it with any submitted PRs.

We are actively seeking additional maintainers. If you're interested, please
[contact me](https://github.com/bckohan).


## Installation

`django-render-static` uses [Poetry](https://python-poetry.org/) for environment, package and
dependency management. [Poetry](https://python-poetry.org/) greatly simplifies environment
bootstrapping. Once it's installed.

```shell
poetry install -E all
```

### External Dependencies

Some of the tests require [npm](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm)
to be installed.

## Documentation

`django-render-static` documentation is generated using
[Sphinx](https://www.sphinx-doc.org/en/master/) with the [readthedocs](https://readthedocs.org/)
theme. Any new feature PRs must provide updated documentation for the features added. To build
the docs run:

```shell
cd ./doc
poetry run doc8 --ignore-path build --max-line-length 100
poetry run make html
```

## Static Analysis

`django-render-static` uses [Pylint](https://www.pylint.org/) for Python linting and
[mypy](http://mypy-lang.org/) for type checking. Header imports are also standardized using
[isort](https://pycqa.github.io/isort/). Before any PR is accepted the following must be run, and
static analysis tools should not produce any errors or warnings. Disabling certain errors or
warnings where justified is acceptable:

```shell
poetry run isort render_static
poetry run black render_static
poetry run mypy render_static
poetry run pylint render_static
poetry check
poetry run pip check
poetry run python -m readme_renderer ./README.md
```

## Running Tests

`django-render-static` is setup to use
[django-pytest](https://pytest-django.readthedocs.io/en/latest/) to allow
[pytest](https://docs.pytest.org/en/stable/) to run Django unit tests. All the tests are housed in
render_static/tests/tests.py. Before a PR is accepted, all tests must be passing and the code
coverage must be at 100%.

To run the full suite:

```shell
poetry run pytest
```

To run a single test, or group of tests in a class:

```shell
poetry run pytest <path_to_tests_file>::ClassName::FunctionName
```

For instance to run all tests in DefinesToJavascriptTest, and then just the test_classes_to_js test
you would do:

```shell
poetry run pytest render_static/tests/tests.py::DefinesToJavascriptTest
poetry run pytest render_static/tests/tests.py::DefinesToJavascriptTest::test_classes_to_js
```
