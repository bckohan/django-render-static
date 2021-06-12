"""
Generate documents from templates and write them to disk at either pre-configured locations or in
their associated Django app's static directory if residing within an app. This command should be run
during the deployment phase and always before collectstatic is run.

This command accepts a list of template names to render. If no names are specified all templates
as specified in ``STATIC_TEMPLATES`` will be rendered. A template name supplied as an argument does
not need to be specified in ``STATIC_TEMPLATES`` for it to be found and rendered. Such templates
will be given the global context as specified in ``STATIC_TEMPLATES``.
"""
from django.core.management.base import BaseCommand, CommandError
from render_static.engine import StaticTemplateEngine


def get_parser():
    """
    This instantiates an argparser parser for this command so sphinx doc can autogenerate the
    docs for it.
    """
    cmd = Command()
    parser = cmd.create_parser('manage.py', 'render_static')
    return parser


class Command(BaseCommand):
    # pylint: disable=C0115

    help = 'Generate static files from static templates.'

    def add_arguments(self, parser):

        parser.add_argument(
            'selectors',
            metavar='S',
            nargs='*',
            type=str,
            help='Template name selectors for the templates to render. Selectors are like template '
                 'names, but can be glob patterns, or patterns understood by specifically '
                 'configured loaders. Template selectors can resolve to more than one valid '
                 'template name. Default: All template selectors specified in settings.'
        )
        parser.add_argument(
            '-c',
            '--context',
            dest='context',
            type=str,
            default=None,
            help='An alternate context to use when rendering the selected templates. This will '
                 'override any conflicting context parameters in the context(s) specified in '
                 'settings. Will be treated as a path to any of the following file types: '
                 'python files, json files, yaml files, or pickled python dictionaries.'
        )

        parser.add_argument(
            '-d',
            '--destination',
            dest='dest',
            type=str,
            default=None,
            help='The location to render templates to. This will override the destination '
                 'specified in settings for selected template, if one exists. If no destination is '
                 'specified in settings or here, the default destination is settings.STATIC_ROOT.'
        )

        parser.add_argument(
            '--first-engine',
            dest='first_engine',
            action='store_true',
            default=False,
            help='Render only the set of templates that match the selector that are found by the '
                 'highest priority rendering engine. By default (False) any templates that match '
                 'the selector from any engine will be rendered.'
        )

        parser.add_argument(
            '--first-loader',
            dest='first_loader',
            action='store_true',
            default=False,
            help='Render only the set of templates found by the first loader that match any part '
                 'of the selector. By default (False) any template name that matches the selector '
                 'from any loader will be rendered.'
        )

        parser.add_argument(
            '--first-preference',
            dest='first_preference',
            action='store_true',
            default=False,
            help='Render only the templates that match the first preference for each loader. When '
                 'combined with --first-loader render only the first preference(s) of the '
                 'first loader. Preferences are loader specific and documented on the '
                 'loader. For instance, for the App directories loader preference is defined as '
                 'app precedence in settings - so if any templates match the selector for the '
                 'highest priority app, only those templates would be rendered.'
        )

    def handle(self, *args, **options):

        engine = StaticTemplateEngine()

        selectors = options.get('selectors', [])
        if not selectors:
            selectors = list(engine.templates.keys())

        if not selectors:
            self.stdout.write(self.style.WARNING('No templates selected for generation.'))
            return

        try:
            for render in engine.render_each(
                    *selectors,
                    dest=options.get('dest', None),
                    context=options.get('context', None),
                    first_engine=options.get('first_engine', False),
                    first_loader=options.get('first_loader', False),
                    first_preference=options.get('first_preference', False)
            ):
                self.stdout.write(
                    self.style.SUCCESS(f'Rendered {render}.')
                )
        except Exception as exp:
            raise CommandError(f'Error rendering template to disk: {exp}') from exp
