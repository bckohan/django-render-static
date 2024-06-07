r"""
    ____                 __             _____ __        __  _
   / __ \___  ____  ____/ /__  _____   / ___// /_____ _/ /_(_)____
  / /_/ / _ \/ __ \/ __  / _ \/ ___/   \__ \/ __/ __ `/ __/ / ___/
 / _, _/  __/ / / / /_/ /  __/ /      ___/ / /_/ /_/ / /_/ / /__
/_/ |_|\___/_/ /_/\__,_/\___/_/      /____/\__/\__,_/\__/_/\___/

"""

from .context import resolve_context
from .resource import resource
from .transpilers.defines_to_js import DefaultDefineTranspiler
from .transpilers.enums_to_js import EnumClassWriter
from .transpilers.urls_to_js import ClassURLWriter, SimpleURLWriter

VERSION = (3, 0, 0)

__title__ = "Django Render Static"
__version__ = ".".join(str(i) for i in VERSION)
__author__ = "Brian Kohan"
__license__ = "MIT"
__copyright__ = "Copyright 2020-2024 Brian Kohan"


__all__ = [
    "resource",
    "resolve_context",
    "DefaultDefineTranspiler",
    "EnumClassWriter",
    "ClassURLWriter",
    "SimpleURLWriter",
]
