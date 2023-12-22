from django.apps import AppConfig


class ExamplesConfig(AppConfig):
    name = "render_static.tests.examples"
    label = name.replace(".", "_")
