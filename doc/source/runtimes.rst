.. _ref-runtimes:

========
Runtimes
========

There are two main use cases for when to run :django-admin:`renderstatic` that determine how it
should be included as a dependency.

Package Time
------------

If you are generating static files that produce no deployment specific output as part of a Django
app that will be distributed on pypi or a similar package service you should use
:django-admin:`renderstatic` at *package time* - that is, before you build and publish the package.

.. important::

    When used at package time :pypi:`django-render-static` should be included as a development
    dependency only. There is no need to require the users of your package to install
    :pypi:`django-render-static` because you are distributing the rendered files with your package.


Deployment Time
---------------

If you are generating static files that produce output dependent on the deployment specific
configuration of a Django site you should use :django-admin:`renderstatic` as part of your
*deployment time* routine - probably just before :django-admin:`collectstatic` is run. 
:templatetag:`urls_to_js` is an example of a *deployment time* use case because its output is
defined by the deployment's urls configuration.

.. warning::

    If app directory loaders are used with the default render destinations at deployment time and
    the deployment user does not have write permission to the virtual environment directories of the
    installed apps - permission errors will be encountered. This can be fixed by using the `dest`
    parameter to force rendering to be written to a directory included in
    :setting:`STATICFILES_DIRS`


Incurred Dependencies
~~~~~~~~~~~~~~~~~~~~~

It may be necessary to incur a deployment time dependency on :pypi:`django-render-static` to users
of your reusable Django app. For example, if you are distributing a Django app that functions as a
`single page application (SPA) <https://en.wikipedia.org/wiki/Single-page_application>`_ and makes
use of :templatetag:`urls_to_js` to resolve its AJAX request urls dynamically you will need users of
your app to run :django-admin:`renderstatic` to generate the urls file(s) your app expects. This can
be even more complicated when you consider that your users might include multiple copies of your SPA
at different url paths.

When you incur a deployment time dependency on your end users - you should take care to think about
how it may be used and provide instructions and a reasonable default template configuration. Below
is a notional directory layout and template configuration for a reusable app relying on
:templatetag:`urls_to_js` that could be included multiple times in a specific Django deployment.

Lets call our notional app *spa*. Our application will need to use the namespaces assigned to
different inclusions of it by the project. Lets layout our app with the following structure::

    .
    ├── __init__.py
    ├── apps.py
    ├── static_templates
    │   └── spa
    │       └── urls.js
    ├── templates
    │   └── spa
    │       └── index.html
    ├── urls.py
    └── views.py


We include a static template for generating our urls.js file but we do not pre-generate and include
it in our distribution package. We must instruct our users to generate the file at deployment time.
Lets say our template simply looks like this:

.. code-block:: htmldjango

    {% urls_to_js export=True include=include %}

It expects a context that has an include variable containing a list of namespaces to include. Lets
say the project including our app has a :setting:`ROOT_URLCONF` file that looks like this:

.. code-block:: python

    from django.urls import include, path

    urlpatterns = [
        path('spa1/', include('spa.urls', namespace='spa1')),
        path('spa2/', include('spa.urls', namespace='spa2'))
    ]

So our app is included twice under two different paths, one with the namespace spa1 and the other
with the namespace spa2. We might instruct our users to generate the urls.js file using the
following settings:

.. code-block:: python

        from pathlib import Path

        LOCAL_STATIC_DIR = Path(BASE_DIR) / 'local_static'

        STATICFILES_DIRS=[
            ('spa', LOCAL_STATIC_DIR),
        ]

        STATIC_TEMPLATES={
            'templates': [
                ('spa/urls.js', {
                    'context': {
                        'include': ['spa1', 'spa2']
                    },
                    'dest': str(LOCAL_STATIC_DIR / 'urls.js')
                })
            ]
        }

Here we setup a local static file directory first so our urls.js file will compile to it instead of
the default location which would be spa/static/spa in your python environment to avoid any
permissions issues (this may be unnecessary depending on the operations environment). We could
alternatively render the file to :setting:`STATIC_ROOT` but that would bypass any
:django-admin:`collectstatic` processing that might be necessary. We also add an include list that
only includes the namespaces we've included the spa app under.

Lets say our spa app's urls.py file looks like this:

.. code-block:: python

    from django.urls import path
    from .views import Index, QryView

    app_name = 'spa'

    urlpatterns = [
        path('', Index.as_view(), name='index'),
        path('qry/', QryView.as_view(), name='qry'),
        path('qry/<int:arg>', QryView.as_view(), name='qry')
    ]

So we have an index page, and a query view that has an optional integer argument called arg. The
context of our IndexView must contain the namespace the app was included under. To do this, our
IndexView could easily build its context like this:

.. code-block:: python

    from django.views.generic import TemplateView


    class Index(TemplateView):

        template_name = 'spa/index.html'

        def get_context_data(self, **kwargs):
            return {
                **super().get_context_data(),
                'namespace': self.request.resolver_match.namespace
            }

Our template file needs to pull in the generated url resolver and instantiate it with this default
namespace:

.. code-block:: html+django

    {% load static %}
    <html>
        <head>
            <script type="module">
                import { URLResolver } from "{% static 'spa/urls.js' %}";
                const urls = new URLResolver({namespace: '{{namespace}}'});
            </script>
        </head>

        <!-- now we can use urls.reverse('qry') and it will resolve to the correct url -->

