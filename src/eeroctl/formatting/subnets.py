"""Rendering for `network subnets show` and `network subnets filters show`.

<!-- unverified shape --> Response shapes are undocumented beyond the
envelope (no live sample captured yet, migration plan §5.3), so both go
through the generic key/value renderer for every format.
"""

from typing import Any

from ..context import EeroCliContext
from .generic import render_generic


def print_subnets_config(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network subnets show` (`get_subnets_config`)."""
    render_generic(cli_ctx, data, "eero.network.subnets.show/v1")


def print_subnet_content_filters(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network subnets filters show` (`get_subnet_content_filters`)."""
    render_generic(cli_ctx, data, "eero.network.subnets.filters.show/v1")
