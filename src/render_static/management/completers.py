"""
Shell completion helpers for :django-admin:`renderstatic` related management commands.
"""

import typing as t

from click import Context, Parameter
from click.shell_completion import CompletionItem

from render_static.engine import StaticTemplateEngine


def complete_selector(
    ctx: Context,
    param: Parameter,
    incomplete: str,
    engine: t.Optional[StaticTemplateEngine] = None,
) -> t.List[CompletionItem]:
    """
    Generate completions for the template selectors and the given or default engines.

    To use this completer with a non-default engine you can bind the engine parameter:

    .. code-block:: python

        from render_static.engine import StaticTemplateEngine
        from render_static.management.completers import complete_selector
        from functools import partial

        custom_engine = StaticTemplateEngine(...)

        Argument(
            help=_("..."),
            shell_complete=partial(complete_selector, engine=custom_engine),
        )

    :param ctx: The Click context.
    :param param: The Click parameter.
    :param incomplete: The incomplete selector string.
    :param engine: An optional StaticTemplateEngine to use for searching.
    :return: A list of CompletionItem objects representing possible completions.
    """
    engine = engine or StaticTemplateEngine()
    present = ctx.params.get(param.name or "") or []
    completions = []
    seen = set()
    for template in engine.search(
        incomplete,
        first_engine=bool(ctx.params.get("first_engine")),
        first_loader=bool(ctx.params.get("first_loader")),
    ):
        tmpl_name = str(template.origin.template_name or "")
        if tmpl_name and tmpl_name not in present and tmpl_name not in seen:
            # the slicing is because we need to denormalize the prefix if the
            # search process normalized the name somehow, because the prefixes
            # must exactly match whats on the command line for most shell completion
            # utilities
            completions.append(
                CompletionItem(f"{incomplete}{tmpl_name[len(incomplete) :]}")
            )
            seen.add(tmpl_name)
    return completions
