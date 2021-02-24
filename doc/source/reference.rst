.. _ref-reference:

=========
Reference
=========

.. _engine:

engine
--------------------------------

.. automodule:: static_templates.engine

   .. autoclass:: StaticTemplateEngine

.. _backends:

backends
----------------------------------

.. automodule:: static_templates.backends

   .. autoclass:: StaticDjangoTemplates
   .. autoclass:: StaticJinja2Templates


.. _loaders:

loaders
---------------------------------

.. automodule:: static_templates.loaders

   .. autoclass:: StaticAppDirectoriesLoader
   .. autoclass:: StaticFilesystemLoader
   .. autoclass:: StaticLocMemLoader

.. _origin:

origin
--------------------------------

.. automodule:: static_templates.origin

   .. autoclass:: AppOrigin

.. _templatetags:

templatetags.django\_static\_templates
----------------------------------------------------------------

.. automodule:: static_templates.templatetags.static_templates

   .. autofunction:: split
   .. autofunction:: to_js
   .. autofunction:: classes_to_js
   .. autofunction:: modules_to_js
   .. autofunction:: urls_to_js

.. exceptions:

exceptions
----------------------------------------------------------------

.. automodule:: static_templates.exceptions

   .. autoclass:: PlaceholderNotFound
   .. autoclass:: URLGenerationFailed


.. _placeholders:

placeholders
----------------------------------------------------------------

.. automodule:: static_templates.placeholders

   .. autofunction:: register_converter_placeholder
   .. autofunction:: register_variable_placeholder
   .. autofunction:: register_unnamed_placeholders
   .. autofunction:: resolve_placeholders
   .. autofunction:: resolve_unnamed_placeholders
