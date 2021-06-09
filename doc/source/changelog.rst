==========
Change Log
==========

v1.1.0
====================

* Fixed `Rename render_static -> renderstatic <https://github.com/bckohan/django-render-static/issues/11>`_
* Fixed `Richer contexts <https://github.com/bckohan/django-render-static/issues/6>`_
* Fixed `Add GET query parameters to ClassURLWriter's reverse function <https://github.com/bckohan/django-render-static/issues/12>`_


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

