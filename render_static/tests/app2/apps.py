from django.apps import AppConfig


class App2Config(AppConfig):
    name = 'render_static.tests.app2'
    label = name.replace('.', '_')
