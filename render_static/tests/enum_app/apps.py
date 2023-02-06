from django.apps import AppConfig


class EnumAppConfig(AppConfig):
    name = 'render_static.tests.enum_app'
    label = name.replace('.', '_')
