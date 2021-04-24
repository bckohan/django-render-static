.. _ref-configuration:

=============
Configuration
=============

`django-render-static` settings are set in the ``STATIC_TEMPLATES`` dictionary in your site
settings:

.. code-block:: python

      STATIC_TEMPLATES = {
        'ENGINES': [
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'DIRS': [BASE_DIR / 'tmpls' ], # look here for templates
            'OPTIONS': {
                'app_dir': 'static_templates',  # search this directory in apps for templates
                'loaders': [
                    # search apps for templates
                    'render_static.loaders.StaticAppDirectoriesLoader',
                    # search DIRS for templates
                    'render_static.loaders.StaticFilesystemLoader'
                 ],
                'builtins': ['render_static.templatetags.render_static']
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
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'DIRS': [],
            'OPTIONS': {
                'loaders': ['render_static.loaders.StaticAppDirectoriesLoader'],
                'builtins': ['render_static.templatetags.render_static']
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
here, instead use the two engines provided by `django-render-static`:

- ``render_static.backends.StaticDjangoTemplates``
    - default app directory: ``static_templates``
- ``render_static.backends.StaticJinja2Templates``
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

- ``render_static.backends.StaticDjangoTemplates``
    - ``render_static.loaders.StaticAppDirectoriesLoader``
    - ``render_static.loaders.StaticFilesystemLoader``
    - ``render_static.loaders.StaticLocMemLoader``

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

The ``templates`` dictionary lists all templates that should be generated when `render_static` is
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


``RENDER_STATIC_REVERSAL_LIMIT``
--------------------------------

The guess and check reversal mechanism used to ensure that `urls_to_js` produces the same reversals
as Django's `reverse` is an **O(n^p)** operation where **n** is the number of placeholder candidates
to try and **p** is the number of arguments in the url. Its possible for this to produce a
complexity explosion for rare cases where the URL has a large number of arguments with unregistered
placeholders. A limit on the number of tries is enforced to guard against this. User's may adjust
the limit via the ``RENDER_STATIC_REVERSAL_LIMIT`` settings parameter. By default it is 2**14 tries
which runs in ~seconds per URL.

The solution if this limit is hit, is to provide more specific placeholders as placeholders are
attempted in order of specificity where specificity is defined by url name, variable name,
app name and/or converter type.
