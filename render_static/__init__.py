r"""
    ____                 __             _____ __        __  _
   / __ \___  ____  ____/ /__  _____   / ___// /_____ _/ /_(_)____
  / /_/ / _ \/ __ \/ __  / _ \/ ___/   \__ \/ __/ __ `/ __/ / ___/
 / _, _/  __/ / / / /_/ /  __/ /      ___/ / /_/ /_/ / /_/ / /__
/_/ |_|\___/_/ /_/\__,_/\___/_/      /____/\__/\__,_/\__/_/\___/

"""
from .context import resolve_context
from .resource import resource
from .url_tree import ClassURLWriter, SimpleURLWriter, URLTreeVisitor

VERSION = (1, 1, 3)

__title__ = 'Django Render Static'
__version__ = '.'.join(str(i) for i in VERSION)
__author__ = 'Brian Kohan'
__license__ = 'MIT'
__copyright__ = 'Copyright 2020-2022 Brian Kohan'


default_app_config = 'render_static.apps.RenderStaticConfig'  # pylint: disable=C0103


class Jinja2DependencyNeeded:  # pylint: disable=R0903
    """
    Jinja2 is an optional dependency - lazy fail if its use is attempted without it being
    present on the python path.
    """

    def __init__(self, *args, **kwargs):
        raise ImportError(  # pragma: no cover
            'To use the Jinja2 backend you must install the Jinja2 python package.'
        )
