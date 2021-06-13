"""
Deprecated old style name - will be removed in V2.0
"""
import warnings

from render_static.management.commands.renderstatic import Command as RSCommand


class Command(RSCommand):
    # pylint: disable=C0115

    help = 'Deprecated, use renderstatic.'

    def handle(self, *args, **options):
        warnings.warn("Deprecated, use 'renderstatic' instead!", DeprecationWarning)
        super().handle(*args, **options)  # type: ignore
