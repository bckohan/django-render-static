# pylint: disable=C0114

from abc import ABCMeta, abstractmethod


class JavaScriptGenerator(metaclass=ABCMeta):
    """
    An abstract base class for JavaScript generator types. This class defines a basic generation
    API, and implements configurable indentation/newline behavior. It also offers a toggle for
    ES5/ES6 mode that deriving classes may use.

    To use this class derive from it and implement generate().

    The configuration parameters that control the JavaScript output include:

        * *depth*
            the integer starting indentation level, default: 0
        * *indent*
            the string to use as the indentation string. May be None or empty string for no indent
            which will also cause no newlines to be inserted, default: \t
        * *es5*
            If true, generated JavaScript will be valid es5.

    :param kwargs: A set of configuration parameters for the generator, see above.
    """

    rendered_ = ''
    level_ = 0
    indent_ = '\t'
    es5_ = False
    nl_ = '\n'

    def __init__(self, **kwargs) -> None:
        self.level_ = kwargs.pop('depth', self.level_)
        self.indent_ = kwargs.pop('indent', self.indent_)
        if self.indent_ is None:
            self.indent_ = ''
        self.es5_ = kwargs.pop('es5', self.es5_)
        self.nl_ = self.nl_ if self.indent_ else ''  # pylint: disable=C0103

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
        Generate and return javascript as a string. Deriving classes must implement this.

        :param args: Any positional args - used by deriving classes
        :param kwargs: Any named args - used by deriving classes
        :return: The rendered JavaScript string
        """
        ...  # pragma: no cover

    def write_line(self, line: str) -> None:
        """
        Writes a line to the rendered JavaScript, respecting indentation/newline configuration for
        this generator.

        :param line: The code line to write
        :return:
        """
        if line is not None:
            self.rendered_ += f'{self.indent_*self.level_}{line}{self.nl_}'
