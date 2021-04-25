.. _ref-commands:

========
Commands
========

.. _renderstatic:

renderstatic
------------

.. automodule:: render_static.management.commands.renderstatic

Usage
~~~~~

.. argparse::
    :module: render_static.management.commands.renderstatic
    :func: get_parser
    :prog: manage.py

Example
~~~~~~~

To generate all templates configured in ``STATIC_TEMPLATES`` settings:

.. code::

    $ manage.py renderstatic

Alternatively individual templates can be generated, regardless of their presence
in ``STATIC_TEMPLATES``. They will be given the global context:

.. code::

    $ manage.py renderstatic name/of/template1.js name/of/template2.js
