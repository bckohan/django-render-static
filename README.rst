|MIT license| |PyPI version fury.io| |PyPI pyversions| |PyPi djversions| |PyPI status| |Documentation Status|
|Code Cov| |Test Status|

.. |MIT license| image:: https://img.shields.io/badge/License-MIT-blue.svg
   :target: https://lbesson.mit-license.org/

.. |PyPI version fury.io| image:: https://badge.fury.io/py/django-render-static.svg
   :target: https://pypi.python.org/pypi/django-render-static/

.. |PyPI pyversions| image:: https://img.shields.io/pypi/pyversions/django-render-static.svg
   :target: https://pypi.python.org/pypi/django-render-static/

.. |PyPI djversions| image:: https://img.shields.io/pypi/djversions/django-enum.svg
   :target: https://pypi.org/project/django-enum/

.. |PyPI status| image:: https://img.shields.io/pypi/status/django-render-static.svg
   :target: https://pypi.python.org/pypi/django-render-static

.. |Documentation Status| image:: https://readthedocs.org/projects/django-render-static/badge/?version=latest
   :target: http://django-render-static.readthedocs.io/?badge=latest/

.. |Code Cov| image:: https://codecov.io/gh/bckohan/django-render-static/branch/main/graph/badge.svg?token=0IZOKN2DYL
   :target: https://codecov.io/gh/bckohan/django-render-static

.. |Test Status| image:: https://github.com/bckohan/django-render-static/workflows/test/badge.svg
   :target: https://github.com/bckohan/django-render-static/actions


django-render-static
#######################

Use Django's template engines to render static files that are collected
during the ``collectstatic`` routine and likely served above Django at runtime.
Files rendered by django-render-static are immediately available to participate
in the normal static file collection pipeline.

For example, a frequently occurring pattern that violates the `DRY principle <https://en.wikipedia.org/wiki/Don%27t_repeat_yourself>`_
is the presence of defines, or enum like structures in server side Python code that are simply replicated in client
side JavaScript. Another example might be rebuilding Django URLs from arguments in a `Single Page Application <https://en.wikipedia.org/wiki/Single-page_application>`_.
Single-sourcing these structures by transpiling client side code from the server side code keeps the stack bone DRY.

`django-render-static` includes Python to Javascript transpilers for:
    - Django's `reverse` function (`urls_to_js`)
    - PEP 435 style Python enumerations (`enums_to_js`)
    - Plain data define-like structures in Python classes and modules
      (`defines_to_js`)

`django-render-static` also formalizes the concept of a package-time or deployment-time
static file rendering step. It piggybacks off the existing templating engines and configurations
and should therefore be familiar to Django developers. It supports both standard Django templating
and Jinja templates and allows contexts to be specified in python, json or YAML.

You can report bugs and discuss features on the
`issues page <https://github.com/bckohan/django-render-static/issues>`_.

`Contributions <https://github.com/bckohan/django-render-static/blob/main/CONTRIBUTING.rst>`_ are
encouraged!

`Full documentation at read the docs. <https://django-render-static.readthedocs.io/en/latest/>`_

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
            'templates' : [
                ('path/to/template':, {'context' {'variable': 'value'})
            ]
        }


4. Run ``renderstatic`` preceding every run of ``collectstatic`` :

.. code:: bash

        $> manage.py renderstatic
        $> manage.py collectstatic


.. _GitHub: http://github.com/bckohan/django-render-static
.. _PyPI: http://pypi.python.org/pypi/django-render-static
.. _django-enum: http://pypi.python.org/pypi/django-enum
.. _enum-properties: http://pypi.python.org/pypi/enum-properties


Usage
-----

Transpiling Model Field Choices
-------------------------------

You have an app with a model with a character field that has several valid choices defined in an
enumeration type way, and you'd like to export those defines to JavaScript. You'd like to include
a template for other's using your app to use to generate a defines.js file. Say your app structure
looks like this::

    .
    └── examples
        ├── __init__.py
        ├── apps.py
        ├── defines.py
        ├── models.py
        ├── static_templates
        │   └── examples
        │       └── defines.js
        └── urls.py


Your defines/model classes might look like this:

.. code:: python

    class ExampleModel(Defines, models.Model):

        DEFINE1 = 'D1'
        DEFINE2 = 'D2'
        DEFINE3 = 'D3'
        DEFINES = (
            (DEFINE1, 'Define 1'),
            (DEFINE2, 'Define 2'),
            (DEFINE3, 'Define 3')
        )

        define_field = models.CharField(choices=DEFINES, max_length=2)


And your defines.js template might look like this:

.. code:: js+django

    {% defines_to_js modules="examples.models" %}


If someone wanted to use your defines template to generate a JavaScript version of your Python
class their settings file might look like this:

.. code:: python

    STATIC_TEMPLATES = {
        'templates': [
            'examples/defines.js'
        ]
    }


And then of course they would call `renderstatic` before `collectstatic`:

.. code:: bash

    $> ./manage.py renderstatic
    $> ./manage.py collectstatic


This would create the following file::

    .
    └── examples
        └── static
            └── examples
                └── defines.js

