from django.template import Origin

__all__ = ['AppOrigin']


class AppOrigin(Origin):

    def __init__(self, *args, **kwargs):
        self.app = kwargs.pop('app', None)
        super().__init__(*args, **kwargs)

    def __eq__(self, other):
        return super().__eq__(other) and self.app == getattr(other, 'app', None)

