from datetime import datetime
import sys
import os
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
sys.path.append(str(Path(__file__).parent.parent.parent / 'tests'))
import render_static
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tests.settings')
django.setup()

# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))


# -- Project information -----------------------------------------------------
project = render_static.__title__
copyright = render_static.__copyright__
author = render_static.__author__
release = render_static.__version__

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.todo',
    'sphinxcontrib.typer',
    'sphinx.ext.intersphinx',
    'sphinxcontrib_django'
    # 'sphinx_js'
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'furo'
html_theme_options = {
    "source_repository": "https://github.com/bckohan/django-render-static/",
    "source_branch": "main",
    "source_directory": "doc/source",
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = []

todo_include_todos = True

# js_source_path = (
#   str(Path(__file__).parent.parent.parent / 'render_static' / 'tests' /
#   'examples' / 'static' / 'examples'
# )

autodoc_default_options = {
    'show-inheritance': True,
    # Add other autodoc options here if desired, e.g.:
    # 'members': True,
    # 'inherited-members': True,
}
# In your Sphinx conf.py
autodoc_typehints = "description"
autodoc_typehints_format = "short"
autodoc_class_signature = "separated"
autodoc_member_order = 'bysource'


intersphinx_mapping = {
    "django": (
        "https://docs.djangoproject.com/en/stable",
        "https://docs.djangoproject.com/en/stable/_objects/",
    ),
    "click": ("https://click.palletsprojects.com/en/stable", None),
    "django-typer": ("https://django-typer.readthedocs.io/en/stable", None),
    "enum-properties": ("https://enum-properties.readthedocs.io/en/stable", None),
    "django-enum": ("https://django-enum.readthedocs.io/en/stable", None),
    "jinja": ("https://jinja.palletsprojects.com/en/stable", None),
    "python": ('https://docs.python.org/3', None)
}


def pypi_role(name, rawtext, text, lineno, inliner, options={}, content=[]):
    from docutils import nodes
    url = f"https://pypi.org/project/{text}/"
    node = nodes.reference(rawtext, text, refuri=url, **options)
    return [node], []


def setup(app):
    # Register a sphinx.ext.autodoc.between listener to ignore everything
    # between lines that contain the word IGNORE
    from docutils.parsers.rst import roles
    app.add_crossref_type(directivename="django-admin", rolename="django-admin")
    roles.register_local_role('pypi', pypi_role)
    return app
