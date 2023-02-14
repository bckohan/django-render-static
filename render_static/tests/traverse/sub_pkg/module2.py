from enum import Enum, IntEnum, auto


class Class1Module2:
    MEMBER1 = 'string'
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


class Class2Module2:
    class EnumStr(str, Enum):
        STR1 = 'str1'
        STR2 = 'str2'
        STR3 = 'str3'

    A_DICTIONARY = {
        'str1': EnumStr.STR1,
        'str2': EnumStr.STR3
    }
