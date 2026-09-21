"""Rendering for account-scoped commands.

Response shape is undocumented (migration plan §4, `account premium` row); this
is a thin, schema-carrying wrapper over the generic key/value renderer
(`formatting/generic.py`).
"""

from typing import Any

from ..context import EeroCliContext
from .generic import render_generic


def print_account_premium(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `account premium` (`get_premium_customer`)."""
    render_generic(cli_ctx, data, "eero.account.premium/v1")
