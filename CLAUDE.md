# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## About

`django-render-static` is a Django app that uses Django's template engines to render static files at deployment/package time. It includes Python-to-JavaScript transpilers for:
- Django's `reverse` function (`urls_to_js` template tag)
- PEP 435 Python enumerations (`enums_to_js` template tag)
- Plain data define-like structures (`defines_to_js` template tag)

## Commands

The project uses [just](https://just.systems) for task automation and [uv](https://docs.astral.sh/uv) for environment/package management.

```shell
just setup          # create venv and install pre-commit hooks
just install        # sync all dev dependencies
just test           # run tests (with extras, uses project venv)
just test-all       # run full test suite in isolated venvs (with and without optional extras)
just test tests/test_js.py::ClassName::test_method  # run a specific test
just check          # run all static checks (lint, format, types, docs, readme)
just fix            # auto-fix formatting and linting issues
just check-types    # run mypy + pyright
just run <cmd>      # run any command in the venv
just manage <cmd>   # run Django management commands using tests.settings
```

Tests use `pytest-django` with `DJANGO_SETTINGS_MODULE=tests.settings`. The `just test-all` recipe runs the suite twice in isolated venvs: once with all optional extras (PyYAML, Jinja2) and once without.

In CI, Django version matrix entries are `dj42`/`dj52`/`dj60` — these map to `[dependency-groups]` in `pyproject.toml` and are passed as `--group` flags to `uv run --isolated`. No `test-lock` or venv mutation is needed.

100% code coverage is required before PRs are accepted.

## Architecture

### Core Flow

1. `STATIC_TEMPLATES` setting configures engines, global context, and templates to render
2. `StaticTemplateEngine` (`src/render_static/engine.py`) orchestrates rendering — resolves templates from backends, merges contexts, and writes output to disk
3. The `renderstatic` management command (`src/render_static/management/commands/renderstatic.py`) drives the engine from the CLI
4. Rendered files land in each app's `static/` directory (or `STATIC_ROOT`) and then participate in the normal `collectstatic` pipeline

### Key Components

- **`src/render_static/engine.py`** — `StaticTemplateEngine`: central orchestrator; `Render` namedtuple holds selector, config, template, and destination for each rendering job
- **`src/render_static/backends/`** — `StaticDjangoTemplates` and `StaticJinja2Templates` extend Django's backends; `StaticEngine` ABC defines `select_templates` and `search_templates`
- **`src/render_static/loaders/`** — custom template loaders (Django and Jinja2 variants) that look in `static_templates/` app directories instead of `templates/`; include batch/glob support via `mixins.py`
- **`src/render_static/transpilers/`** — transpiler classes invoked by template tags:
  - `base.py` — `Transpiler` ABC + `to_js`/`to_js_datetime` utilities
  - `urls_to_js.py` — `ClassURLWriter`, `SimpleURLWriter`
  - `enums_to_js.py` — `EnumClassWriter`
  - `defines_to_js.py` — `DefaultDefineTranspiler`
- **`src/render_static/templatetags/render_static.py`** — `urls_to_js`, `enums_to_js`, `defines_to_js` template tags that invoke transpilers
- **`src/render_static/placeholders.py`** — registry for URL argument placeholders used during URL transpilation
- **`src/render_static/context.py`** — resolves context from dicts, callables, or importable strings; supports JSON/YAML files

### Template Discovery

Static templates are stored in `static_templates/` subdirectories within Django apps (analogous to `templates/`). Loaders discover these directories via Django's app registry. The `STATIC_TEMPLATES` setting mirrors the structure of Django's `TEMPLATES` setting.

### Optional Dependencies

- `PyYAML` — enables YAML context files
- `Jinja2` — enables Jinja2 backend (`StaticJinja2Templates`)

### Testing

- `tests/settings.py` — test Django settings (SQLite in-memory, multiple test apps installed)
- Test apps: `tests/app1`, `tests/app2`, `tests/app3`, `tests/enum_app`, `tests/examples`, `tests/spa`, `tests/chain`, `tests/traverse`
- Key test files: `test_js.py` (transpilers), `test_core.py` (engine/loaders), `test_jinja2.py`, `test_web.py` (Selenium), `test_yaml.py`
- `tests/conftest.py` — `pytest_configure` hook verifies `TEST_PYTHON_VERSION`/`TEST_DJANGO_VERSION` env vars match the active interpreter and Django install when running in GitHub Actions
- `test_web.py` requires npm and Selenium for browser-based JavaScript validation
