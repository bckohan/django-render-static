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

.. automodule:: render_static.backends.django

   .. autoclass:: StaticDjangoTemplates

.. automodule:: render_static.backends.jinja2

   .. autoclass:: StaticJinja2Templates


.. _django_loaders:

loaders.django
---------------------------------

.. automodule:: render_static.loaders.django

   .. autoclass:: StaticAppDirectoriesLoader
   .. autoclass:: StaticFilesystemLoader
   .. autoclass:: StaticAppDirectoriesBatchLoader
   .. autoclass:: StaticFilesystemBatchLoader
   .. autoclass:: StaticLocMemLoader

.. _jinja2_loaders:

loaders.jinja2
---------------------------------

.. automodule:: render_static.loaders.jinja2

   .. autoclass:: StaticFileSystemLoader
   .. autoclass:: StaticFileSystemBatchLoader
   .. autoclass:: StaticPackageLoader
   .. autoclass:: StaticPrefixLoader
   .. autoclass:: StaticFunctionLoader
   .. autoclass:: StaticDictLoader
   .. autoclass:: StaticChoiceLoader
   .. autoclass:: StaticModuleLoader


.. _loader_mixins:

loaders.mixins
---------------------------------

.. automodule:: render_static.loaders.mixins

   .. autoclass:: BatchLoaderMixin

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
    .. autofunction:: defines_to_js
    .. autofunction:: urls_to_js
    .. autofunction:: enums_to_js

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


.. _transpilers:

transpilers
----------------------------------------------------------------

.. automodule:: render_static.transpilers.base

   .. autofunction:: to_js
   .. autofunction:: to_js_datetime
   .. autoclass:: CodeWriter
   .. autoclass:: Transpiler
   .. autoproperty:: Transpiler.context


.. _transpilers_defines_to_js:

transpilers.defines_to_js
----------------------------------------------------------------


.. automodule:: render_static.transpilers.defines_to_js

   .. autoclass:: DefaultDefineTranspiler
   .. autoproperty:: DefaultDefineTranspiler.context


.. _transpilers_urls_to_js:

transpilers.urls_to_js
----------------------------------------------------------------

.. automodule:: render_static.transpilers.urls_to_js

   .. autoclass:: URLTreeVisitor
   .. autoproperty:: URLTreeVisitor.context
   .. autoclass:: SimpleURLWriter
   .. autoproperty:: SimpleURLWriter.context
   .. autoclass:: ClassURLWriter
   .. autoproperty:: ClassURLWriter.context
   .. autoclass:: Substitute
   .. autofunction:: normalize_ns
   .. autofunction:: build_tree


.. _transpilers_enums_to_js:

transpilers.enums_to_js
----------------------------------------------------------------

.. automodule:: render_static.transpilers.enums_to_js

   .. autoclass:: UnrecognizedBehavior
   .. autoclass:: EnumTranspiler
   .. autoclass:: EnumClassWriter
   .. autoproperty:: EnumClassWriter.context


.. _context:

context
----------------------------------------------------------------

.. automodule:: render_static.context

   .. autofunction:: resolve_context


.. _resource:

resource
----------------------------------------------------------------

.. automodule:: render_static.resource

   .. autofunction:: resource


