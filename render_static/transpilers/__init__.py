"""
Base transpiler components.
"""

from abc import ABCMeta, abstractmethod
from typing import Any, Optional, Union, Callable
import numbers
from django.utils.module_loading import import_string
import json


__all__ = ['to_js', 'JavaScriptGenerator']


def to_js(value: Any) -> str:
    if isinstance(value, numbers.Number):
        return str(value)
    if isinstance(value, str):
        return f'"{value}"'
    return json.dumps(value)


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
    def generate(self, *args, **kwargs) -> str:
        """
        Generate and return javascript as a string. Deriving classes must
        implement this.

        :param args: Any positional args - used by deriving classes
        :param kwargs: Any named args - used by deriving classes
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
        return self.to_javascript(value)
