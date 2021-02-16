.. _ref-commands:

========
Commands
========

generate_static
---------------

.. automodule:: django_static_templates.management.commands.generate_static

Usage
~~~~~

.. argparse::
    :module: django_static_templates.management.commands.generate_static
    :func: get_parser
    :prog: manage.py

Example
~~~~~~~

To generate all templates configured in ``STATIC_TEMPLATES`` settings:

.. code::

    $ manage.py generate_static

Alternatively individual templates can be generated, regardless of their presence
in ``STATIC_TEMPLATES``. They will be given the global context:

.. code::

    $ manage.py generate_static name/of/template1.js name/of/template2.js

