.. _ref-usage:

===============
Quick Reference
===============

First go back to the :doc:`installation` page and install :pypi:`django-render-static` if you
haven't!

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
        │   └── my_app
        │   └── defines.js
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

And your defines.js template might look like this:

.. code-block:: js+django

    {% defines_to_js defines="my_app.defines.Defines" %}


If someone wanted to use your defines template to generate a JavaScript version of your Python
class their settings file might look like this:

.. code-block:: python

    STATIC_TEMPLATES = {
        'templates': ['my_app/defines.js']
    }

And then of course they would call :django-admin:`renderstatic` before
:django-admin:`collectstatic`::

    $> ./manage.py renderstatic
    $> ./manage.py collectstatic

This would create the following file::

    .
    └── my_app
        └── static
            └── my_app
                └── defines.js

Which would look like this:

.. code-block:: javascript

    const defines = {
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

You'd like to be able to call something like :func:`~django.urls.reverse` on path names from your
client JavaScript code the same way you do from Python Django code. You don't want to expose your
admin paths though.

:pypi:`django-render-static` comes bundled with a urls template ready to use. You can see if your
URLs will generate out of the box by running:

.. code-block:: console

        $> ./manage.py renderstatic render_static/urls.js --dest ./urls.js

If this fails, you may need to add some :mod:`~render_static.placeholders`.

The output can be more customized as well. For example your settings file might look like:

.. code-block:: python

    from pathlib import Path

    BASE_DIR = Path(__file__).parent

    STATICFILES_DIRS = [
        BASE_DIR / 'more_static'
    ]

    # since its so small, we just specify our template inline in the settings file
    STATIC_TEMPLATES = {
        'ENGINES': [{
            'BACKEND': 'render_static.backends.StaticDjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    ('render_static.loaders.StaticLocMemLoader', {
                        'urls.js': (
                            '{% urls_to_js exclude=exclude export=True %}'
                        )
                    })
                 ]
            },
        }],
        'templates': [
            ('urls.js', {
                'dest': BASE_DIR / 'more_static' / 'urls.js'
            })
        ]
    }


Then call :django-admin:`renderstatic` before :django-admin:`collectstatic`::

    $> ./manage.py renderstatic
    $> ./manage.py collectstatic

If your root urls.py looks like this:

.. code-block:: python

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

