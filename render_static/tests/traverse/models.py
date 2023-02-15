from django_enum import TextChoices, IntegerChoices
from enum_properties import s, p


class ExampleModel:

    DEFINE1 = 'D1'
    DEFINE2 = 'D2'
    DEFINE3 = 'D3'
    DEFINES = (
        (DEFINE1, 'Define 1'),
        (DEFINE2, 'Define 2'),
        (DEFINE3, 'Define 3')
    )

    class Color(TextChoices, s('rgb'), s('hex', case_fold=True)):
        # name   value   label       rgb       hex
        RED   =   'R',   'Red',   (1, 0, 0), 'ff0000'
        GREEN =   'G',   'Green', (0, 1, 0), '00ff00'
        BLUE  =   'B',   'Blue',  (0, 0, 1), '0000ff'

    class MapBoxStyle(
        IntegerChoices,
        s('slug', case_fold=True),
        s('label', case_fold=True),
        p('version')
    ):
        """
        https://docs.mapbox.com/api/maps/styles/
        """
        _symmetric_builtins_ = ['name', 'uri']

        # name            value    slug                 label           version
        STREETS =           1,   'streets',           'Streets',             11
        OUTDOORS =          2,   'outdoors',          'Outdoors',            11
        LIGHT =             3,   'light',             'Light',               10
        DARK =              4,   'dark',              'Dark',                10
        SATELLITE =         5,   'satellite',         'Satellite',            9
        SATELLITE_STREETS = 6,   'satellite-streets', 'Satellite Streets',   11
        NAVIGATION_DAY =    7,   'navigation-day',    'Navigation Day',       1
        NAVIGATION_NIGHT =  8,   'navigation-night',  'Navigation Night',     1

        @property
        def uri(self):
            return f'mapbox://styles/mapbox/{self.slug}-v{self.version}'

        def __str__(self):
            return self.uri
