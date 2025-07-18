.. _ref-configuration:

=============
Configuration
=============

:pypi:`django-render-static` settings are set in the :setting:`STATIC_TEMPLATES` dictionary in your
site settings:

.. code-block:: python

      STATIC_TEMPLATES = {
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'DIRS': [BASE_DIR / 'tmpls' ], # look here for templates
            'OPTIONS': {
                'app_dir': 'static_templates',  # search this directory in apps for templates
                'loaders': [
                    # search apps for templates
                    'render_static.loaders.StaticAppDirectoriesBatchLoader',
                    # search DIRS for templates
                    'render_static.loaders.StaticFilesystemBatchLoader'
                 ],
                'builtins': ['render_static.templatetags.render_static']
            },
        }],
        'context': {
            # define a global context dictionary that will be used to render all templates
        },
        'templates': [
            ('app/js/defines.js', {
                'context': {
                    'defines': 'app.defines.DefinesClass'
                }
            }),
            ('urls.js', {})
        ]
      }

The :setting:`STATIC_TEMPLATES` setting closely mirrors the :setting:`TEMPLATES` setting by defining
which template backends should be used. It extends the standard setting with a few options needed by
the static engine including a global context available to all static templates and a set of template
specific configuration parameters. It's advisable to first read about Django's :setting:`TEMPLATES`
setting. The main difference with :setting:`STATIC_TEMPLATES` is that it supports batch rendering.
Glob-like patterns can be used to select multiple templates for rendering. See :ref:`loaders` for
more details.

Minimal Configuration
---------------------

To run :django-admin:`renderstatic`, If :setting:`STATIC_TEMPLATES` is not defined in settings. Or,
if it's an empty dictionary (or None) then the default engine and loaders will be used which is
equivalent to:

.. code-block:: python

    STATIC_TEMPLATES = {
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': ['render_static.loaders.StaticAppDirectoriesBatchLoader'],
                'builtins': ['render_static.templatetags.render_static']
            },
        }]
    }



``ENGINES``
-----------

A prioritized list of backend template engines and their parameters. The engines at the front of the
list have precedence over engines further down the list. The ``ENGINES`` parameters are inherited
from the standard Django :setting:`TEMPLATES` configuration.

``BACKEND``
~~~~~~~~~~~
The backend classes that render templates. The standard :setting:`TEMPLATES` engines should not be
used here, instead use the two engines provided by :pypi:`django-render-static`:

- :class:`render_static.backends.StaticDjangoTemplates`
    - default app directory: :setting:`STATIC_TEMPLATES`
- :class:`render_static.backends.jinja2.StaticJinja2Templates`
    - default app directory: ``static_jinja2``

If ``APP_DIRS`` is true, or if an app directories loader is used such that templates are searched
for in apps then the default app directories listed above are where templates should reside. Unlike
the standard Django backends, the app directory location can be changed by passing the ``app_dir``
parameter into ``OPTIONS``.

``OPTIONS``
~~~~~~~~~~~

A list of configuration parameters to pass to the backend during initialization. Most of these
parameters are inherited from the standard Django template backends. One additional parameter
``app_dir`` can be used to change the default search path for static templates within apps. The
:class:`options available to the StaticDjangoTemplates backend <django.template.backends.django.DjangoTemplates>`
differ slightly from the :class:`options available to the StaticJinja2Templates backend <django.template.backends.jinja2.Jinja2>`.

.. _loaders:

``loader(s)``
*************

Works the same way as the ``loaders`` parameter on :setting:`TEMPLATES`. Except when using the
standard template backend the loaders have been extended and static specific loaders should be used
instead:

- :class:`render_static.backends.StaticDjangoTemplates <render_static.backends.django.StaticDjangoTemplates>`
    - :class:`render_static.loaders.django.StaticAppDirectoriesBatchLoader` **default**
    - :class:`render_static.loaders.django.StaticFilesystemBatchLoader`
    - :class:`render_static.loaders.django.StaticAppDirectoriesLoader`
    - :class:`render_static.loaders.django.StaticFilesystemLoader`
    - :class:`render_static.loaders.django.StaticLocMemLoader`

- :class:`render_static.backends.jinja2.StaticJinja2Templates`
    - :class:`render_static.loaders.jinja2.StaticFileSystemBatchLoader` **default**
    - :class:`render_static.loaders.jinja2.StaticFileSystemLoader`
    - :class:`render_static.loaders.jinja2.StaticPackageLoader`
    - :class:`render_static.loaders.jinja2.StaticPrefixLoader`
    - :class:`render_static.loaders.jinja2.StaticFunctionLoader`
    - :class:`render_static.loaders.jinja2.StaticDictLoader`
    - :class:`render_static.loaders.jinja2.StaticChoiceLoader`
    - :class:`render_static.loaders.jinja2.StaticModuleLoader`


.. note::

    The :class:`~render_static.backends.jinja2.StaticJinja2Templates` engine is configurable with
    only one loader and the parameter is called ``loader``. The
    :class:`~render_static.backends.django.StaticDjangoTemplates` engine is configurable with more
    than one loader that are specified as a list under the ``loaders`` parameter.


The static template engine supports batch rendering. All loaders that have ``Batch`` in the name
support wild cards and glob-like patterns when loading templates. By default, if no loaders are
specified these loaders are used. For instance, if I wanted to render every .js file in a directory
called static_templates/js I could configure templates like so:

.. code-block:: python

    'templates': ['js/*.js']

``context``
-----------
Specify a dictionary containing the context to pass to any static templates as they render. This is
the global context that will be applied to all templates. Specific templates can override
individual context parameters, but not the whole dictionary. By default all contexts will have the
Django settings in them, keyed by ``settings``.