.. code-block:: javascript

    /**
     * A url resolver class that provides an interface very similar to Django's
     * reverse() function. This interface is nearly identical to reverse() with
     * a few caveats:
     *
     *  - Python type coercion is not available, so care should be taken to pass
     *      in argument inputs that are in the expect string format.
     *  - Not all reversal behavior can be replicated but these are corner cases
     *      that are not likely to be correct url specification to begin with.
     *  - The reverse function also supports a query option to include url query
     *      parameters in the reversed url.
     *
     * @class
     */
    export class URLResolver {

        /**
         * Instantiate this url resolver.
         *
         * @param {Object} options - The options object.
         * @param {string} options.namespace - When provided, namespace will
         *     prefix all reversed paths with the given namespace.
         */
        constructor(options=null) {
            this.options = options || {};
            if (this.options.hasOwnProperty("namespace")) {
                this.namespace = this.options.namespace;
                if (!this.namespace.endsWith(":")) {
                    this.namespace += ":";
                }
            } else {
                this.namespace = "";
            }
        }

        /**
         * Given a set of args and kwargs and an expected set of arguments and
         * a default mapping, return True if the inputs work for the given set.
         *
         * @param {Object} kwargs - The object holding the reversal named arguments.
         * @param {string[]} args - The array holding the positional reversal arguments.
         * @param {string[]} expected - An array of expected arguments.
         * @param {Object.<string, string>} defaults - An object mapping default arguments to their values.
         */
        match(kwargs, args, expected, defaults={}) {
            if (defaults) {
                kwargs = Object.assign({}, kwargs);
                for (const [key, val] of Object.entries(defaults)) {
                    if (kwargs.hasOwnProperty(key)) {
                        if (kwargs[key] !== val) { return false; }
                        if (!expected.includes(key)) { delete kwargs[key]; }
                    }
                }
            }
            if (Array.isArray(expected)) {
                return (
                    Object.keys(kwargs).length === expected.length &&
                    expected.every(value => kwargs.hasOwnProperty(value));
                );
            } else if (expected) {
                return args.length === expected;
            } else {
                return Object.keys(kwargs).length === 0 && args.length === 0;
            }
        }

        /**
         * Reverse a Django url. This method is nearly identical to Django's
         * reverse function, with an additional option for URL parameters. See
         * the class docstring for caveats.
         *
         * @param {string} qname - The name of the url to reverse. Namespaces
         *   are supported using `:` as a delimiter as with Django's reverse.
         * @param {Object} options - The options object.
         * @param {string} options.kwargs - The object holding the reversal named arguments.
         * @param {string[]} options.args - The array holding the reversal positional arguments.
         * @param {Object.<string, string|string[]>} options.query - URL query parameters to add
         *    to the end of the reversed url.
         */
        reverse(qname, options={}) {
            if (this.namespace) {
                qname = `${this.namespace}${qname.replace(this.namespace, "")}`;
            }
            const kwargs = options.kwargs || {};
            const args = options.args || [];
            const query = options.query || {};
            let url = this.urls;
            for (const ns of qname.split(':')) {
                if (ns && url) { url = url.hasOwnProperty(ns) ? url[ns] : null; }
            }
            if (url) {
                let pth = url(kwargs, args);
                if (typeof pth === "string") {
                    if (Object.keys(query).length !== 0) {
                        const params = new URLSearchParams();
                        for (const [key, value] of Object.entries(query)) {
                            if (value === null || value === '') continue;
                            if (Array.isArray(value)) value.forEach(element => params.append(key, element));
                            else params.append(key, value);
                        }
                        const qryStr = params.toString();
                        if (qryStr) return `${pth.replace(/\/+$/, '')}?${qryStr}`;
                    }
                    return pth;
                }
            }
            throw new TypeError(`No reversal available for parameters at path: ${qname}`);
        }

        urls = {
            "different": (kwargs={}, args=[]) => {
                if (this.match(kwargs, args, ['arg1','arg2'])) { return `/different/${kwargs["arg1"]}/${kwargs["arg2"]}`; }
            },
            "simple": (kwargs={}, args=[]) => {
                if (this.match(kwargs, args, ['arg1'])) { return `/simple/${kwargs["arg1"]}`; }
                if (this.match(kwargs, args)) { return "/simple"; }
            },
        }
    };


So you can now fetch paths like this:

.. code-block:: javascript

    import { URLResolver } from "./urls.js";

    // /different/143/emma
    const urls = new URLResolver();
    urls.reverse('different', {'arg1': 143, 'arg2': 'emma'});

    // reverse also supports query parameters
    // /different/143/emma?intarg=0&listarg=A&listarg=B&listarg=C
    url.reverse(
        'different',
        {
            kwargs: {arg1: 143, arg2: 'emma'},
            query: {
                intarg: 0,
                listarg: ['A', 'B', 'C']
            }
        }
    );

.. warning::

    If you get an exception when you run :django-admin:`renderstatic` that originated from a
    :class:`render_static.exceptions.URLGenerationFailed` exception, you mostly likely need to
    register some :mod:`~render_static.placeholders` before calling :templatetag:`urls_to_js`.

.. note::
    The JavaScript URL resolution is guaranteed to produce the same paths as Django's reversal
    mechanism. If it does not, this is a bug and we kindly ask
    `you to report it <https://github.com/bckohan/django-render-static/issues>`_.


Transpiling Enumerations
------------------------

Say instead of the usual choices tuple you're using
:class:`PEP 435 style python enumerations <enum.Enum>` as model fields using
:doc:`django-enum <django-enum:index>` and :doc:`enum-properties <enum-properties:index>`. For
example we might define a simple color enumeration like so:

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

It will contain a javascript class transpilation of the Color enum that looks like this:

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
