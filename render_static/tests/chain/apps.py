from django.apps import AppConfig


class ChainConfig(AppConfig):
    name = "render_static.tests.chain"
    label = name.replace(".", "_")
