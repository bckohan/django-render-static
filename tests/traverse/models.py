from django_enum.choices import IntegerChoices, TextChoices
from enum_properties import p, s


class ExampleModel:
    DEFINE1 = "D1"
    DEFINE2 = "D2"
    DEFINE3 = "D3"
    DEFINES = ((DEFINE1, "Define 1"), (DEFINE2, "Define 2"), (DEFINE3, "Define 3"))

    class Color(TextChoices, s("rgb"), s("hex", case_fold=True)):
        # name   value   label       rgb       hex
        RED = "R", "Red", (1, 0, 0), "ff0000"
        GREEN = "G", "Green", (0, 1, 0), "00ff00"
        BLUE = "B", "Blue", (0, 0, 1), "0000ff"

    class MapBoxStyle(IntegerChoices, s("slug", case_fold=True), p("version")):
        """
        https://docs.mapbox.com/api/maps/styles/
        """

        _symmetric_builtins_ = ["name", "uri", "label"]

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


not_a_define = None
