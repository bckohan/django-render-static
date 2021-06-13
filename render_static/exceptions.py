"""
Define exceptions thrown by `django-render-static`
"""

__all__ = ['URLGenerationFailed', 'ReversalLimitHit', 'InvalidContext']


class URLGenerationFailed(Exception):
    """
    Thrown by `urls_to_js` under any circumstance where URL generation fails for a specific
    fully qualified URL name.
    """


class ReversalLimitHit(Exception):
    """
    Thrown by `urls_to_js` under any circumstance where the configured maximum number of tries has
    been hit when attempting to reverse a URL.
    """


class InvalidContext(Exception):
    """
    Thrown when a configured context is not resolvable to a dictionary type.
    """
