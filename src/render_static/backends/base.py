import typing as t
from abc import abstractmethod

from django.template import Template
from django.template.backends.base import BaseEngine

T = t.TypeVar("T")


def with_typehint(baseclass: t.Type[T]) -> t.Type[T]:
    """
    Change inheritance to add Field type hints when type checking is running.
    This is just more simple than defining a Protocol - revisit if Django
    provides Field protocol - should also just be a way to create a Protocol
    from a class?

    This is icky but it works - revisit in future.
    """
    if t.TYPE_CHECKING:
        return baseclass  # pragma: no cover
    return object  # type: ignore


class StaticEngine(with_typehint(BaseEngine)):  # type: ignore
    @abstractmethod
    def select_templates(
        self, selector: str, first_loader: bool = False, first_preference: bool = False
    ) -> t.List[str]:
        """
        Resolves a template selector into a list of template names from the
        loaders configured on this backend engine.

        :param selector: The template selector
        :param first_loader: If True, return only the set of template names
            from the first loader that matches any part of the selector. By
            default (False) any template name that matches the selector from
            any loader will be returned.
        :param first_preference: If true, return only the templates that match
            the first preference for each loader. When combined with
            first_loader will return only the first preference(s) of the first
            loader. Preferences are loader specific and documented on the
            loader.
        :return: The list of resolved template names
        """

    @abstractmethod
    def search_templates(
        self, prefix: str, first_loader: bool = False
    ) -> t.Generator[Template, None, None]:
        """
        Resolves a partial template selector into a list of template names from the
        loaders configured on this backend engine.

        :param prefix: The template prefix to search for
        :param first_loader: Search only the first loader
        :return: The list of resolved template names
        """
