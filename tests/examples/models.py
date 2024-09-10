import typing as t
from django.db import models
from django_enum import EnumField
from django_enum.choices import IntegerChoices, TextChoices
from enum_properties import Symmetric, s
from typing_extensions import Annotated

try:
    from django.utils.decorators import classproperty
except ImportError:
    from django.utils.functional import classproperty


class ExampleModel(models.Model):
    DEFINE1 = "D1"
    DEFINE2 = "D2"
    DEFINE3 = "D3"
    DEFINES = ((DEFINE1, "Define 1"), (DEFINE2, "Define 2"), (DEFINE3, "Define 3"))

    define_field = models.CharField(choices=DEFINES, max_length=2)

    class Color(TextChoices):

        rgb: Annotated[t.Tuple[int, int, int], Symmetric()]
        hex: Annotated[str, Symmetric(case_fold=True)]

        # name   value   label       rgb       hex
        RED = "R", "Red", (1, 0, 0), "ff0000"
        GREEN = "G", "Green", (0, 1, 0), "00ff00"
        BLUE = "B", "Blue", (0, 0, 1), "0000ff"

    class MapBoxStyle(IntegerChoices):
        """
        https://docs.mapbox.com/api/maps/styles/
        """

        _symmetric_builtins_ = ["name", "uri", "label"]

        slug: Annotated[str, Symmetric(case_fold=True)]
        version: int

        # name            value  label                slug            version
        STREETS = 1, "Streets", "streets", 11
        OUTDOORS = 2, "Outdoors", "outdoors", 11
        LIGHT = 3, "Light", "light", 10
        DARK = 4, "Dark", "dark", 10
        SATELLITE = 5, "Satellite", "satellite", 9
        SATELLITE_STREETS = 6, "Satellite Streets", "satellite-streets", 11
        NAVIGATION_DAY = 7, "Navigation Day", "navigation-day", 1
        NAVIGATION_NIGHT = 8, "Navigation Night", "navigation-night", 1

        @property
        def uri(self):
            return f"mapbox://styles/mapbox/{self.slug}-v{self.version}"

        def __str__(self):
            return self.uri

        @classproperty
        def docs(cls):
            return "https://mapbox.com"

    color = EnumField(Color, null=True, default=None)
    style = EnumField(MapBoxStyle, default=MapBoxStyle.STREETS)
