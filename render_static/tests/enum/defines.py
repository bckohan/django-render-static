from enum import Enum, auto


class Define(Enum):

    VALUE1 = auto()
    VALUE2 = auto()
    VALUE3 = auto()

    @property
    def label(self):
        return self.name

    def __str__(self):
        return self.name.lower()
