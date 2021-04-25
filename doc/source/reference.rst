.. _ref-reference:

=========
Reference
=========

.. _engine:

engine
--------------------------------

.. automodule:: render_static.engine

   .. autoclass:: StaticTemplateEngine

.. _backends:

backends
----------------------------------

.. automodule:: render_static.backends

   .. autoclass:: StaticDjangoTemplates
   .. autoclass:: StaticJinja2Templates


.. _loaders:

loaders
---------------------------------

.. automodule:: render_static.loaders

   .. autoclass:: StaticAppDirectoriesLoader
   .. autoclass:: StaticFilesystemLoader
   .. autoclass:: StaticLocMemLoader

.. _origin:

origin
--------------------------------

.. automodule:: render_static.origin

   .. autoclass:: AppOrigin

.. _templatetags:

templatetags.django\_static\_templates
----------------------------------------------------------------

.. automodule:: render_static.templatetags.render_static

    .. autofunction:: split
    .. autofunction:: to_js
    .. autofunction:: classes_to_js
    .. autofunction:: modules_to_js
    .. autofunction:: urls_to_js

.. _exceptions:

exceptions
----------------------------------------------------------------

.. automodule:: render_static.exceptions

    .. autoclass:: URLGenerationFailed
    .. autoclass:: ReversalLimitHit


.. _placeholders:

placeholders
----------------------------------------------------------------

.. automodule:: render_static.placeholders

   .. autofunction:: register_converter_placeholder
   .. autofunction:: register_variable_placeholder
   .. autofunction:: register_unnamed_placeholders
   .. autofunction:: resolve_placeholders
   .. autofunction:: resolve_unnamed_placeholders


.. _javascript:

javascript
----------------------------------------------------------------

.. automodule:: render_static.javascript

   .. autoclass:: JavaScriptGenerator


.. _url_tree:

url_tree
----------------------------------------------------------------

.. automodule:: render_static.url_tree

   .. autoclass:: URLTreeVisitor
   .. autoclass:: SimpleURLWriter
   .. autoclass:: ClassURLWriter
   .. autoclass:: Substitute
   .. autofunction:: normalize_ns
   .. autofunction:: build_tree
