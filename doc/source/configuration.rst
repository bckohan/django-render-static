.. _ref-configuration:

=============
Configuration
=============

`django-static-templates` settings are set in the ``STATIC_TEMPLATES`` dictionary in your site
settings:

.. code-block:: python

      STATIC_TEMPLATES = {
        'ENGINES': [
            'BACKEND': 'static_templates.backends.StaticDjangoTemplates',
            'DIRS': [BASE_DIR / 'tmpls' ], # look here for templates
            'OPTIONS': {
                'app_dir': 'static_tmplates',  # search this directory in apps for templates
                'loaders': [
                    # search apps for templates
                    'static_templates.loaders.StaticAppDirectoriesLoader',
                    # search DIRS for templates
                    'static_templates.loaders.StaticFilesystemLoader'
                 ],
                'builtins': ['static_templates.templatetags.static_templates']
            },
        ],
        'context': {
            # define a global context dictionary that will be used to render all templates
        },
        'templates' {
            'app/js/defines.js': {
                'context': {
                    'defines': 'app.defines.DefinesClass'
                }
            },
            'urls.js': {}
        }
      }

The ``STATIC_TEMPLATES`` setting closely mirrors the ``TEMPLATES`` setting by defining which
template backends should be used. It extends the standard setting with a few options needed by the
static engine including a global context available to all static templates and a set of template
specific configuration parameters. It's advisable to first read about Django's ``TEMPLATES``
setting.

Minimal Configuration
---------------------

To run render_static, ``STATIC_TEMPLATES`` must be defined in settings. If it's an empty
dictionary (or None):

.. code-block:: python

    STATIC_TEMPALTES = {}


then the default engine and loaders will be used which is equivalent to:

.. code-block:: python

    STATIC_TEMPALTES = {
        'ENGINES': [
            'BACKEND': 'static_templates.backends.StaticDjangoTemplates',
            'DIRS': [],
            'OPTIONS': {
                'loaders': ['static_templates.loaders.StaticAppDirectoriesLoader'],
                'builtins': ['static_templates.templatetags.static_templates']
            },
        ]
    }



``ENGINES``
-----------

A prioritized list of backend template engines and their parameters. The engines at the front of the
list have precedence over engines further down the list. The ``ENGINES`` parameters are
inherited from the standard Django ``TEMPLATES`` configuration.

``BACKEND``
~~~~~~~~~~~
The backend classes that render templates. The standard ``TEMPLATES`` engines should not be used
here, instead use the two engines provided by `django-static-templates`:

- ``static_templates.backends.StaticDjangoTemplates``
    - default app directory: ``static_templates``
- ``static_templates.backends.StaticJinja2Templates``
    - default app directory: ``static_jinja2``

If ``APP_DIRS`` is true, or if an app directories loader is used such that templates are searched
for in apps then the default app directories listed above are where templates should reside. Unlike
the standard Django backends, the app directory location can be changed by passing the ``app_dir``
parameter into ``OPTIONS``.

``OPTIONS``
~~~~~~~~~~~

A list of configuration parameters to pass to the backend during initialization. Most of these
parameters are inherited from the standard Django template backends. One additional parameter
``app_dir`` can be used to change the default search path for static templates within apps.

``loaders``
***********

Works the same way as the ``loaders`` parameter on ``TEMPLATES``. Except when using the standard
template backend the loaders have been extended and static specific loaders should be used instead:

- ``static_templates.backends.StaticDjangoTemplates``
    - ``static_templates.loaders.StaticAppDirectoriesLoader``
    - ``static_templates.loaders.StaticFilesystemLoader``
    - ``static_templates.loaders.StaticLocMemLoader``

The normal Jinja2 loaders are used for the ``StaticJinja2Templates`` backend.

``context``
-----------
Specify a dictionary containing the context to pass to any static templates as they render. This
is the global context that will be applied to all templates. Specific templates can override
individual context parameters, but not the whole dictionary. By default all contexts will have the
Django settings in them, keyed by ``settings``.

A context is passed to each template for it render just as with the dynamic template engine. The
main difference is that static template rendering does not occur in the context of a request, so
there is no request object to build context off of. Dynamic templates are also often rendering
contextual data built from the database but static templates are only rendered at deployment time,
so stuffing dynamic database information in static template contexts is not advisable.

``templates``
-------------

The ``templates`` dictionary lists all templates that should be generated when render_static is
run with no arguments. If specific configuration directives including rendered path and context are
needed for a template they must be specified here.

.. note::

    `render_static` will be able to generate templates not listed in ``templates``, but only if
    supplied by name on the command line. Only the default context will be available to them.

``dest``
~~~~~~~~

Override the default destination where a template will be rendered. Templates loaded from ``DIRS``
instead of apps do not have a default destination and must be provided one here. The ``dest``
parameter must contain the full path where the template will be rendered including the file name.


``context``
~~~~~~~~~~~

Provide additional parameters for each template in the ``context`` dictionary. Any context variables
specified here that clash with global context variables will override them.
