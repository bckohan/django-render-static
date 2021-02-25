.. _ref-installation:

============
Installation
============


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

4. Run ``render_static`` preceding every run of ``collectstatic`` ::

        manage.py render_static
        manage.py collectstatic


.. _GitHub: http://github.com/bckohan/django-static-templates
.. _PyPI: http://pypi.python.org/pypi/django-static-templates
