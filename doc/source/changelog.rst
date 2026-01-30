==========
Change Log
==========

v3.5.1 (2026-01-30)
===================

* Add context intersphinx ref to docs.

v3.5.0 (2026-01-29)
===================

* Move template :mod:`shell completer logic <render_static.management.completers>` to separate
  module for reuse.

v3.4.0 (2025-11-22)
===================

* `Drop support for Django 3.2-4.1 and 5.0 <https://github.com/bckohan/django-render-static/issues/204>`_
* `Drop support for python 3.9 <https://github.com/bckohan/django-render-static/issues/203>`_


v3.3.4 (2025-09-27)
===================

* Support for Django 6.0 - test against alpha


v3.3.3 (2025-09-22)
===================

* Add support for Python 3.14


v3.3.2 (2025-07-18)
===================

* Docs: change autodoc configuration to make type hints more legible, reorganize reference section


v3.3.1 (2025-07-16)
===================

* Added `Convert docs to intersphinx references. <https://github.com/bckohan/django-render-static/issues/187>`_


v3.3.0 (2025-03-12)
====================

* Fixed `True/False values transpiled as True/False instead of true/false <https://github.com/bckohan/django-render-static/issues/179>`_
* Implemented `Move from poetry -> uv <https://github.com/bckohan/django-render-static/issues/178>`_
* Implemented `Support Django 5.2 <https://github.com/bckohan/django-render-static/issues/177>`_


v3.2.1 (2025-02-17)
====================

* Fixed `webdriver-manager included as non-dev dependency in 3.2.0 <https://github.com/bckohan/django-render-static/issues/175>`_


v3.2.0 (2025-02-17)
====================

* Fixed `Batch loading jinja templates on windows using wildcards is broken. <https://github.com/bckohan/django-render-static/issues/173>`_
* Fixed `Permissions errors when searching template directories on windows. <https://github.com/bckohan/django-render-static/issues/172>`_
* Implemented `Drop support for python 3.8 <https://github.com/bckohan/django-render-static/issues/171>`_
* Implemented `Support django-typer 3.x <https://github.com/bckohan/django-render-static/issues/170>`_


v3.1.3 (2024-08-26)
====================

* Fixed `Switch to furo theme on rtd <https://github.com/bckohan/django-render-static/issues/165>`_
* Fixed `Support python 3.13 <https://github.com/bckohan/django-render-static/issues/164>`_

v3.1.2 (2024-07-18)
====================

* Fixed `BatchLoaders should not try to load pycache files. <https://github.com/bckohan/django-render-static/issues/160>`_

v3.1.1 (2024-07-18)
====================

* Fixed `__pycache__ dirs should be ignored during batch rendering. <https://github.com/bckohan/django-render-static/issues/158>`_

v3.1.0 (2024-07-16)
====================

* Implemented `Support a no-render copy operation where the path may be a template. <https://github.com/bckohan/django-render-static/issues/156>`_

v3.0.1 (2024-07-15)
====================

* Implemented `Support Django 5.1 <https://github.com/bckohan/django-render-static/issues/153>`_

v3.0.0 (2024-06-07)
====================

**This is a major version upgrade - please see migration guide for instructions
on how to** :ref:`migrate from version 2.x to 3.x. <migration_2_3>`

* Implemented `Move tests into top level directory. <https://github.com/bckohan/django-render-static/issues/149>`_
* Implemented `Remove wrapped dependency required mishegoss and replace with jinja2 module level imports <https://github.com/bckohan/django-render-static/issues/148>`_
* Implemented `Allow context import path to also point to a module. <https://github.com/bckohan/django-render-static/issues/147>`_
* Implemented `Remove imports in __init__.py <https://github.com/bckohan/django-render-static/issues/146>`_
* Implemented `Switch to ruff for formatting and linting <https://github.com/bckohan/django-render-static/issues/145>`_
* Fixed `Support django-typer version 2.1 <https://github.com/bckohan/django-render-static/issues/144>`_


v2.2.1 (2024-04-11)
====================

* Fixed `Custom URL converts may expect reversal kwargs to be of a given type. <https://github.com/bckohan/django-render-static/issues/141>`_
* Fixed `Switch README and CONTRIBUTING to markdown. <https://github.com/bckohan/django-render-static/issues/140>`_

v2.2.0 (2024-02-27)
====================

