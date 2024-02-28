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

.. typer:: render_static.management.commands.renderstatic.Command:typer_app
    :prog: manage.py renderstatic
    :width: 90

Example
~~~~~~~

To generate all templates configured in ``STATIC_TEMPLATES`` settings:

.. code::

    $ manage.py renderstatic

Alternatively individual templates can be generated, regardless of their presence
in ``STATIC_TEMPLATES``. They will be given the global context with any overriding context
parameters supplied on the command line:

.. code::

    $ manage.py renderstatic path/*.js -c ./js_context.yaml -d outputdir
