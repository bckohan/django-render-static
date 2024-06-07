from django.apps import AppConfig


class ExamplesConfig(AppConfig):
    name = "tests.examples"
    label = name.replace(".", "_")
