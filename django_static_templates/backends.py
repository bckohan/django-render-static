from django.template.backends.django import DjangoTemplates
from django.template.backends.jinja2 import Jinja2


__all__ = ['StaticDjangoTemplates', 'StaticJinja2Templates']


class StaticDjangoTemplates(DjangoTemplates):

    app_dirname = 'static_templates'

    def __init__(self, params):
        params = params.copy()
        options = params.pop('OPTIONS').copy()
        loaders = options.get('loaders', None)
        self.app_dirname = options.pop('app_dir', self.app_dirname)
        if loaders is None:
            loaders = ['django_static_templates.loaders.StaticFilesystemLoader']
            if params.get('APP_DIRS', False):
                loaders += ['django.template.loaders.StaticAppDirectoriesLoader']
            options['loaders'] = loaders
        params['OPTIONS'] = options
        super().__init__(params)


class StaticJinja2Templates(Jinja2):

    app_dirname = 'static_jinja2'

    def __init__(self, params):
        params = params.copy()
        options = params.pop('OPTIONS').copy()
        self.app_dirname = options.pop('app_dir', self.app_dirname)
        params['OPTIONS'] = options
        super().__init__(params)

