from django.apps import AppConfig


class SPAConfig(AppConfig):
    name = "render_static.tests.spa"
    label = name.replace(".", "_")
