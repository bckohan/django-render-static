from django.apps import AppConfig


class ChainConfig(AppConfig):
    name = "tests.chain"
    label = name.replace(".", "_")