* Implemented `Refactor renderstatic command using TyperCommand <https://github.com/bckohan/django-render-static/issues/137>`_
* Implemented `Allow enum class writer to_string parameter to be the name of a property to return from toString() <https://github.com/bckohan/django-render-static/issues/132>`_

v2.1.3 (2023-12-12)
====================

* Fixed `Support Django 5.0 <https://github.com/bckohan/django-render-static/issues/136>`_


v2.1.2 (2023-11-21)
====================

* Fixed `deepEqual should only be included by ClassURLWriter when Django version is less than 4.1 <https://github.com/bckohan/django-render-static/issues/134>`_
* Fixed `deepEqual generated code in ClassURLWriter has an error <https://github.com/bckohan/django-render-static/issues/133>`_

v2.1.1 (2023-11-20)
====================

* Fixed `include_properties can result in non-deterministic ordering of constructor parameters that changes render to render <https://github.com/bckohan/django-render-static/issues/131>`_

v2.1.0 (2023-11-20)
====================
* Implemented `Support templating of destination paths. <https://github.com/bckohan/django-render-static/issues/129>`_
* Implemented `Support configurable case insensitive property mapping on enum transpilation. <https://github.com/bckohan/django-render-static/issues/128>`_
* Implemented `Add a pass through getter for enums_to_js transpilation. <https://github.com/bckohan/django-render-static/issues/126>`_
* Implemented `enum transpilation should iterate through value properties instead of hardcoding a switch statement. <https://github.com/bckohan/django-render-static/issues/125>`_
* Implemented `Add type check and return to getter on transpiled enum classes.. <https://github.com/bckohan/django-render-static/issues/122>`_
* Implemented `Provide switch to turn off toString() transpilation on enums_to_js <https://github.com/bckohan/django-render-static/issues/121>`_
* Implemented `Allow include_properties to be a list of properties on enums_to_js <https://github.com/bckohan/django-render-static/issues/119>`_
* Implemented `Extension points for transpiled code. <https://github.com/bckohan/django-render-static/issues/104>`_

v2.0.3 (2023-11-09)
====================
* Fixed `Invalid URL generation for urls with default arguments. <https://github.com/bckohan/django-render-static/issues/124>`_


v2.0.2 (2023-10-26)
====================
* Fixed `Dependency bug, for python < 3.9 importlib_resource req should simply be >=1.3 <https://github.com/bckohan/django-render-static/issues/123>`_


v2.0.1 (2023-10-24)
====================
* Fixed `enums_to_js allows 'name' property through even if it is excluded. <https://github.com/bckohan/django-render-static/issues/120>`_


v2.0.0 (2023-10-21)
====================

**This is a major version upgrade - please see migration guide for instructions
on how to** :ref:`migrate from version 1.x to 2.x. <migration_1_2>`

* Implemented `Add some default templates to ship for defines, urls and enums. <https://github.com/bckohan/django-render-static/issues/116>`_
* Implemented `Generate JDoc comments in the generated URLResolver class. <https://github.com/bckohan/django-render-static/issues/115>`_
* Implemented `Include render_static filters and tags in engine be default. <https://github.com/bckohan/django-render-static/issues/113>`_
* Implemented `Exclude admin urls by default from urls_to_js output <https://github.com/bckohan/django-render-static/issues/112>`_
* Implemented `Remove multi-arg call style from url reverse() <https://github.com/bckohan/django-render-static/issues/96>`_
* Implemented `Test re_path nested arguments <https://github.com/bckohan/django-render-static/issues/93>`_
* Implemented `Combine classes_to_js and modules_to_js into defines_to_js <https://github.com/bckohan/django-render-static/issues/91>`_
* Implemented `Unify all transpilation tags as specializations of {% transpile %}  <https://github.com/bckohan/django-render-static/issues/90>`_
* Implemented `Change all filters to tags  <https://github.com/bckohan/django-render-static/issues/88>`_
* Implemented `Deprecate es5 support. <https://github.com/bckohan/django-render-static/issues/87>`_
* Implemented `Refactor classes_to_js and modules_to_js to use JavascriptGenerator pattern. <https://github.com/bckohan/django-render-static/issues/86>`_
* Implemented `Provide customization point for all javascript value output. <https://github.com/bckohan/django-render-static/issues/85>`_
* Implemented `Set the urls_to_js default visitor to the Class visitor <https://github.com/bckohan/django-render-static/issues/83>`_
* Implemented `urls_to_js namespace argument  <https://github.com/bckohan/django-render-static/issues/82>`_
* Implemented `Change templates config parameter to be a list of tuples. <https://github.com/bckohan/django-render-static/issues/81>`_
* Implemented `Require importlib-resources for python < 3.9 <https://github.com/bckohan/django-render-static/issues/80>`_
* Implemented `Conditionally collect tests requiring optional dependencies <https://github.com/bckohan/django-render-static/issues/79>`_
* Implemented `Implement node.js tests for all js2py tests. <https://github.com/bckohan/django-render-static/issues/78>`_
* Implemented `Drop support for python 3.6 <https://github.com/bckohan/django-render-static/issues/70>`_
* Implemented `Upgrade build tooling to poetry 1.2 <https://github.com/bckohan/django-render-static/issues/69>`_
* Implemented `Deprecate render_static command in favor of renderstatic. <https://github.com/bckohan/django-render-static/issues/67>`_
* Implemented `urls_to_js should gracefully handle default kwargs supplied to path() <https://github.com/bckohan/django-render-static/issues/66>`_
* Implemented `Document deployment time vs package time use cases. <https://github.com/bckohan/django-render-static/issues/64>`_
* Fixed `Max line length from 100 -> 80 <https://github.com/bckohan/django-render-static/issues/63>`_
* Implemented `Port all DTL filters and tags to Jinja2 <https://github.com/bckohan/django-render-static/issues/25>`_
* Fixed `Multilevel url arguments not working <https://github.com/bckohan/django-render-static/issues/13>`_
* Implemented `Enum support <https://github.com/bckohan/django-render-static/issues/4>`_