Which would look like this:

.. code:: javascript

    const defines = {
        ExampleModel: {
            DEFINE1: "D1",
            DEFINE2: "D2",
            DEFINE3: "D3",
            DEFINES: [["D1", "Define 1"], ["D2", "Define 2"], ["D3", "Define 3"]]
        }
    };


Transpiling Enumerations
------------------------

Say instead of the usual choices tuple you're using PEP 435 style python
enumerations as model fields using django-enum_ and enum-properties_. For example
we might define a simple color enumeration like so:

.. code:: python

    from django.db import models
    from django_enum import EnumField, TextChoices
    from enum_properties import p, s

    class ExampleModel(models.Model):

        class Color(TextChoices, s('rgb'), s('hex', case_fold=True)):

            # name   value   label       rgb       hex
            RED   =   'R',   'Red',   (1, 0, 0), 'ff0000'
            GREEN =   'G',   'Green', (0, 1, 0), '00ff00'
            BLUE  =   'B',   'Blue',  (0, 0, 1), '0000ff'

        color = EnumField(Color, null=True, default=None)

If we define an enum.js template that looks like this:

.. code:: js+django

    {% enums_to_js enums="examples.models.ExampleModel.Color" %}

It will contain a javascript class transpilation of the Color enum that looks
like this:

.. code:: javascript

    class Color {

        static RED = new Color("R", "RED", "Red", [1, 0, 0], "ff0000");
        static GREEN = new Color("G", "GREEN", "Green", [0, 1, 0], "00ff00");
        static BLUE = new Color("B", "BLUE", "Blue", [0, 0, 1], "0000ff");

        constructor (value, name, label, rgb, hex) {
            this.value = value;
            this.name = name;
            this.label = label;
            this.rgb = rgb;
            this.hex = hex;
        }

        toString() {
            return this.value;
        }

        static get(value) {
            switch(value) {
                case "R":
                    return Color.RED;
                case "G":
                    return Color.GREEN;
                case "B":
                    return Color.BLUE;
            }
            throw new TypeError(`No Color enumeration maps to value ${value}`);
        }

        static [Symbol.iterator]() {
            return [Color.RED, Color.GREEN, Color.BLUE][Symbol.iterator]();
        }
    }

We can now use our enumeration like so:

.. code:: javascript

    Color.BLUE === Color.get('B');
    for (const color of Color) {
        console.log(color);
    }


Transpiling URL reversal
------------------------

You'd like to be able to call something like `reverse` on path names from your client JavaScript
code the same way you do from Python Django code.

Your settings file might look like:

.. code:: python

    STATIC_TEMPLATES={
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': '{% urls_to_js %}'
                    })
                ]
            },
        }],
        'templates': ['urls.js']
    }


Then call `renderstatic` before `collectstatic`::

    $> ./manage.py renderstatic
    $> ./manage.py collectstatic

If your root urls.py looks like this:

.. code:: python

    from django.contrib import admin
    from django.urls import path

    from .views import MyView

    urlpatterns = [
        path('admin/', admin.site.urls),
        path('simple', MyView.as_view(), name='simple'),
        path('simple/<int:arg1>', MyView.as_view(), name='simple'),
        path('different/<int:arg1>/<str:arg2>', MyView.as_view(), name='different'),
    ]


So you can now fetch paths like this, in a way that is roughly API-equivalent
to Django's `reverse` function:

.. code:: javascript

    import { URLResolver } from '/static/urls.js';

    const urls = new URLResolver();

    // /different/143/emma
    urls.reverse('different', {kwargs: {'arg1': 143, 'arg2': 'emma'}});

    // reverse also supports query parameters
    // /different/143/emma?intarg=0&listarg=A&listarg=B&listarg=C
    urls.reverse(
        'different',
        {
            kwargs: {arg1: 143, arg2: 'emma'},
            query: {
                intarg: 0,
                listarg: ['A', 'B', 'C']
            }
        }
    );
    

URLGenerationFailed Exceptions & Placeholders
---------------------------------------------

If you encounter a ``URLGenerationFailed`` exception you most likely need to register a placeholder for the argument in question. A placeholder is just a string or object that can be coerced to a string that matches the regular expression for the argument:

.. code:: python

   from render_static.placeholders import register_variable_placeholder

   app_name = 'year_app'
   urlpatterns = [
       re_path(r'^fetch/(?P<year>\d{4})/$', YearView.as_view(), name='fetch_year')
   ]

   register_variable_placeholder('year', 2000, app_name=app_name)

Users should typically use a path instead of re_path and register their own custom converters when needed. Placeholders can be directly registered on the converter (and are then conveniently available to users of your app!):

.. code:: python

   from django.urls.converters import register_converter

   class YearConverter:
       regex = '[0-9]{4}'
       placeholder = 2000  # this attribute is used by `url_to_js` to reverse paths

       def to_python(self, value):
           return int(value)

       def to_url(self, value):
           return str(value)


   register_converter(YearConverter, 'year')

   urlpatterns = [
       path('fetch/<year:year>', YearView.as_view(), name='fetch_year')
   ]


