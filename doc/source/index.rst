============
Introduction
============

Use Django's dynamic templates to render static files. That is, files that are collected
during the ``collectstatic`` routine and likely served above Django on the stack. Static
templates should be rendered preceding any run of ``collectstatic``.

For example, a frequently occurring pattern that violates the DRY principle is the presence of
defines, or enum like structures in server side Python code that are simply replicated in client
side JavaScript. Single-sourcing these structures by generating client side code from the server
side code maintains DRYness.

Have you ever wished you could replicate Django's `reverse` function in a JavaScript library for
your site? Now you can with the `urls_to_js` template tag included with `django-render-static`.

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
   templatetags
   commands
   reference
   changelog
