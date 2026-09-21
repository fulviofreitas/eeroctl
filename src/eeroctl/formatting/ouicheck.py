"""Rendering for `network ouicheck <eero>`.

<!-- unverified shape --> Response shape is undocumented beyond the envelope
(no live sample captured yet, migration plan §5.3), so this goes through the
generic key/value renderer for every format.
"""

from typing import Any

from ..context import EeroCliContext
from .generic import render_generic


def print_ouicheck(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network ouicheck <eero>` (`get_ouicheck`)."""
    render_generic(cli_ctx, data, "eero.network.ouicheck/v1")
