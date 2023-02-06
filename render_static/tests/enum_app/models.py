from django.db import models
from django_enum import EnumField, IntegerChoices, TextChoices
from enum_properties import p, s

try:
    from django.utils.decorators import classproperty
except ImportError:
    from django.utils.functional import classproperty


class EnumTester(models.Model):

    class NotAnEnum:
        pass

    class Color(TextChoices, s('rgb'), s('hex', case_fold=True)):
        # name   value   label       rgb       hex
        RED   =   'R',   'Red',   (1, 0, 0), 'ff0000'
        GREEN =   'G',   'Green', (0, 1, 0), '00ff00'
        BLUE  =   'B',   'Blue',  (0, 0, 1), '0000ff'

        @classproperty
        def class_name(cls):
            return cls.__name__

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

        @classproperty
        def class_name(cls):
            return cls.__name__

        @classproperty
        def docs(cls):
            return 'https://mapbox.com'

        # def __str__(self):
        #    return self.uri

    class AddressRoute(TextChoices, s('alt', case_fold=True), p('str')):

        _symmetric_builtins_ = [s('name', case_fold=True)]

        # name    value          alt
        ALLEY  =  'ALY',   ['ALLEE', 'ALLY'],                       'Aly' # for this one __str__ and str match, dont change - important for str resolve test
        AVENUE =  'AVE',   ['AV', 'AVEN', 'AVENU', 'AVN', 'AVNUE'], 'ave'
        CIRCLE =  'CIR',   ['CIRC', 'CIRCL', 'CRCL', 'CRCLE'],      'cir'

        def __str__(self):
            return self.value.title()

        @classproperty
        def class_name(cls):
            return cls.__name__

    color = EnumField(Color, null=True, default=None)
    style = EnumField(MapBoxStyle, default=MapBoxStyle.STREETS)
    route = EnumField(AddressRoute, strict=False, max_length=32)
