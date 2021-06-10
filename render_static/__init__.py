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

VERSION = (1, 1, 0)

__title__ = 'Django Render Static'
__version__ = '.'.join(str(i) for i in VERSION)
__author__ = 'Brian Kohan'
__license__ = 'MIT'
__copyright__ = 'Copyright 2020-2021 Brian Kohan'


default_app_config = 'render_static.apps.RenderStaticConfig'  # pylint: disable=C0103
