"""Rendering for `network power-saving schedules list`.

Response shape is undocumented beyond the envelope (migration plan §4), so
this goes through the generic key/value renderer for every format.
"""

from typing import Any

from ..context import EeroCliContext
from .generic import render_generic


def print_power_saving_schedules(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network power-saving schedules list` (`get_power_saving_schedules`)."""
    render_generic(cli_ctx, data, "eero.network.power_saving.schedules.list/v1")
