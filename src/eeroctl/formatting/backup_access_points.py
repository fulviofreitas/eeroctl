"""Rendering for `network backup access-points list|discover`.

<!-- unverified shape --> Response shapes are undocumented beyond the
envelope (no live sample captured yet, migration plan §5.3), so both go
through the generic key/value renderer for every format.
"""

from typing import Any

from ..context import EeroCliContext
from .generic import render_generic


def print_backup_access_points(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network backup access-points list` (`list_backup_access_points`)."""
    render_generic(cli_ctx, data, "eero.network.backup.access_points.list/v1")


def print_backup_ssid_discovery(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network backup access-points discover` (`discover_backup_ssids`)."""
    render_generic(cli_ctx, data, "eero.network.backup.access_points.discover/v1")
