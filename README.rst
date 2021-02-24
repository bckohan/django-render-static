django-static-templates
#######################

`django-static-templates` enables Django's dynamic templates to be used to generate static files.
That is, files that are collected during the ``collectstatic`` routine and likely served above
Django on the stack. Static templates should be rendered preceding any run of ``collectstatic``.

For example, a frequently occurring pattern that violates the DRY principle is the presence of
defines, or enum like structures in server side Python code that are simply replicated in client
side JavaScript. Single-sourcing these structures by generating client side code from the server
side code maintains DRYness.

Have you ever wished you could replicate Django's `reverse` function in a JavaScript library for
your site? Now you can with the `urls_to_js` template tag included with `django-static-templates`.

You can report bugs and discuss features on the
`issues page <https://github.com/bckohan/django-static-templates/issues>`_.

`Contributions <https://github.com/bckohan/django-static-templates/blob/main/CONTRIBUTING.rst>`_ are
encouraged! Especially additional template tags and filters!

Installation
------------

1. Clone django-static-templates from GitHub_ or install a release off PyPI_ ::

       pip install django-static-templates


2. Add 'static_templates' to your ``INSTALLED_APPS`` ::

       INSTALLED_APPS = [
           'static_templates',
       ]

3. Add a ``STATIC_TEMPLATES`` configuration directive to your settings file::

        STATIC_TEMPLATES = {
            'templates' : {
                'path/to/template': {
                    'context' { 'variable': 'value' }
                }
        }

4. Run ``generate_static`` preceding every run of ``collectstatic`` ::

        manage.py generate_static
        manage.py collectstatic


.. _GitHub: http://github.com/bckohan/django-static-templates
.. _PyPI: http://pypi.python.org/pypi/django-static-templates


Usage
-----

Generating Javascript Defines
-----------------------------

You have an app with a model with a character field that has several valid choices defined in an
enumeration type way, and you'd like to export those defines to JavaScript. You'd like to include
a template for other's using your app to use to generate a defines.js file. Say your app structure
looks like this::

    .
    └── my_app
        ├── __init__.py
        ├── apps.py
        ├── defines.py
        ├── models.py
        ├── static_templates
        │   └── my_app
        │       └── defines.js
        └── urls.py


Your defines/model classes might look like this::

    class Defines:

        DEFINE1 = 'D1'
        DEFINE2 = 'D2'
        DEFINE3 = 'D3'
        DEFINES = (
            (DEFINE1, 'Define 1'),
            (DEFINE2, 'Define 2'),
            (DEFINE3, 'Define 3')
        )

    class MyModel(Defines, models.Model):

        define_field = models.CharField(choices=Defines.DEFINES, max_length=2)

And your defines.js template might look like this::

    var defines = {
        {{ "my_app.defines.Defines"|split|classes_to_js }}
    };


If someone wanted to use your defines template to generate a JavaScript version of your Python
class their settings file might look like this::

    STATIC_TEMPLATES = {
        'templates': {
            'my_app/defines.js': {}
        }
    }

And then of course they would call `generate_static` before `collectstatic`::

    $> ./manage.py generate_static
    $> ./manage.py collectstatic

This would create the following file::

    .
    └── my_app
        └── static
            └── my_app
                └── defines.js

Which would look like this::

    var defines = {
        Defines: {
            DEFINE1: 'D1'
            DEFINE2: 'D2'
            DEFINE3: 'D3'
            DEFINES: [
                ['D1', 'Define 1'],
                ['D2', 'Define 2'],
                ['D3', 'Define 3']
            ]
        }
    };

URL reverse functions
---------------------

You'd like to be able to call something like `reverse` on path names from your client JavaScript
code the same way you do from Python Django code. You don't want to expose your admin paths though.

Your settings file might look like::

    from pathlib import Path

    BASE_DIR = Path(__file__).parent

    STATICFILES_DIRS = [
        BASE_DIR / 'more_static'
    ]

    STATIC_TEMPLATES = {
        'ENGINES': [{
            'BACKEND': 'static_templates.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('static_templates.loaders.StaticLocMemLoader', {
                        'urls.js': 'var urls = {\n{% urls_to_js exclude=exclude %}\n};'
                    })
                 ],
                'builtins': ['static_templates.templatetags.static_templates']
            },
        },
        'templates': {
            'urls.js': {
                'dest': BASE_DIR / 'more_static' / 'urls.js',
                'context': {
                    'exclude': ['admin']
                }
            }
        }]

Then call `generate_static` before `collectstatic`::

    $> ./manage.py generate_static
    $> ./manage.py collectstatic

If your root urls.py looks like this::

    from django.contrib import admin
    from django.urls import include, path

    from .views import MyView

    urlpatterns = [
        path('admin/', admin.site.urls),
        path('simple', MyView.as_view(), name='simple'),
        path('simple/<int:arg1>', MyView.as_view(), name='simple'),
        path('different/<int:arg1>/<str:arg2>', MyView.as_view(), name='different'),
    ]

Then urls.js will look like this::

    var urls = {
        "simple": function(kwargs={}, args=[]) {
            if (Object.keys(kwargs).length === 0 && args.length === 0)
                return "/simple";
            if (
                Object.keys(kwargs).length === 1 &&
                ['arg1'].every(value => kwargs.hasOwnProperty(value))
            )
                return `/simple/${kwargs["arg1"]}`;
            throw new TypeError("No reversal available for parameters at path: simple");
        },
        "different": function(kwargs={}, args=[]) {
            if (
                Object.keys(kwargs).length === 2 &&
                ['arg1','arg2'].every(value => kwargs.hasOwnProperty(value))
            )
                return `/different/${kwargs["arg1"]}/${kwargs["arg2"]}`;
            throw new TypeError("No reversal available for parameters at path: different");
        }
    }

So you can now fetch paths like this::

    // /different/143/emma
    urls.different({'arg1': 143, 'arg2': 'emma'});

.. note::
    If you get an exception when you run generate_static that originated from a PlaceholderNotFound
    exception, you need to register some :ref:`placeholders` before calling :ref:`urls_to_js`.
