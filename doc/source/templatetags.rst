.. _ref-filters_and_tags:

=======================
Built-in Filters & Tags
=======================

`django-static-templates` includes several built-in template filters and tags. These are described
here.

.. _filters:

Filters
-------

.. _split:

``split``
~~~~~~~~~

This is a simple wrapper around Python's split call. A frequent use case of this library might be
passing lists of classes/modules/includes/excludes into the other tags in this library. This allows
users to embed those lists directly in templates without having to provide them in a template
context. The first argument is the string to split and the second is the separator::

    {{ "my_app.mod.Class, my_app.mod.OtherClass"|split:"," }}


.. _classes_to_js:

``classes_to_js``
~~~~~~~~~~~~~~~~~

Converts a list of classes and their defines-style attributes into JavaScript structures.
Defines-style attributes are attributes that:

    - Are all upper case
    - Contain plain old data including iterables and dictionaries that contain json-serializbale
      types.

The filter accepts two arguments the first is a list of class types or string import paths to
classes and the second is the string to use for indentation. The indentation string defaults to
'\t'::

    var defines = {
        {{ class_list|classes_to_js:"\t" }}
    };

.. note::
    Note that the filter does not produce valid JavaScript on its own. It must be embedded in an
    object as above.

For instance if the class_list context variable contained the following::

    context: {
        'class_list': ['myapp.defines.TestDefines']
    }

And `myapp.defines.TestDefines` contained the following::

    class TestDefines(object):

        DEFINE1 = 'D1'
        DEFINE2 = 'D2'
        DEFINE3 = 'D3'
        DEFINES = (
            (DEFINE1, 'Define 1'),
            (DEFINE2, 'Define 2'),
            (DEFINE3, 'Define 3'),
        )

        DICTIONARY = {
            'Key': 'value',
            'Numeric': 0
        }

The generated source would look like::

    var defines = {
      TestDefines: {
           DEFINE1: "D1",
           DEFINE2: "D2",
           DEFINE3: "D3",
           DEFINES: [["D1", "Define 1"], ["D2", "Define 2"], ["D3", "Define 3"]],
           DICTIONARY: {"Key": "value", "Numeric": 0}
      },
    };

.. note::
    The filter will also walk inheritance hierarchy and pull out any defines-style attributes in
    parent classes and add them to the JavaScript.


.. _modules_to_js:

``modules_to_js``
~~~~~~~~~~~~~~~~~

This filter pulls out all the classes from a list of modules and feeds them through
``classes_to_js``. It also takes one additional argument, the `indent` string to use::

    {{ module_list|modules_to_js:"\t" }}

The module_list may be a list of module types or string import paths to modules.


.. _tags:

Tags
----

.. _urls_to_js:

``urls_to_js``
~~~~~~~~~~~~~~

This tag spits out a JavaScript object that can be used in the same manner as Django's URL
`reverse <https://docs.djangoproject.com/en/3.1/ref/urlresolvers/#reverse>`_ function.

It accepts a number of different parameters:

    - **url_conf** The root url module to dump urls from. Can be an import string or an actual
      module type. default: settings.ROOT_URLCONF
    - **indent** String to use for indentation in javascript, default: '\\t'
    - **depth** The starting indentation depth, default: 0
    - **include** A list of path names to include, namespaces without path names will be treated as
      every path under the namespace. Default: include everything
    - **exclude** A list of path names to exclude, namespaces without path names will be treated as
      every path under the namespace. Excludes override includes. Default: exclude nothing
    - **es5** If True, dump es5 valid JavaScript, if False JavaScript will be es6, default: False

Includes and excludes are hierarchical strings that contain the fully qualified name of a namespace
or path name. For instance `namespace1:namespace2:url_name` would include only patterns that are
mapped to `url_name` under `namespace2` that is in turn under `namespace1`. `namespace1:namespace2`
would include all paths in any namespace(s) at or under `namespace1:namespace2` but it would
not include paths directly under `namespace1`. Excludes always override includes. By default every
path is included and no paths are excluded. If any includes are provided, then only those includes
are included (everything else is by default excluded).

.. warning::

    All the URLs embedded in JavaScript are exposed client side. Its never a good idea to have site
    security dependent on path visibility, but if there are sensitive URLs that shouldn't be
    generally known its best practice to exclude them from URL generation.

For instance a very common pattern would be to generate urls for every path except the admin
paths. Given the following ROOT_URLCONF::

    from django.contrib import admin
    from django.urls import include, path

    from .views import MyView

    urlpatterns = [
        path('admin/', admin.site.urls),
        path('simple', MyView.as_view(), name='simple'),
        path('simple/<int:arg1>', MyView.as_view(), name='simple'),
        path('different/<int:arg1>/<str:arg2>', MyView.as_view(), name='different'),
    ]

When given the context::

    context = {
        'exclude': ['admin']
    }

And passed through::

    var urls = {
        {% urls_to_js indent="\t" exclude=exclude %}
    };

Would generate::

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

It is strongly encouraged as a best practice to use `path` instead of `re_path`. If an
argument requires a regex that isn't supported by the existing Django `converter` set it is very
easy to implement new ones::

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

Note the ``placeholder`` attribute. This attribute is used by `urls_to_js` to reverse paths for the
generated JavaScript. By including the attribute on your converter you ensure that anyone using your
converter will be able to run `urls_to_js` without error. And you don't even have to
include `django-static-templates` as a dependency if you aren't using it! Alternatively if you're
using someone else's converter and they haven't supplied a ``placeholder`` attribute, you can
register one::

    from static_templates.placeholders import register_converter_placeholder
    register_converter_placeholder(YearConverter, 2000)

Of if you're using `re_path` instead::

    from static_templates.placeholders import register_variable_placeholder

    app_name = 'year_app'
    urlpatterns = [
        re_path(r'^fetch/(?P<year>\d{4})/$', YearView.as_view(), name='fetch_year')
    ]

    register_variable_placeholder('year', 2000, app_name=app_name)

Paths with unnamed arguments are also supported, but be kind to yourself and don't use them.
Any number of placeholders may be registered against any number of variable/app_name combinations.
When `urls_to_js` is run it won't give up until its tried all placeholders that might potentially
match the path.
