|MIT license| |PyPI version fury.io| |PyPI pyversions| |PyPI status| |Documentation Status|
|Code Cov| |Tests Status|

.. |MIT license| image:: https://img.shields.io/badge/License-MIT-blue.svg
   :target: https://lbesson.mit-license.org/

.. |PyPI version fury.io| image:: https://badge.fury.io/py/django-render-static.svg
   :target: https://pypi.python.org/pypi/django-render-static/

.. |PyPI pyversions| image:: https://img.shields.io/pypi/pyversions/django-render-static.svg
   :target: https://pypi.python.org/pypi/django-render-static/

.. |PyPI status| image:: https://img.shields.io/pypi/status/django-render-static.svg
   :target: https://pypi.python.org/pypi/django-render-static

.. |Documentation Status| image:: https://readthedocs.org/projects/django-render-static/badge/?version=latest
   :target: http://django-render-static.readthedocs.io/?badge=latest/

.. |Code Cov| image:: https://codecov.io/gh/bckohan/django-render-static/branch/main/graph/badge.svg?token=0IZOKN2DYL
   :target: https://codecov.io/gh/bckohan/django-render-static

.. |Tests Status| image:: https://github.com/bckohan/django-render-static/workflows/test/badge.svg?branch=master&event=push
   :target: https://github.com/bckohan/django-render-static/actions?query=workflow%3Atest

django-render-static
#######################

`django-render-static` enables Django's dynamic templates to be used to generate static files.
That is, files that are collected during the ``collectstatic`` routine and likely served above
Django on the stack. Static templates should be rendered preceding any run of ``collectstatic``.

For example, a frequently occurring pattern that violates the DRY principle is the presence of
defines, or enum like structures in server side Python code that are simply replicated in client
side JavaScript. Single-sourcing these structures by generating client side code from the server
side code maintains DRYness.

Have you ever wished you could replicate Django's `reverse` function in a JavaScript library for
your site? Now you can with the `urls_to_js` template tag included with `django-render-static`.

You can report bugs and discuss features on the
`issues page <https://github.com/bckohan/django-render-static/issues>`_.

`Contributions <https://github.com/bckohan/django-render-static/blob/main/CONTRIBUTING.rst>`_ are
encouraged! Especially additional template tags and filters!

Installation
------------

1. Clone django-render-static from GitHub_ or install a release off PyPI_ :

.. code:: bash

       pip install django-render-static


2. Add 'render_static' to your ``INSTALLED_APPS`` :

.. code:: python

       INSTALLED_APPS = [
           'render_static',
       ]


3. Add a ``STATIC_TEMPLATES`` configuration directive to your settings file:

.. code:: python

        STATIC_TEMPLATES = {
            'templates' : {
                'path/to/template': {
                    'context' { 'variable': 'value' }
                }
        }


4. Run ``render_static`` preceding every run of ``collectstatic`` :

.. code:: bash

        $> manage.py render_static
        $> manage.py collectstatic


.. _GitHub: http://github.com/bckohan/django-render-static
.. _PyPI: http://pypi.python.org/pypi/django-render-static


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


Your defines/model classes might look like this:

.. code:: python

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
class their settings file might look like this:

.. code:: python

    STATIC_TEMPLATES = {
        'templates': {
            'my_app/defines.js': {}
        }
    }


And then of course they would call `render_static` before `collectstatic`:

.. code:: bash

    $> ./manage.py render_static
    $> ./manage.py collectstatic


This would create the following file::

    .
    └── my_app
        └── static
            └── my_app
                └── defines.js

Which would look like this:

.. code:: javascript

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

Your settings file might look like:

.. code:: python

    from pathlib import Path

    BASE_DIR = Path(__file__).parent

    STATICFILES_DIRS = [
        BASE_DIR / 'more_static'
    ]

    STATIC_TEMPLATES = {
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': (
                            'var urls = {\n
                                {% urls_to_js exclude=exclude %}
                            \n};'
                        )
                    })
                 ],
                'builtins': ['render_static.templatetags.render_static']
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


Then call `render_static` before `collectstatic`::

    $> ./manage.py render_static
    $> ./manage.py collectstatic

If your root urls.py looks like this:

.. code:: python

    from django.contrib import admin
    from django.urls import include, path

    from .views import MyView

    urlpatterns = [
        path('admin/', admin.site.urls),
        path('simple', MyView.as_view(), name='simple'),
        path('simple/<int:arg1>', MyView.as_view(), name='simple'),
        path('different/<int:arg1>/<str:arg2>', MyView.as_view(), name='different'),
    ]


Then urls.js will look like this:

.. code:: javascript

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


So you can now fetch paths like this:

.. code:: javascript

    // /different/143/emma
    urls.different({'arg1': 143, 'arg2': 'emma'});
