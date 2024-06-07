from enum import Enum, IntEnum, auto

__all__ = ["Class1Module1", "Class2Module1", "MODULE_MEMBER"]

MODULE_MEMBER = "a string"
module_list = ["things"]


class Class1Module1:
    MEMBER1 = "string"
    MEMBER2 = 1

    class SubClass1:
        class Enum1(Enum):
            VALUE1 = 1
            VALUE2 = 2
            VALUE3 = 3

        class Enum2(IntEnum):
            VALUE1 = auto()
            VALUE2 = auto()
            VALUE3 = auto()

        LIST_MEMBER = [en for en in Enum1]


class Class2Module1:
    class EnumStr(str, Enum):
        STR1 = "str1"
        STR2 = "str2"
        STR3 = "str3"

    class NotAnEnum:
        pass

    A_DICTIONARY = {"str1": EnumStr.STR1, "str2": EnumStr.STR3}
