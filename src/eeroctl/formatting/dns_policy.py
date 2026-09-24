"""Rendering for `network dns policy show`.

Only the top-level key names are documented (`data.allowed_list`/
`data.blocked_list` -- migration plan §4); entry shape within each list is not,
so this goes through the generic key/value renderer for every format.
"""

from typing import Any

from ..context import EeroCliContext
from .generic import render_generic


def print_dns_policy(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network dns policy show` (`get_advanced_content_filter`)."""
    render_generic(cli_ctx, data, "eero.network.dns.policy.show/v1")
