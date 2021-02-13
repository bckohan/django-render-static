# pylint: disable=C0114

import os
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Union

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.template.backends.base import BaseEngine
from django.template.exceptions import TemplateDoesNotExist
from django.template.utils import InvalidTemplateEngineError
from django.utils.functional import cached_property
from django.utils.module_loading import import_string

__all__ = ['StaticTemplateEngine']


class StaticTemplateEngine:
    """
    An engine for rendering static templates to disk based on a standard STATIC_TEMPLATES
    configuration either passed in at construction or obtained from settings.

    :param config: If provided use this configuration instead of the one from settings
    :raises ImproperlyConfigured: If there are any errors in the configuration passed in or
        specified in settings.
    """

    config_: Dict = {}

    DEFAULT_ENGINE_CONFIG = [{
        'BACKEND': 'django_static_templates.backends.StaticDjangoTemplates',
        'DIRS': [],
        'OPTIONS': {
            'loaders': ['django_static_templates.loaders.StaticAppDirectoriesLoader'],
            'builtins': ['django_static_templates.templatetags.django_static_templates']
        },
    }]

    class TemplateConfig:
        """
        Container for template specific configuration parameters.

        :param name: The name of the template
        :param dest: The absolute destination directory where the template will be written. May be
            None which indicates the template will be written to its owning app's static directory
            if it was loaded with an app directory loader
        :param context: A specific dictionary context to use for this template. This may override
            global context parameters
        :raises ImproperlyConfigured: If there are any unexpected or misconfigured parameters
        """

        context_: Dict = {}
        dest_: Optional[Path] = None

        def __init__(
                self,
                name: str,
                dest: Optional[Union[Path, str]] = None,
                context: Optional[Dict] = None
        ) -> None:
            self.name = name

            if dest is not None:
                if not isinstance(dest, (str, Path)):
                    raise ImproperlyConfigured(
                        f"Template {name} 'dest' parameter in STATIC_TEMPLATES must be a string or "
                        f"path-like object, not {type(dest)}"
                    )
                self.dest_ = Path(dest)
                if not self.dest_.is_absolute():
                    raise ImproperlyConfigured(
                        f'In STATIC_TEMPLATES, template {name} dest must be absolute!'
                    )

            if context is not None:
                if not isinstance(context, dict):
                    raise ImproperlyConfigured(
                        f"Template {name} 'context' parameter in STATIC_TEMPLATES must be a "
                        f"dictionary, not {type(context)}"
                    )

                self.context_ = context

        @property
        def context(self) -> Dict:
            """
            The context specific to this template. This will not include global parameters only
            the context as specified in the template configuration.
            """
            return self.context_

        @property
        def dest(self) -> Optional[Path]:
            """
            The location this template should be saved to, if specified.
            """
            return self.dest_

    def __init__(self, config: Optional[Dict] = None) -> None:
        if config:
            self.config_ = config

    @cached_property
    def config(self) -> dict:
        """
        Lazy configuration property. Fetch the STATIC_TEMPLATES configuration dictionary which will
        either be the configuration passed in on initialization or the config specified in the
        STATIC_TEMPLATES setting.

        :return: The STATIC_TEMPLATES configuration this engine has initialized from
        :raises ImproperlyConfigured:
        """
        if not self.config_:
            if not hasattr(settings, 'STATIC_TEMPLATES'):
                raise ImproperlyConfigured(
                    'No STATIC_TEMPLATES configuration directive in settings!'
                )

            self.config_ = settings.STATIC_TEMPLATES

        unrecognized_keys = [
            key for key in self.config_.keys() if key not in ['ENGINES', 'templates', 'context']
        ]
        if unrecognized_keys:
            raise ImproperlyConfigured(
                f'Unrecognized STATIC_TEMPLATES configuration directives: {unrecognized_keys}'
            )
        return self.config_

    @cached_property
    def context(self) -> dict:
        """
        Lazy context property. Fetch the global context that will be fed to all templates. This
        includes the settings object and anything listed in the context dictionary in the
        STATIC_TEMPLATES configuration.

        :return: A dictionary containing the global template context
        :raises ImproperlyConfigured: If the template context is specified and is not a dictionary.
        """
        global_ctx = self.config.get('context', {})
        if not isinstance(global_ctx, dict):
            raise ImproperlyConfigured(
                "STATIC_TEMPLATES 'context' configuration directive must be a dictionary!"
            )
        return {
            'settings': settings,
            **global_ctx
        }

    @cached_property
    def templates(self) -> dict:
        """
        Lazy templates property. Fetch the dictionary mapping template names to TemplateConfig
        objects initializing them if necessary.

        :return: A dictionary mapping template names to configurations
        :raise ImproperlyConfigured: If there are any configuration issues with the templates
        """
        try:
            templates = {
                name: StaticTemplateEngine.TemplateConfig(name=name, **config)
                for name, config in self.config.get('templates', {}).items()
            }
        except ImproperlyConfigured:
            raise
        except Exception as exp:
            raise ImproperlyConfigured(f"Invalid 'templates' in STATIC_TEMPLATE: {exp}!") from exp

        return templates

    @cached_property
    def engines(self) -> dict:
        """
        Lazy engines property. Fetch the dictionary of engine names to engine instances
        based on the configuration, initializing said entities if necessary.

        :return: A dictionary mapping engine names to instances
        :raise ImproperlyConfigured: If there are configuration problems with the engine backends.
        """
        engine_defs = self.config.get('ENGINES', None)
        if engine_defs is None:
            self.config['ENGINES'] = self.DEFAULT_ENGINE_CONFIG
        elif not hasattr(engine_defs, '__iter__'):
            raise ImproperlyConfigured(
                f'ENGINES in STATIC_TEMPLATES setting must be an iterable containing engine '
                f'configurations! Encountered: {type(engine_defs)}'
            )

        engines = {}
        backend_names = []
        for backend in self.config.get('ENGINES', []):
            try:
                # This will raise an exception if 'BACKEND' doesn't exist or
                # isn't a string containing at least one dot.
                default_name = backend['BACKEND'].rsplit('.', 2)[-1]
            except Exception as exp:
                invalid_backend = backend.get('BACKEND', '<not defined>')
                raise ImproperlyConfigured(
                    f'Invalid BACKEND for a static template engine: {invalid_backend}. Check '
                    f'your STATIC_TEMPLATES setting.'
                ) from exp

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
        """
        Accessor for backend instances indexed by name.

        :param alias: The name of the backend to fetch
        :return: The backend instance
        :raises InvalidTemplateEngineError: If a backend of the given alias does not exist
        """
        try:
            return self.engines[alias]
        except KeyError as key_error:
            raise InvalidTemplateEngineError(
                f"Could not find config for '{alias}' "
                f"in settings.STATIC_TEMPLATES"
            ) from key_error

    def __iter__(self):
        """
        Iterate through the backends.
        """
        return iter(self.engines)

    def all(self) -> List[BaseEngine]:
        """
        Get a list of all registered engines in order of precedence.
        :return: A list of engine instances in order of precedence
        """
        return [self[alias] for alias in self]

    def render_to_disk(self, template_name: str) -> Path:
        """
        Render the template of the highest precedence for the given template name to disk.
        The location of the directory location of the rendered template will either be

        :param template_name: The name of the template to render to disk
        :return: The path to the rendered template on disk
        :raises TemplateDoesNotExist: if no template by the given name is found
        :raises ImproperlyConfigured: if not enough information was given to render and write the
            template
        """
        config = self.templates.get(
            template_name,
            StaticTemplateEngine.TemplateConfig(name=template_name)
        )
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
                    f"Template {template_name} must be configured with a 'dest' since it was not "
                    f"loaded from an app!"
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
