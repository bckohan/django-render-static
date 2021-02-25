from django.apps import AppConfig


class App3Config(AppConfig):
    name = 'render_static.tests.app3'
    label = name.replace('.', '_')
