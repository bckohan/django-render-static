.. _ref-migration:

=========
Migration
=========

`django-render-static` `uses semantic versioning <https://semver.org/>`_. This
page documents how to migrate past the breaking changes introduced by major
version updates.

1.x -> 2.x
----------

Template Filter Changes
~~~~~~~~~~~~~~~~~~~~~~~

classes_to_js and modules_to_js template filters have been removed and
replaced by the :ref:`defines_to_js` tag. To upgrade simply replace the old
filter with the new tag and pass the first argument as the defined parameter
and the second argument if one was provided to the indent parameter:

.. code-block:: js+django

    // version 1.x
    var defines = {
        {{ "my_app.defines.Defines"|split|classes_to_js }}
    };

    var module_defines = {
        {{ "my_app.defines"|split|modules_to_js:'\t'}}
    };

    // version 2.x
    {% defines_to_js defines="my_app.defines.Defines" %}

    {% defines_to_js defines="my_app.defines" indent='\t' %}

.. note::

    In version 2.x defines_to_js renders a complete javascript object instead
    of a snippet.


Command Changes
~~~~~~~~~~~~~~~

The `render_static` command has been removed and renamed to :ref:`renderstatic`.
To upgrade simply replace any calls to render_static with :ref:`renderstatic`.
