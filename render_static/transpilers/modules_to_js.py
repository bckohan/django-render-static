"""
Built-in transpilers for python modules. Only one is provided that transpiles
any classes found in the modules.
"""
import inspect
from abc import abstractmethod
from types import ModuleType
from typing import Any, Collection, Dict, Generator, Type, Union

from django.utils.module_loading import import_module, import_string
from render_static.transpilers import JavaScriptGenerator
from render_static.transpilers.classes_to_js import (
    DefaultClassWriter,
    PythonClassVisitor,
)


class PythonModuleVisitor(JavaScriptGenerator):
    """
    An abstract JavaScriptGenerator that transpiles python modules to
    JavaScript. Transpilers used with modules_to_js must inherit from this
    base module visitor.
    """

    class_transpiler_: Type[PythonClassVisitor] = DefaultClassWriter
    class_transpiler_kwargs_: Dict[str, Any] = {}

    @property
    def class_transpiler(self):
        """
        An instance of the configured class transpiler that should be used
        to transpile any constituent classes on the module
        """
        return self.class_transpiler_(**self.class_transpiler_kwargs_)

    def __init__(
        self,
        class_transpiler: Union[
            Type[PythonClassVisitor], str
        ] = DefaultClassWriter,
        **kwargs
    ):
        self.class_transpiler_ = (
            import_string(class_transpiler)
            if isinstance(class_transpiler, str)
            else class_transpiler
        )
        self.class_transpiler_kwargs_ = {
            **{key: val for key, val in kwargs.items() if key != 'level'},
            'level': 0
        }
        super().__init__(**kwargs)

    def generate(
        self,
        modules: Union[Collection[Union[ModuleType, str]], ModuleType, str]
    ) -> str:
        """
        Implements JavaScriptGenerator::generate. Calls the visitation entry
        point and writes all the yielded JavaScript lines to a member string
        which is returned.

        :param modules: The module or list of modules or import strings of
            modules to transpile
        :return: The rendered module(s) as javascript.
        """
        if not isinstance(modules, Collection) or isinstance(modules, str):
            modules = [modules]
        for idx, module in enumerate(modules):
            if isinstance(module, str):
                module = import_module(module)
            for line in self.visit_module(
                module,
                is_last=(idx == (len(modules) - 1))
            ):
                self.write_line(line)
        return self.rendered_

    @abstractmethod
    def visit_module(
        self,
        module: ModuleType,
        is_last: bool = False
    ) -> Generator[str, None, None]:
        """
        Deriving classes must implement this method to transpile and yield the
        javascript for the module.

        :param module: The module to transpile
        :param is_last: True if this will be the last module visited
        :yield: transpiled JavaScript for the module
        """


class DefaultModuleWriter(PythonModuleVisitor):
    """
    A simple transpiler that will run all classes found in a module through
    the configured class transpiler.
    """

    def visit_module(
        self,
        module: ModuleType,
        is_last: bool = False
    ) -> Generator[str, None, None]:
        """
        Visits each class in turn and transpiles with the configured class
        transpiler.

        :param module: The module to transpile
        :param is_last: True if this will be the last module visited
        :yield: transpiled JavaScript for the module
        """
        classes = [
            member
            for _, member in vars(module).items()
            if inspect.isclass(member)
        ]
        for idx, cls in enumerate(classes):
            yield from self.visit_class(
                cls,
                is_last=(idx == (len(classes) - 1)) and is_last
            )

    def visit_class(
        self,
        cls: Type,
        is_last: bool = False
    ) -> Generator[str, None, None]:
        """
        Convert python class defines to javascript.

        :param cls: The class to visit and yield javascript for
        :param is_last: True if this is the last class that will be visited
        :yield: The class represented in javascript
        """
        lines = [
            line
            for line in self.class_transpiler.generate(cls).split(self.nl_)
            if line.strip()
        ]
        for idx, line in enumerate(lines):
            yield f'{line}' \
                  f'{"," if (idx == (len(lines) - 1) and not is_last) else ""}'
