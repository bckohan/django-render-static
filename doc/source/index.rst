============
Introduction
============

Use Django's template engines to render static files that are collected
during the ``collectstatic`` routine and likely served above Django at runtime.
Files rendered by django-render-static are immediately available to participate
in the normal static file collection pipeline.

For example, a frequently occurring pattern that violates the DRY principle is the presence of
defines, or enum like structures in server side Python code that are simply replicated in client
side JavaScript. Single-sourcing these structures by transpiling client side code from the server
side code keeps the stack bone DRY.

`django-render-static` includes Python to Javascript transpilers for:
    - Django's `reverse` function (`urls_to_js`)
    - PEP 435 style Python enumerations (`enums_to_js`)
    - Plain data define-like structures in Python classes and modules
      (`defines_to_js`)


You can report bugs and discuss features on the
`issues page <https://github.com/bckohan/django-render-static/issues>`_.

`Contributions <https://github.com/bckohan/django-render-static/blob/main/CONTRIBUTING.rst>`_ are
encouraged! Especially additional template tags and filters!

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   tldr
   configuration
   runtimes
   templatetags
   commands
   reference
   changelog
   migration

