# pylint: disable=C0114

from typing import Union

from django.apps.config import AppConfig
from django.template import Origin
from django.template.loaders.base import Loader

__all__ = ['AppOrigin']


class AppOrigin(Origin):
    """
    Extend Origin to contain the application it was found in. This is used by the static template
    engine to determine where a template should be written to disk.

    :param args:
    :param kwargs:
    """

    def __init__(self, *args: str, **kwargs: Union[str, Loader, AppConfig]) -> None:
        self.app = kwargs.pop('app', None)
        super().__init__(*args, **kwargs)

    def __eq__(self, other: Union[Origin, 'AppOrigin']) -> bool:
        """
        Determine origin equality as defined by template name and application origin. AppOrigins
        will compare as equal to Origins if neither have an app

        :param other: The AppOrigin or Origin to compare to
        :return: True if the origins are the same, False otherwise
        """
        return super().__eq__(other) and self.app == getattr(other, 'app', None)
