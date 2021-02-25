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
            'templates',
            metavar='T',
            nargs='*',
            type=str,
            help='The template names to render. Default: All templates specified in settings.'
        )

    def handle(self, *args, **options):

        engine = StaticTemplateEngine()

        templates = options.get('templates', [])
        if not templates:
            templates = list(engine.templates.keys())

        if not templates:
            self.stdout.write(self.style.WARNING('No templates selected for generation.'))
            return

        for template in templates:
            try:
                destination = engine.render_to_disk(template)
                self.stdout.write(
                    self.style.SUCCESS(f'Rendered template {template} to {destination}.')
                )
            except Exception as exp:
                raise CommandError(f'Error rendering template {template} to disk: {exp}') from exp
