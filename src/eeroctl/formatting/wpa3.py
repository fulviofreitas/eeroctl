"""Rendering for `network wpa3 show` and `network security fast-transition show`.

Both response shapes are undocumented beyond the corresponding setters' kwarg
names, so both go through the generic key/value renderer for every format.
"""

from typing import Any

from ..context import EeroCliContext
from .generic import render_generic


def print_wpa3_per_band(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network wpa3 show` (`get_wpa3_per_band`)."""
    render_generic(cli_ctx, data, "eero.network.wpa3.show/v1")


def print_fast_transition(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network security fast-transition show` (`get_fast_transition`)."""
    render_generic(cli_ctx, data, "eero.network.security.fast_transition.show/v1")
