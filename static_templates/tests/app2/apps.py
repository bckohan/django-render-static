from django.apps import AppConfig


class App2Config(AppConfig):
    name = 'static_templates.tests.app2'
    label = name.replace('.', '_')
