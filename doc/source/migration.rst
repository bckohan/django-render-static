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


urls_to_js Changes
~~~~~~~~~~~~~~~~~~

* urls_to_js no longer supports ES5 output, instead by default it now
  transpiles to an es6 class.
* urls_to_js excludes admin urls by default, to include them set exclude to None
* kwargs, args and query values must now be specified as part of the options
  parameter on reverse():

    .. code-block:: javascript

        // version 1.x
        urls.reverse('my_app:my_view', {id: 1}, [1], {page: 1})

        // version 2.x
        urls.reverse('my_app:my_view', {kwargs: {id: 1}, args: [1], query: {page: 1}})


STATIC_TEMPLATES
~~~~~~~~~~~~~~~~

The ``templates`` parameter on ``STATIC_TEMPLATES`` may remain a dictionary,
but will now also accept a sequence. This allows a single template to be rendered
multiple times with different contexts. Specifying ``templates`` as a list of
tuples is now preferred:

    .. code-block:: python

        STATIC_TEMPLATES={
            'ENGINES': [{
                'BACKEND': 'render_static.backends.StaticDjangoTemplates',
                'OPTIONS': {
                    'loaders': [
                        ('render_static.loaders.StaticLocMemLoader', {
                            'urls.js': '{% urls_to_js exclude=exclude %}'
                        })
                    ]
                },
            }],

            # 1.x
            'templates': {
                'urls.js': {'context': {'exclude': ['admin']}}
            }

            # 2.x
            'templates': [
                ('urls.js', {'context': {'exclude': ['admin']}})
            ]
        }
