from django.core.management.base import BaseCommand, CommandError
from django_static_templates.engine import StaticTemplateEngine


class Command(BaseCommand):

    help = 'Generate static files from static templates.'

    def add_arguments(self, parser):

        parser.add_argument(
            'templates',
            metavar='T',
            nargs='*',
            type=str,
            help='The template names to generate. Default: All templates specified in settings.'
        )

    def handle(self, *args, **options):

        engine = StaticTemplateEngine()

        templates = options.get('templates', [])
        if not templates:
            templates = list(engine.templates.keys())

        if not templates:
            self.stdout.write(self.style.WARNING(f'No templates selected for generation.'))
            return

        for template in templates:
            try:
                destination = engine.render_to_disk(template)
                self.stdout.write(self.style.SUCCESS(f'Rendered template {template} to {destination}.'))
            except Exception as e:
                raise CommandError(f'Error rendering template {template} to disk: {e}')
