from django.apps import AppConfig


class App2Config(AppConfig):
    name = "tests.app2"
    label = name.replace(".", "_")
