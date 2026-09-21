"""Rendering for `network events`, `network scan`, and `network channels`.

Response shapes are undocumented (migration plan §4); each function here is a
thin, schema-carrying wrapper over the generic key/value renderer
(`formatting/generic.py`) until a live sample justifies a dedicated table
(§5.3 of the migration plan).
"""

from typing import Any, Optional

from ..context import EeroCliContext
from .generic import render_generic, render_generic_with_cursor


def print_events(cli_ctx: EeroCliContext, data: Any, next_cursor: Optional[str]) -> None:
    """Render `network events` (`get_app_events`), with a pagination cursor."""
    render_generic_with_cursor(
        cli_ctx,
        data,
        "eero.network.events/v1",
        next_cursor=next_cursor,
        cursor_label="next_cursor",
    )


def print_scan(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network scan` (`get_network_scan`)."""
    render_generic(cli_ctx, data, "eero.network.scan/v1")


def print_channels(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network channels` (`get_channel_utilization`)."""
    render_generic(cli_ctx, data, "eero.network.channels/v1")
