"""Rendering for `network permissions`.

Unlike most phase-A families, the SDK documents this shape (`data.role` +
`data.permissions`, a per-capability mapping -- `eero/api/permissions.py:38-41`),
so `table` output gets a small dedicated view instead of the fully generic
renderer; `json`/`yaml`/`text`/`list` still pass the raw `data` through
unchanged via the generic renderer.
"""

from typing import Any

from rich.panel import Panel
from rich.table import Table

from ..context import EeroCliContext
from ..transformers.permissions import extract_capability_map, extract_role
from .base import field, format_bool
from .generic import render_generic

_SCHEMA = "eero.network.permissions/v1"


def print_permissions(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network permissions` (`get_permissions`)."""
    if cli_ctx.output_format != "table" or not isinstance(data, dict):
        render_generic(cli_ctx, data, _SCHEMA)
        return

    console = cli_ctx.console
    role = extract_role(data)
    capabilities = extract_capability_map(data)

    console.print(Panel(field("Role", role or "Unknown"), title="Permissions", border_style="blue"))

    if capabilities:
        table = Table(title="Capabilities")
        table.add_column("Capability", style="cyan")
        table.add_column("Allowed", justify="center")
        for capability in sorted(capabilities):
            table.add_row(capability, format_bool(bool(capabilities[capability])))
        console.print(table)
    else:
        console.print("[yellow]No capability data available[/yellow]")
