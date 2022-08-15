from django.apps import AppConfig


class EnumConfig(AppConfig):
    name = 'render_static.tests.enum'
    label = name.replace('.', '_')