v1.1.6 (2023-02-15)
====================

* Fixed `LICENSE is packaged as source. <https://github.com/bckohan/django-render-static/issues/95>`_

v1.1.5 (2023-01-16)
====================

* Fixed `Support python 3.11 <https://github.com/bckohan/django-render-static/issues/77>`_
* Fixed `Drop support for python 3.6 <https://github.com/bckohan/django-render-static/issues/70>`_
* Fixed `Upgrade build tooling to poetry 1.2 <https://github.com/bckohan/django-render-static/issues/69>`_

v1.1.4 (2022-08-20)
====================

* Fixed `urls_to_js output is incorrect when default kwargs specified in path() <https://github.com/bckohan/django-render-static/issues/65>`_

v1.1.3 (2022-01-18)
====================

* Fixed `Django4.0 Support <https://github.com/bckohan/django-render-static/issues/45>`_

v1.1.2 (2021-10-08)
====================

* Fixed `Jinja2 include breaks Jinja2 as optional dependency <https://github.com/bckohan/django-render-static/issues/34>`_

v1.1.1 (2021-07-12)
====================

* Support for Jinja2 3.0
* Improved importlib.resources inclusion logic

v1.1.0 (2021-06-12)
====================

* Added `Support batch rendering & glob patterns in template selectors <https://github.com/bckohan/django-render-static/issues/15>`_
* Fixed `Rename render_static -> renderstatic <https://github.com/bckohan/django-render-static/issues/11>`_
* Added `Allow 'lazy' contexts built after Django bootstrapping <https://github.com/bckohan/django-render-static/issues/6>`_
* Added `Flexible context specifiers <https://github.com/bckohan/django-render-static/issues/17>`_
* Added `Add GET query parameters to ClassURLWriter's reverse function <https://github.com/bckohan/django-render-static/issues/12>`_


v1.0.1 (2021-04-24)
====================

* Fixed `Bound complexity of URL Generation <https://github.com/bckohan/django-render-static/issues/10>`_
* Fixed `Unnamed/named urls of the same name sometimes fail <https://github.com/bckohan/django-render-static/issues/9>`_
* Fixed `Default placeholders not activated <https://github.com/bckohan/django-render-static/issues/8>`_

v1.0.0 (2021-04-21)
====================

* New abstract visitor pattern allows customization of generated URL resolution javascript
* A class generator is included which generates fully-fledged JavaScript class that includes a
  `reverse` function for urls that's directly analogous to Django's `reverse` function.
* More common placeholders have been added as defaults that are always attempted if no
  registered placeholders are found to work, this should increase the success rate of
  out-of-the box URL generation.
* Removed Jinja2 as a direct dependency - it is now in extras.
* API is now considered production/stable.


v0.1.1 (2021-03-02)
====================

* Added common placeholders, and placeholders for allauth and DRF


v0.1.0 (2021-02-24)
====================

* Initial Release