A context is passed to each template for it render just as with the dynamic template engine. The
main difference is that static template rendering does not occur in the context of a request, so
there is no request object to build context off of. Dynamic templates are also often rendering
contextual data built from the database but static templates are only rendered at deployment time,
so stuffing dynamic database information in static template contexts is not advisable.

Context configuration parameters may be any of the following:

    - **dictionary**: Simply specify context dictionary inline
    - **callable**: That returns a dictionary. This allows lazy context initialization to take
      place after Django bootstrapping
    - **module**: When a module is used as a context, the module's locals will be used as the
      context.
    - **json**: A path to a JSON file
    - **yaml**: A path to a YAML file (yaml supports comments!)
    - **pickle**: A path to a python pickled dictionary
    - **python**: A path to a python file. The locals defined in the file will
      comprise the context.
    - **a packaged resource**: Any of the above files imported as a packaged resource via
      :mod:`render_static.resource` to any of the above files.
    - **import string**: to any of the above.

For example:

.. code-block:: python

      from render_static import resource
      STATIC_TEMPLATES = {
        'context': resource('package.module', 'context.yaml')
      }


``STATIC_TEMPLATES``
--------------------

.. setting:: STATIC_TEMPLATES

The :setting:`STATIC_TEMPLATES` dictionary lists all templates that should be generated when
:django-admin:`renderstatic` is run with no arguments. If specific configuration directives
including rendered path and context are needed for a template they must be specified here.
:setting:`STATIC_TEMPLATES` may also be a list containing template names or 2-tuples of template
names and configurations. By specifying :setting:`STATIC_TEMPLATES` this way, a single template may
be rendered multiple times using different contexts to different locations. For example, the
following would render one template three times:

.. code-block:: python

        'templates' [
            'urls.js',
            ('urls.js', {'context': {'includes': ['namespace1']}, 'dest': 'ns1_urls.js'}),
            ('urls.js', {'context': {'includes': ['namespace2']}, 'dest': 'ns2_urls.js'}),
        ]


.. note::

    :django-admin:`renderstatic` will be able to generate templates not listed in
    :setting:`STATIC_TEMPLATES`, but only if supplied by name on the command line. Contexts may
    also be augmented/overridden via the command line.

``dest``
~~~~~~~~

Override the default destination where a template will be rendered. Templates loaded from ``DIRS``
instead of apps do not have a default destination and must be provided here. When rendering a
single template, if the ``dest`` parameter is not an existing directory, it will be assumed to be
the full path including the file name where the template will be rendered. When rendering in batch
mode, ``dest`` will be treated as a directory and created if it does not exist.

The ``dest`` parameter may include template variables that will be replaced with the value of the
variable in the context. For example, if ``dest`` is ``'js/{{ app_name }}.js'`` and the context
contains ``{'app_name': 'my_app'}`` then the template will be rendered to ``js/my_app.js``.

``context``
~~~~~~~~~~~

Provide additional parameters for each template in the ``context`` dictionary. Any context variables
specified here that clash with global context variables will override them. May be specified using
any of the same context specifiers that work for the global context.


``RENDER_STATIC_REVERSAL_LIMIT``
--------------------------------

.. setting:: RENDER_STATIC_REVERSAL_LIMIT

The guess and check reversal mechanism used to ensure that :templatetag:`urls_to_js` produces the
same reversals as Django's :func:`~django.urls.reverse` is an **O(n^p)** operation where **n** is
the number of placeholder candidates to try and **p** is the number of arguments in the url. Its
possible for this to produce a complexity explosion for rare cases where the URL has a large number
of arguments with unregistered placeholders. A limit on the number of tries is enforced to guard
against this. User's may adjust the limit via the :setting:`RENDER_STATIC_REVERSAL_LIMIT`` settings
parameter. By default it is 2**14 tries which runs in ~seconds per URL.

The solution if this limit is hit, is to provide more specific placeholders as placeholders are
attempted in order of specificity where specificity is defined by url name, variable name, app name
and/or converter type.


:class:`~render_static.backends.jinja2.StaticJinja2Templates` Example
---------------------------------------------------------------------

Using the :class:`~render_static.backends.jinja2.StaticJinja2Templates` engine requires a slightly
different configuration. By default the
:class:`render_static.loaders.jinja2.StaticFileSystemBatchLoader` loader is used and its
``app_dir`` setting will expect to find templates in static_jinja2 sub directories. For example to
render all urls except our admin urls to javascript using :templatetag:`urls_to_js` we might have
the following app tree::

    .
    └── my_app
        ├── __init__.py
        ├── apps.py
        ├── defines.py
        ├── models.py
        ├── static_jinja2
        │   └── my_app
        │       └── urls.js
        └── urls.py

Where our urls.js file might look like:

.. code-block:: js+django

    {{ urls_to_js(exclude=exclude) }}

And our settings file might look like:

.. code-block:: python

    from pathlib import Path
    from render_static.loaders.jinja2 import StaticFileSystemBatchLoader

    BASE_DIR = Path(__file__).parent

    STATICFILES_DIRS = [
        BASE_DIR / 'more_static'
    ]

    STATIC_TEMPLATES = {
        'ENGINES': [{
            'BACKEND': 'render_static.backends.jinja2.StaticJinja2Templates',
            'OPTIONS': {
                'loader': StaticFileSystemBatchLoader()
            },
        }],
        'templates': [
            ('urls.js', {
                'dest': BASE_DIR / 'more_static' / 'urls.js',
                'context': {
                    'exclude': ['admin']
                }
            )
        ]
    }
