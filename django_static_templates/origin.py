from django.template import Origin
from typing import Union
from django.apps.config import AppConfig
from django.template.loaders.base import Loader

__all__ = ['AppOrigin']


class AppOrigin(Origin):

    def __init__(self, *args: str, **kwargs: Union[str, Loader, AppConfig]) -> None:
        self.app = kwargs.pop('app', None)
        super().__init__(*args, **kwargs)

    def __eq__(self, other: Union[Origin, 'AppOrigin']) -> bool:
        return super().__eq__(other) and self.app == getattr(other, 'app', None)

