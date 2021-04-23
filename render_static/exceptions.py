"""
Define exceptions thrown by `django-render-static`
"""

__all__ = ['URLGenerationFailed']


class URLGenerationFailed(Exception):
    """
    Thrown by `urls_to_js` under any circumstance where URL generation fails for a specific
    fully qualified URL name.
    """
