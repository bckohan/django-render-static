.. _ref-commands:

========
Commands
========

render_static
---------------

.. automodule:: render_static.management.commands.render_static

Usage
~~~~~

.. argparse::
    :module: render_static.management.commands.render_static
    :func: get_parser
    :prog: manage.py

Example
~~~~~~~

To generate all templates configured in ``STATIC_TEMPLATES`` settings:

.. code::

    $ manage.py render_static

Alternatively individual templates can be generated, regardless of their presence
in ``STATIC_TEMPLATES``. They will be given the global context:

.. code::

    $ manage.py render_static name/of/template1.js name/of/template2.js

