"""
Helper classes for augmenting loader behavior.
"""
from glob import glob
from os.path import relpath
from typing import Generator, List

from django.core.exceptions import SuspiciousFileOperation
from django.template.loaders.filesystem import safe_join

__all__ = ['BatchLoaderMixin']


class BatchLoaderMixin:
    """
    A mixin for Jinja2 loaders that enables glob pattern selectors to load batches of templates
    from the file system.

    Yields batches of template names in order of preference, where preference is defined by the
    order directories are listed in.
    """

    def get_dirs(self) -> List[str]:
        """
        Return a priority ordered list of directories on the search path of this loader.
        """
        raise NotImplementedError(
            f'{self.__class__.__name__} must implement get_dirs!'
        )  # pragma: no cover

    def select_templates(self, selector: str) -> Generator[List[str], None, None]:
        """
        Yields template names matching the selector pattern.

        :param selector: A glob pattern, or file name
        """
        for template_dir in self.get_dirs():
            try:
                pattern = safe_join(template_dir, selector)
            except SuspiciousFileOperation:
                # The joined path was located outside of this template_dir
                # (it might be inside another one, so this isn't fatal).
                continue

            yield [relpath(file, template_dir) for file in glob(pattern, recursive=True)]
