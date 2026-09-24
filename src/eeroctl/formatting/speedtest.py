"""Rendering for `network speedtest history`.

Reuses the generic renderer's list-of-dicts column auto-selection for
`table`/`list`; `json`/`yaml`/`text` pass the full history list through.
`network speedtest show` (`speedtest.py`) reads through the same
`transformers.speedtest` accessors but keeps its existing dedicated panel.
"""

from typing import Any

from ..context import EeroCliContext
from .generic import render_generic


def print_speedtest_history(cli_ctx: EeroCliContext, history: Any) -> None:
    """Render `network speedtest history` (`get_speed_tests`)."""
    render_generic(cli_ctx, history, "eero.network.speedtest.history/v1")
