============
Introduction
============

Use Django's template engines to render static files that are collected during the
:django-admin:`collectstatic` routine and likely served above Django at runtime. Files rendered by
django-render-static are immediately available to participate in the normal static file collection
pipeline.

For example, a frequently occurring pattern that violates the
`DRY principle <https://en.wikipedia.org/wiki/Don%27t_repeat_yourself>`_ is the presence of
defines, or enum like structures in server side Python code that are simply replicated in client
side JavaScript. Another example might be rebuilding Django URLs from arguments in a
`Single Page Application <https://en.wikipedia.org/wiki/Single-page_application>`_. Single-sourcing
these structures by transpiling client side code from the server side code keeps the stack bone
DRY.

:pypi:`django-render-static` includes Python to Javascript transpilers for:
    - Django's :func:`~django.urls.reverse` function (:templatetag:`urls_to_js`)
    - PEP 435 style Python enumerations (:templatetag:`enums_to_js`)
    - Plain data define-like structures in Python classes and modules
      (:templatetag:`defines_to_js`)


:pypi:`django-render-static` also formalizes the concept of a package-time or deployment-time
static file rendering step. It piggybacks off the existing templating engines and configurations
and should therefore be familiar to Django developers. It supports both standard Django templating
and Jinja templates and allows contexts to be specified in python, json or YAML.

You can report bugs and discuss features on the
`issues page <https://github.com/bckohan/django-render-static/issues>`_.

`Contributions <https://github.com/bckohan/django-render-static/blob/main/CONTRIBUTING.md>`_ are
encouraged! Especially additional template tags and filters!

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   quick
   configuration
   runtimes
   templatetags
   commands
   migration
   changelog
   reference/index
