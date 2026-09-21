"""Rendering for `network wan multistaticip show`.

<!-- unverified shape --> Response shape is undocumented beyond the envelope
(no live sample captured yet, migration plan §5.3), so the configured case
goes through the generic key/value renderer for every format.
"""

from typing import Any

from ..context import EeroCliContext
from .generic import render_generic

_SCHEMA = "eero.network.wan.multistaticip.show/v1"


def print_multistaticip(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network wan multistaticip show` (`get_multistaticip`)."""
    render_generic(cli_ctx, data, _SCHEMA)


def print_multistaticip_not_configured(cli_ctx: EeroCliContext) -> None:
    """Render the "not configured" case (migration plan §12, Q7).

    Absent-feature reads exit 0 with an explicit "not configured" line and
    `data: null` in structured output; exit 5 stays reserved for a wrong id
    (see `commands/network/wan.py` for the exception-classification logic).
    """
    if cli_ctx.is_structured_output():
        cli_ctx.render_structured(None, _SCHEMA)
        return
    cli_ctx.console.print("[yellow]Multi-static IP is not configured on this network.[/yellow]")
