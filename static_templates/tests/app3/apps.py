from django.apps import AppConfig


class App3Config(AppConfig):
    name = 'static_templates.tests.app3'
    label = name.replace('.', '_')
