.. _ref-installation:

============
Installation
============


1. Install :pypi:`django-render-static` or clone from GitHub_::

       pip install django-render-static


2. Add 'render_static' to your :setting:`INSTALLED_APPS` ::

       INSTALLED_APPS = [
           'render_static',
           ...
       ]

3. Add a :setting:`STATIC_TEMPLATES` configuration directive to your settings file::

        STATIC_TEMPLATES = {
            'templates' : [
                ('path/to/template', {'context' { 'variable': 'value' }})
            ]
        }

4. Run :django-admin:`renderstatic` preceding every run of :django-admin:`collectstatic`::

        manage.py renderstatic
        manage.py collectstatic


.. _GitHub: http://github.com/bckohan/django-render-static
