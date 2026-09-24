"""Rendering for the `network notifications *` command family.

`show` and `unread` have SDK-documented shapes (`eero/api/notifications.py`),
so `table` output gets a small dedicated view for each; `history`'s shape is
undocumented and always goes through the generic renderer. `json`/`yaml`/
`text`/`list` pass `data` through unchanged for all three.
"""

from typing import Any, Optional

from rich.panel import Panel
from rich.table import Table

from ..context import EeroCliContext
from .base import field_bool, format_bool
from .generic import render_generic, render_generic_with_cursor

_SHOW_SCHEMA = "eero.network.notifications.show/v1"
_UNREAD_SCHEMA = "eero.network.notifications.unread/v1"
_HISTORY_SCHEMA = "eero.network.notifications.history/v1"


def print_notification_settings(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network notifications show` (`get_notification_settings`).

    Documented shape: one boolean per event key (`notifications.py:41-43`).
    """
    if cli_ctx.output_format != "table" or not isinstance(data, dict):
        render_generic(cli_ctx, data, _SHOW_SCHEMA)
        return

    if not data:
        cli_ctx.console.print("[yellow]No notification settings available[/yellow]")
        return

    table = Table(title="Notification Settings")
    table.add_column("Event", style="cyan")
    table.add_column("Enabled", justify="center")
    for event_key in sorted(data):
        table.add_row(event_key, format_bool(bool(data[event_key])))
    cli_ctx.console.print(table)


def print_unread(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network notifications unread` (`has_unread_notifications`).

    Documented shape: `data.has_unread` boolean (`notifications.py:114-115`).
    """
    if cli_ctx.output_format != "table":
        render_generic(cli_ctx, data, _UNREAD_SCHEMA)
        return

    has_unread: Optional[bool] = data.get("has_unread") if isinstance(data, dict) else None
    cli_ctx.console.print(
        Panel(field_bool("Has Unread", has_unread), title="Notifications", border_style="blue")
    )


def print_notification_history(
    cli_ctx: EeroCliContext, data: Any, next_cursor: Optional[str]
) -> None:
    """Render `network notifications history` (`get_notification_history`)."""
    render_generic_with_cursor(
        cli_ctx,
        data,
        _HISTORY_SCHEMA,
        next_cursor=next_cursor,
        cursor_label="next_cursor",
    )
