from django.apps import AppConfig
from django.urls.converters import register_converter


class YearConverter:
    regex = '[1|2][0-9]{3}'
    placeholder = '2000'

    def to_python(self, value):
        return int(value)

    def to_url(self, value):
        return str(value)


register_converter(YearConverter, 'year')


class App1Config(AppConfig):
    name = 'static_templates.tests.app1'
    label = name.replace('.', '_')
