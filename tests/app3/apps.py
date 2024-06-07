from django.apps import AppConfig


class App3Config(AppConfig):
    name = "tests.app3"
    label = name.replace(".", "_")
