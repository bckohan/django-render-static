from django.apps import AppConfig


class EnumAppConfig(AppConfig):
    name = "tests.enum_app"
    label = name.replace(".", "_")
