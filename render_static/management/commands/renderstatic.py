"""
Generate documents from templates and write them to disk at either
pre-configured locations or in their associated Django app's static directory
if residing within an app. This command should be run during the deployment
phase and always before collectstatic is run.

This command accepts a list of template names to render. If no names are
specified all templates as specified in ``STATIC_TEMPLATES`` will be rendered.
A template name supplied as an argument does not need to be specified in
``STATIC_TEMPLATES`` for it to be found and rendered. Such templates will be
given the global context as specified in ``STATIC_TEMPLATES``.
"""

import sys
import typing as t
from pathlib import Path

from click import Context, Parameter
from click.shell_completion import CompletionItem
from django.core.management.base import CommandError
from django.utils.translation import gettext as _
from django_typer.completers import (
    chain,
    complete_directory,
    complete_import_path,
    complete_path,
)
from django_typer.management import TyperCommand
from typer import Argument, Option

from render_static.engine import StaticTemplateEngine

if sys.version_info >= (3, 9):
    from typing import Annotated
else:
    from typing_extensions import Annotated


def complete_selector(
    ctx: Context, param: Parameter, incomplete: str
) -> t.List[CompletionItem]:
    """
    Generate completions for the template selectors.
    """
    engine = StaticTemplateEngine()
    present = ctx.params.get(param.name or "") or []
    completions = []
    for template in engine.search(
        incomplete,
        first_engine=bool(ctx.params.get("first_engine")),
        first_loader=bool(ctx.params.get("first_loader")),
    ):
        tmpl_name = str(template.origin.template_name or "")
        if tmpl_name and tmpl_name not in present and tmpl_name not in completions:
            # the slicing is because we need to denormalize the prefix if the
            # search process normalized the name somehow, because the prefixes
            # must exactly match whats on the command line for most shell completion
            # utilities
            completions.append(
                CompletionItem(f"{incomplete}{tmpl_name[len(incomplete):]}")
            )
    return completions


class Command(TyperCommand):
    help = _("Generate static files from static templates.")

    def handle(
        self,
        selectors: Annotated[
            t.Optional[t.List[str]],
            Argument(
                help=_(
                    "Template name selectors for the templates to render. "
                    "Selectors are like template names, but can be glob patterns,"
                    " or patterns understood by specifically configured loaders. "
                    "Template selectors can resolve to more than one valid "
                    "template name. Default: All template selectors specified in "
                    "settings.",
                ),
                shell_complete=complete_selector,
            ),
        ] = None,
        context: Annotated[
            t.Optional[str],
            Option(
                "--context",
                "-c",
                help=_(
                    "An alternate context to use when rendering the selected "
                    "templates. This will override any conflicting context "
                    "parameters in the context(s) specified in settings. Must be "
                    "a path to any of the following file types: "
                    "python files, json files, yaml files, or pickled python "
                    "dictionaries.",
                ),
                shell_complete=chain(complete_path, complete_import_path),
            ),
        ] = None,
        destination: Annotated[
            t.Optional[Path],
            Option(
                "--destination",
                "-d",
                help=_(
                    "The location to render templates to. This will override the "
                    "destination specified in settings for selected template, if "
                    "one exists. If no destination is specified in settings or "
                    "here, the default destination is settings.STATIC_ROOT."
                ),
                shell_complete=complete_directory,
            ),
        ] = None,
        first_engine: Annotated[
            bool,
            Option(
                "--first-engine",
                help=_(
                    "Render only the set of templates that match the selector "
                    "that are found by the highest priority rendering engine. By "
                    "default (False) any templates that match the selector from "
                    "any engine will be rendered."
                ),
            ),
        ] = False,
        first_loader: Annotated[
            bool,
            Option(
                "--first-loader",
                help=_(
                    "Render only the set of templates found by the first loader "
                    "that match any part of the selector. By default (False) any "
                    "template name that matches the selector from any loader will "
                    "be rendered."
                ),
            ),
        ] = False,
        first_preference: Annotated[
            bool,
            Option(
                "--first-preference",
                help=_(
                    "Render only the templates that match the first preference "
                    "for each loader. When combined with --first-loader render "
                    "only the first preference(s) of the first loader. "
                    "Preferences are loader specific and documented on the "
                    "loader. For instance, for the App directories loader "
                    "preference is defined as app precedence in settings - so if "
                    "any templates match the selector for the highest priority "
                    "app, only those templates would be rendered."
                ),
            ),
        ] = False,
        exclude: Annotated[
            t.List[Path],
            Option(
                "--exclude",
                "-e",
                help=_(
                    "Exclude these files from rendering, or any files at or below "
                    "this directory."
                ),
                shell_complete=complete_path,
            ),
        ] = [],
        no_render_contents: Annotated[
            bool,
            Option(
                "--no-render-contents",
                help=_(
                    "Do not render the contents of the files. If paths are "
                    "templates, destinations will still be rendered."
                ),
            ),
        ] = False,
    ):
        engine = StaticTemplateEngine()

        if not selectors:
            selectors = list({selector for selector, _ in engine.templates})

        if not selectors:
            self.stdout.write(
                self.style.WARNING(_("No templates selected for generation."))
            )
            return

        try:
            for render in engine.render_each(
                *selectors,
                dest=destination,
                context=context,
                first_engine=first_engine,
                first_loader=first_loader,
                first_preference=first_preference,
                exclude=exclude,
                render_contents=not no_render_contents,
            ):
                self.stdout.write(
                    self.style.SUCCESS(_("Rendered {render}.").format(render=render))
                )
        except Exception as exp:
            raise CommandError(
                _("Error rendering template to disk: {exp}").format(exp=exp)
            ) from exp
