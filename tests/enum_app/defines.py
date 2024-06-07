from datetime import date, datetime, timezone
from enum import Enum, IntEnum, auto

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


class TimeEnum(Enum):
    YEAR1 = date(year=2020, month=1, day=1)
    YEAR2 = date(year=2021, month=1, day=1)
    YEAR3 = date(year=2022, month=1, day=1)
    YEAR4 = date(year=2023, month=1, day=1)

    @property
    def with_time(self):
        return datetime(
            year=self.value.year,
            month=self.value.month,
            day=self.value.day,
            tzinfo=timezone.utc,
        )
