"""Rendering for `network members list|invites`.

`list`'s shape is documented (`data.members`, a list -- see
`transformers/members.py`). `table` gets a dedicated name/email/role/status
view (email shown deliberately: the command's whole purpose is showing who
has access); `list`/`text` go through the generic renderer, which redacts
sensitive keys (see `formatting/generic.py`); `json`/`yaml` pass the full raw
`data` through unchanged. `invites`'s shape is undocumented, so it always
goes through the generic renderer on the raw `data`.

Security note: this used to gate on `EeroCliContext.is_structured_output()`,
which is `True` for `json`/`yaml`/`text` alike -- so `--output text` leaked
the raw, unredacted payload (email, phone, an unredacted `invite_token`, ...).
Only `json`/`yaml` may see the raw payload now.
"""

from typing import Any

from rich.table import Table

from ..context import EeroCliContext
from ..transformers.members import extract_members_list
from .generic import render_generic

_LIST_SCHEMA = "eero.network.members.list/v1"
_INVITES_SCHEMA = "eero.network.members.invites/v1"


def print_members(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network members list` (`get_members`)."""
    if cli_ctx.is_json_output() or cli_ctx.is_yaml_output():
        cli_ctx.render_structured(data, _LIST_SCHEMA)
        return

    members = extract_members_list(data)

    if cli_ctx.output_format == "table":
        if not members:
            cli_ctx.console.print("[yellow]No members found[/yellow]")
            return
        table = Table(title="Network Members")
        table.add_column("Name", style="cyan")
        table.add_column("Email")
        table.add_column("Role")
        table.add_column("Status")
        for member in members:
            table.add_row(
                str(member.get("name") or member.get("display_name") or "-"),
                str(member.get("email") or "-"),
                str(member.get("role") or "-"),
                str(member.get("status") or "-"),
            )
        cli_ctx.console.print(table)
        return

    # `list`/`text`: through the generic renderer, which redacts sensitive
    # keys (email included) -- deliberately more conservative than the
    # curated `table` view above.
    render_generic(cli_ctx, members, _LIST_SCHEMA)


def print_invites(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network members invites` (`get_invites`)."""
    render_generic(cli_ctx, data, _INVITES_SCHEMA)
