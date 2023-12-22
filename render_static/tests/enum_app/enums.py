from enum import Enum

from enum_properties import EnumProperties, s


class IndependentEnum(Enum):
    VALUE0 = 20
    VALUE1 = 21
    VALUE2 = 22


class DependentEnum(EnumProperties, s("indep")):
    VALUE0 = 0, IndependentEnum.VALUE2
    VALUE1 = 1, IndependentEnum.VALUE1
    VALUE2 = 2, IndependentEnum.VALUE0
