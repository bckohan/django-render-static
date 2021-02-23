from django.apps import AppConfig
from django.urls.converters import register_converter
from static_templates.placeholders import register_converter_placeholder


class YearConverter:
    regex = '[1|2][0-9]{3}'
    placeholder = '2000'

    def to_python(self, value):
        return int(value)

    def to_url(self, value):
        return str(value)


class NameConverter:
    regex = '(?:name1|name2)'

    def to_python(self, value):
        return str(value)

    def to_url(self, value):
        return str(value)


register_converter(YearConverter, 'year')
register_converter(NameConverter, 'name')

# this doesnt actually work - but it shouldnt matter because YearConverter.placeholder will
# eventually be tried
register_converter_placeholder(YearConverter, 'deadbeef')
register_converter_placeholder(YearConverter, 'deadbeef')


class App1Config(AppConfig):
    name = 'static_templates.tests.app1'
    label = name.replace('.', '_')
