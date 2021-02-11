from django.utils.functional import cached_property
from django.utils.module_loading import import_string
from django.core.exceptions import ImproperlyConfigured
from django.template.backends.base import BaseEngine
from django.template.utils import InvalidTemplateEngineError
from django.template.exceptions import TemplateDoesNotExist
from collections import Counter
from django.conf import settings
from pathlib import Path
from typing import Union
import os
from jinja2 import Environment

__all__ = ['StaticTemplateEngine']


class StaticTemplateEngine(object):
    """
    An engine for rendering static templates to disk based on a standard STATIC_TEMPLATES configuration either passed
    in at construction or obtained from settings.

    :param config: If provided use this configuration instead of the one from settings
    :raises ImproperlyConfigured: If there are any errors in the configuration passed in or specified in settings.
    """

    config_ = None

    DEFAULT_ENGINE_CONFIG = [{
        'BACKEND': 'django_static_templates.backends.StaticDjangoTemplates',
        'DIRS': [],
        'OPTIONS': {
            'loaders': ['django_static_templates.loaders.StaticAppDirectoriesLoader'],
            'builtins': ['django_static_templates.templatetags.django_static_templates']
        },
    }]

    class TemplateConfig(object):
        """
        Container for template specific configuration parameters.

        :param name: The name of the template
        :param dest: The absolute destination directory where the template will be written. May be None which indicates
            the template will be written to its owning app's static directory if it was loaded with an app directory
            loader
        :param context: A specific dictionary context to use for this template. This may override global context
            parameters
        :raises ImproperlyConfigured: If there are any unexpected or misconfigured parameters
        """

        context_ = {}
        dest_ = None

        def __init__(self, name: str, dest: Union[Path, str] = None, context: dict = None) -> None:
            self.name = name

            if dest is not None:
                if not isinstance(dest, (str, Path)):
                    raise ImproperlyConfigured(
                        f"Template {name} 'dest' parameter in STATIC_TEMPLATES must be a string or path-like object, "
                        f"not {type(dest)}"
                    )
                self.dest_ = Path(dest)
                if not self.dest_.is_absolute():
                    raise ImproperlyConfigured(f'In STATIC_TEMPLATES, template {name} dest must be absolute!')

            if context is not None:
                if not isinstance(context, dict):
                    raise ImproperlyConfigured(
                        f"Template {name} 'context' parameter in STATIC_TEMPLATES must be a dictionary, "
                        f"not {type(context)}"
                    )

                self.context_ = context

        @property
        def context(self) -> dict:
            return self.context_

        @property
        def dest(self) -> dict:
            return self.dest_

    def __init__(self, config: dict = None) -> None:
        self.config_ = config

    @cached_property
    def config(self) -> dict:
        if not self.config_:
            if not hasattr(settings, 'STATIC_TEMPLATES'):
                raise ImproperlyConfigured('No STATIC_TEMPLATES configuration directive in settings!')

            self.config_ = settings.STATIC_TEMPLATES

        unrecognized_keys = [key for key in self.config_.keys() if key not in ['ENGINES', 'templates', 'context']]
        if unrecognized_keys:
            raise ImproperlyConfigured(f'Unrecognized STATIC_TEMPLATES configuration directives: {unrecognized_keys}')
        return self.config_

    @cached_property
    def context(self) -> dict:
        global_ctx = self.config.get('context', {})
        if not isinstance(global_ctx, dict):
            raise ImproperlyConfigured("STATIC_TEMPLATES 'context' configuration directive must be a dictionary!")
        return {
            'settings': settings,
            **global_ctx
        }

    @cached_property
    def templates(self) -> dict:
        try:
            templates = {
                name: StaticTemplateEngine.TemplateConfig(name=name, **config)
                for name, config in self.config.get('templates', {}).items()
            }
        except ImproperlyConfigured as e:
            raise e
        except Exception as e:
            raise ImproperlyConfigured(f"Invalid 'templates' in STATIC_TEMPLATE: {e}!")

        return templates

    @cached_property
    def engines(self) -> dict:
        engine_defs = self.config.get('ENGINES', {})
        if not engine_defs:
            self.config['ENGINES'] = self.DEFAULT_ENGINE_CONFIG
        elif not hasattr(engine_defs, '__iter__'):
            raise ImproperlyConfigured(
                f'ENGINES in STATIC_TEMPLATES setting must be an iterable containing engine configurations! '
                f'Encountered: {type(engine_defs)}'
            )

        engines = {}
        backend_names = []
        for backend in self.config.get('ENGINES', []):
            try:
                # This will raise an exception if 'BACKEND' doesn't exist or
                # isn't a string containing at least one dot.
                default_name = backend['BACKEND'].rsplit('.', 2)[-1]
            except Exception:
                invalid_backend = backend.get('BACKEND', '<not defined>')
                raise ImproperlyConfigured(
                    f'Invalid BACKEND for a static template engine: {invalid_backend}. Check '
                    f'your STATIC_TEMPLATES setting.'
                )

            # set defaults
            backend = {
                'NAME': default_name,
                'DIRS': [],
                'APP_DIRS': False,
                'OPTIONS': {},
                **backend,
            }
            engines[backend['NAME']] = backend
            backend_names.append(backend['NAME'])

        counts = Counter(backend_names)
        duplicates = [alias for alias, count in counts.most_common() if count > 1]
        if duplicates:
            raise ImproperlyConfigured(
                f"Template engine aliases are not unique, duplicates: {', '.join(duplicates)}. "
                f"Set a unique NAME for each engine in settings.STATIC_TEMPLATES."
            )

        for alias, config in engines.items():
            params = config.copy()
            backend = params.pop('BACKEND')
            engines[alias] = import_string(backend)(params)

        return engines

    def __getitem__(self, alias: str) -> BaseEngine:
        try:
            return self.engines[alias]
        except KeyError:
            raise InvalidTemplateEngineError(
                f"Could not find config for '{alias}' "
                f"in settings.STATIC_TEMPLATES"
            )

    def __iter__(self):
        return iter(self.engines)

    def all(self):
        """
        Get a list of all registered engines in order of precedence.
        :return: A list of engine instances in order of precedence
        """
        return [self[alias] for alias in self]

    def render_to_disk(self, template_name: str) -> Path:
        """
        Render the template of the highest precedence for the given template name to disk. The location of the
        directory location of the rendered template will either be

        :param template_name: The name of the template to render to disk
        :return: The path to the rendered template on disk
        :raises TemplateDoesNotExist: if no template by the given name is found
        :raises ImproperlyConfigured: if not enough information was given to render and write the template
        """
        config = self.templates.get(template_name, StaticTemplateEngine.TemplateConfig(name=template_name))
        template = None
        chain = []
        for engine in self.all():
            try:
                template = engine.get_template(template_name)
            except TemplateDoesNotExist as tdne:
                chain.append(tdne)
                continue
        if template is None:
            raise TemplateDoesNotExist(template_name, chain=chain)

        dest = config.dest
        if dest is None:
            if not getattr(template.origin, 'app', None):
                raise ImproperlyConfigured(
                    f"Template {template_name} must be configured with a 'dest' since it was not loaded from an app!"
                )

            dest = Path(template.origin.app.path) / 'static' / template_name

        if not dest.parent.exists():
            os.makedirs(str(dest.parent))

        with open(dest, 'w') as temp_out:
            temp_out.write(
                template.render({
                    **self.context,
                    **config.context
                })
            )

        return dest
