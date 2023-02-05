"""
Base transpiler components.
"""

import json
import numbers
from abc import ABCMeta, abstractmethod
from datetime import date, datetime
from typing import Any, Callable, Optional, Union
from warnings import warn

from django.utils.module_loading import import_string

__all__ = ['to_js', 'JavaScriptGenerator']


def to_js(value: Any) -> str:
    """
    Default javascript transpilation function for values. Simply adds quotes
    if its a string and falls back on json.dumps for non-strings and non-
    numerics.

    :param value: The value to transpile
    :return: Valid javascript code that represents the value
    """
    if isinstance(value, numbers.Number):
        return str(value)
    if isinstance(value, str):
        return f'"{value}"'
    try:
        return json.dumps(value)
    except TypeError:
        if isinstance(value, datetime):
            return f'"{value.isoformat()}"'
        return f'"{str(value)}"'


def to_js_datetime(value: Any) -> str:
    """
    A javascript value transpilation function that transpiles python dates and
    datetimes to javascript Date objects instead of strings. To use this
    function in any of the transpilation routines pass it to the to_javascript
    parameter on any of the template tags::

        {% ... to_javascript="render_static.transpilers.to_js_datetime" %}

    :param value: The value to transpile
    :return: Valid javascript code that represents the value
    """
    if isinstance(value, date):
        return f'new Date("{value.isoformat()}")'
    return to_js(value)


class JavaScriptGenerator(metaclass=ABCMeta):
    """
    An abstract base class for JavaScript generator types. This class defines a
    basic generation API, and implements configurable indentation/newline
    behavior. It also offers a toggle for ES5/ES6 mode that deriving classes
    may use.

    To use this class derive from it and implement generate().

    The configuration parameters that control the JavaScript output include:

        * *depth*
            the integer starting indentation level, default: 0
        * *indent*
            the string to use as the indentation string. May be None or empty
            string for no indent which will also cause no newlines to be
            inserted, default: \t
        * *es5*
            If true, generated JavaScript will be valid es5.

    :param kwargs: A set of configuration parameters for the generator, see
        above.
    """

    rendered_ = ''
    level_ = 0
    indent_ = '\t'
    es5_ = False
    nl_ = '\n'
    to_javascript_ = to_js

    def __init__(
        self,
        level: int = level_,
        indent: Optional[str] = indent_,
        to_javascript: Union[str, Callable] = to_javascript_,
        **kwargs
    ) -> None:
        self.level_ = level
        self.indent_ = indent or ''
        self.es5_ = kwargs.pop('es5', self.es5_)
        if self.es5_:
            warn(
                'Transpilation to ES5 is no longer supported and will be '
                'removed in a future version.',
                DeprecationWarning,
                stacklevel=2
            )
        self.nl_ = self.nl_ if self.indent_ else ''  # pylint: disable=C0103
        self.to_javascript = (
            to_javascript
            if callable(to_javascript)
            else import_string(to_javascript)
        )
        assert callable(self.to_javascript), 'To_javascript is not callable!'

    def indent(self, incr: int = 1) -> None:
        """
        Step in one or more indentation levels.

        :param incr: The number of indentation levels to step into. Default: 1
        :return:
        """
        self.level_ += incr

    def outdent(self, decr: int = 1) -> None:
        """
        Step out one or more indentation levels.

        :param decr: The number of indentation levels to step out. Default: 1
        :return:
        """
        self.level_ -= decr
        self.level_ = max(0, self.level_)

    @abstractmethod
    def generate(self, _: Any) -> str:
        """
        Generate and return javascript as a string. Deriving classes must
        implement this.

        :param _: The object to transpile
        :return: The rendered JavaScript string
        """

    def write_line(self, line: str) -> None:
        """
        Writes a line to the rendered JavaScript, respecting
        indentation/newline configuration for this generator.

        :param line: The code line to write
        :return:
        """
        if line is not None:
            self.rendered_ += f'{self.indent_*self.level_}{line}{self.nl_}'

    def to_js(self, value: Any):
        """
        Return the javascript transpilation of the given value.

        :param value: The value to transpile
        :return: A valid javascript code that represents the value
        """
        return self.to_javascript(value)
