==========
Change Log
==========

v2.1.0
======
* Implemented `Add a pass through getter for enums_to_js transpilation. <https://github.com/bckohan/django-render-static/issues/126>`_
* Implemented `enum transpilation should iterate through value properties instead of hardcoding a switch statement. <https://github.com/bckohan/django-render-static/issues/125>`
* Implemented `Add type check and return to getter on transpiled enum classes.. <https://github.com/bckohan/django-render-static/issues/122>`_
* Implemented `Allow include_properties to be a list of properties on enums_to_js <https://github.com/bckohan/django-render-static/issues/119>`_


v2.0.3
======
* Fixed `Invalid URL generation for urls with default arguments. <https://github.com/bckohan/django-render-static/issues/124>`_


v2.0.2
======
* Fixed `Dependency bug, for python < 3.9 importlib_resource req should simply be >=1.3 <https://github.com/bckohan/django-render-static/issues/123>`_


v2.0.1
======
* Fixed `enums_to_js allows 'name' property through even if it is excluded. <https://github.com/bckohan/django-render-static/issues/120>`_


v2.0.0
======

**This is a major version upgrade - please see migration guide for instructions
on how to** :doc:`migration` **from version 1.x to 2.x.**

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

v1.1.6
====================

* Fixed `LICENSE is packaged as source. <https://github.com/bckohan/django-render-static/issues/95>`_

v1.1.5
====================

* Fixed `Support python 3.11 <https://github.com/bckohan/django-render-static/issues/77>`_
* Fixed `Drop support for python 3.6 <https://github.com/bckohan/django-render-static/issues/70>`_
* Fixed `Upgrade build tooling to poetry 1.2 <https://github.com/bckohan/django-render-static/issues/69>`_

v1.1.4
====================

* Fixed `urls_to_js output is incorrect when default kwargs specified in path() <https://github.com/bckohan/django-render-static/issues/65>`_

v1.1.3
====================

* Fixed `Django4.0 Support <https://github.com/bckohan/django-render-static/issues/45>`_

v1.1.2
====================

* Fixed `Jinja2 include breaks Jinja2 as optional dependency <https://github.com/bckohan/django-render-static/issues/34>`_

v1.1.1
====================

* Support for Jinja2 3.0
* Improved importlib.resources inclusion logic

v1.1.0
====================

* Added `Support batch rendering & glob patterns in template selectors <https://github.com/bckohan/django-render-static/issues/15>`_
* Fixed `Rename render_static -> renderstatic <https://github.com/bckohan/django-render-static/issues/11>`_
* Added `Allow 'lazy' contexts built after Django bootstrapping <https://github.com/bckohan/django-render-static/issues/6>`_
* Added `Flexible context specifiers <https://github.com/bckohan/django-render-static/issues/17>`_
* Added `Add GET query parameters to ClassURLWriter's reverse function <https://github.com/bckohan/django-render-static/issues/12>`_


v1.0.1
====================

* Fixed `Bound complexity of URL Generation <https://github.com/bckohan/django-render-static/issues/10>`_
* Fixed `Unnamed/named urls of the same name sometimes fail <https://github.com/bckohan/django-render-static/issues/9>`_
* Fixed `Default placeholders not activated <https://github.com/bckohan/django-render-static/issues/8>`_

v1.0.0
====================

* New abstract visitor pattern allows customization of generated URL resolution javascript
* A class generator is included which generates fully-fledged JavaScript class that includes a
  `reverse` function for urls that's directly analogous to Django's `reverse` function.
* More common placeholders have been added as defaults that are always attempted if no
  registered placeholders are found to work, this should increase the success rate of
  out-of-the box URL generation.
* Removed Jinja2 as a direct dependency - it is now in extras.
* API is now considered production/stable.


v0.1.1
====================

* Added common placeholders, and placeholders for allauth and DRF


v0.1.0
====================

* Initial Release

