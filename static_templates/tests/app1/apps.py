from django.apps import AppConfig


class App1Config(AppConfig):
    name = 'static_templates.tests.app1'
    label = name.replace('.', '_')
