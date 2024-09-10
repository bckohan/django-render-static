import typing as t
from typing_extensions import Annotated
from django.db import models
from django_enum import EnumField
from django_enum.choices import IntegerChoices, TextChoices
from enum_properties import Symmetric, s

try:
    from django.utils.decorators import classproperty
except ImportError:
    from django.utils.functional import classproperty


class EnumTester(models.Model):
    class NotAnEnum:
        pass

    class Color(TextChoices):
        rgb: Annotated[t.Tuple[int, int, int], Symmetric()]
        hex: Annotated[str, Symmetric(case_fold=True)]

        # name   value   label       rgb       hex
        RED = "R", "Red", (1, 0, 0), "ff0000"
        GREEN = "G", "Green", (0, 1, 0), "00ff00"
        BLUE = "B", "Blue", (0, 0, 1), "0000ff"

        @classproperty
        def class_name(cls):
            return cls.__name__

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

        @classproperty
        def class_name(cls):
            return cls.__name__

        @classproperty
        def docs(cls):
            return "https://mapbox.com"

        # def __str__(self):
        #    return self.uri

    class AddressRoute(TextChoices):
        _symmetric_builtins_ = [s("name", case_fold=True)]

        alt: Annotated[t.List[str], Symmetric(case_fold=True)]
        str: str

        # name    value          alt
        ALLEY = (
            "ALY",
            ["ALLEE", "ALLY"],
            "Aly",
        )  # for this one __str__ and str match, dont change - important for str resolve test
        AVENUE = "AVE", ["AV", "AVEN", "AVENU", "AVN", "AVNUE"], "ave"
        CIRCLE = "CIR", ["CIRC", "CIRCL", "CRCL", "CRCLE"], "cir"

        def __str__(self):
            return self.value.title()

        @classproperty
        def class_name(cls):
            return cls.__name__

    color = EnumField(Color, null=True, default=None)
    style = EnumField(MapBoxStyle, default=MapBoxStyle.STREETS)
    route = EnumField(AddressRoute, strict=False, max_length=32)
