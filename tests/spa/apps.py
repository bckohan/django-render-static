from django.apps import AppConfig


class SPAConfig(AppConfig):
    name = "tests.spa"
    label = name.replace(".", "_")
