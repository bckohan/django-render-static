from enum import IntEnum, auto

try:
    from django.utils.decorators import classproperty
except ImportError:
    from django.utils.functional import classproperty


class Def(IntEnum):

    VALUE1 = auto()
    VALUE2 = auto()
    VALUE3 = auto()

    @property
    def label(self):
        return self.name

    def __str__(self):
        return self.name.lower()

    @classproperty
    def class_name(cls):
        return cls.__name__
