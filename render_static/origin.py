from typing import Optional

from django.apps import AppConfig
from django.template import Origin

__all__ = ["AppOrigin"]


class AppOrigin(Origin):
    """
    Extend Origin to contain the application it was found in. This is used by
    the static template engine to determine where a template should be written
    to disk.

    :param args:
    :param kwargs:
    """

    app: Optional[AppConfig] = None

    def __init__(
        self, name, app: Optional[AppConfig] = None, template_name=None, loader=None
    ) -> None:
        self.app = app
        super().__init__(name, template_name=template_name, loader=loader)

    def __eq__(self, other) -> bool:
        """
        Determine origin equality as defined by template name and application
        origin. AppOrigins will compare as equal to Origins if neither have an
        app

        :param other: The AppOrigin or Origin to compare to
        :return: True if the origins are the same, False otherwise
        """
        return super().__eq__(other) and self.app == getattr(other, "app", None)
