from abc import ABCMeta, abstractmethod


class JavaScriptGenerator(metaclass=ABCMeta):

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
        self.level_ += incr

    def outdent(self, decr: int = 1) -> None:
        self.level_ -= decr
        self.level_ = max(0, self.level_)

    @abstractmethod
    def generate(self, *args, **kwargs) -> str:
        ...  # pragma: no cover

    def write_line(self, line: str) -> None:
        if line is not None:
            self.rendered_ += f'{self.indent_*self.level_}{line}{self.nl_}'
