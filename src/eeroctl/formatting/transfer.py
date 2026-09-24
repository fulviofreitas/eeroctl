"""Rendering for `network transfer`.

<!-- unverified shape --> Response shape is undocumented beyond the envelope
(no live sample captured yet, migration plan §5.3), so this goes through the
generic key/value renderer for every format.
"""

from typing import Any

from ..context import EeroCliContext
from .generic import render_generic


def print_transfer_stats(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network transfer` (`get_transfer_stats`)."""
    render_generic(cli_ctx, data, "eero.network.transfer/v1")
