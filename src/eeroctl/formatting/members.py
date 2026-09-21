"""Rendering for `network members list|invites`.

`list`'s shape is documented (`data.members`, a list -- see
`transformers/members.py`), so `table`/`list` output renders the flattened
member list (letting the generic renderer's list-of-dicts column auto-selection
do the work); `json`/`yaml`/`text` still pass the full raw `data` through
unchanged. `invites`'s shape is undocumented, so it always goes through the
generic renderer on the raw `data`.
"""

from typing import Any

from ..context import EeroCliContext
from ..transformers.members import extract_members_list
from .generic import render_generic

_LIST_SCHEMA = "eero.network.members.list/v1"
_INVITES_SCHEMA = "eero.network.members.invites/v1"


def print_members(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network members list` (`get_members`)."""
    if cli_ctx.is_structured_output():
        cli_ctx.render_structured(data, _LIST_SCHEMA)
        return
    render_generic(cli_ctx, extract_members_list(data), _LIST_SCHEMA)


def print_invites(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network members invites` (`get_invites`)."""
    render_generic(cli_ctx, data, _INVITES_SCHEMA)
