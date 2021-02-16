django-static-templates
#######################

Use Django's template engine to generate static files at deployment time.

poetry install
poetry run make html
poetry run isort django_static_templates
poetry run pytest
poetry run mypy django_static_templates
poetry run pylint django_static_templates
