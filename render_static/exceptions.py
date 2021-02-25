"""
Define exceptions thrown by `django-render-static`
"""

__all__ = ['PlaceholderNotFound', 'URLGenerationFailed']


class PlaceholderNotFound(Exception):
    """
    Thrown by `urls_to_js` when a reversible URL requires placeholders in order ot be reversed
    but none are registered.
    """


class URLGenerationFailed(Exception):
    """
    Thrown by `urls_to_js` under any circumstance where URL generation fails for a specific
    fully qualified URL name.
    """
