"""A setuptools based setup module.
See:
https://packaging.python.org/en/latest/distributing.html
"""

from django.core.management.base import BaseCommand, CommandError
import os
import shutil
from django.template.engine import Engine
from django.template import Context
from django.contrib.staticfiles import finders
from django.conf import settings
from pprint import pformat

import logging


class PrettyLog(object):

    def __init__(self, obj):
        self.obj_ = obj

    def __repr__(self):
        return '\n' + pformat(self.obj_) + '\n'


class Command(BaseCommand):
    logger = logging.getLogger(__name__ + '.Command')

    help = 'Generate the static files from dynamic templates. Note, these files will not have a request in their ' \
           'template context.'

    def handle(self, *args, **options):

        engine = Engine.get_default()
        engine.loaders = settings.STATIC_TEMPLATES.get('loaders', []) + engine.loaders
        engine.template_loaders = engine.get_template_loaders(engine.loaders)

        context = settings.STATIC_TEMPLATES.get('context', {})
        if settings.STATIC_TEMPLATES.get('include_settings', False):
            context['settings'] = settings

        for file in settings.STATIC_TEMPLATES.get('files', []):
            ctx = context.copy()
            ctx.update(file.get('context', {}))
            if file.get('include_settings', settings.STATIC_TEMPLATES.get('include_settings', False)):
                ctx['settings'] = settings
            elif 'settings' in ctx:
                del ctx['settings']

            try:
                template = engine.get_template(file['src'])
            except Exception as e:
                raise CommandError(repr(e))
            dir = os.path.dirname(file.get('dest', file['src']))
            dest_path = finders.find(dir)
            if dest_path is None:
                raise CommandError('Destination directory %s does not exist in any app! You must create it.' % (dir,))
            dest_path = os.path.join(dest_path, os.path.basename(file.get('dest', file['src'])))
            with open(dest_path, 'w') as output:
                self.logger.info('Writting %s to %s.', template.origin.name, dest_path)
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug('Using context: %s', PrettyLog(ctx))
                output.write(template.render(Context(ctx)))
