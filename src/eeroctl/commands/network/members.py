"""Members and invites reads for the Eero CLI.

Commands:
- eero network members list    -- get_members (client.py:2572, verified)
- eero network members invites -- get_invites (client.py:2579, unverified read;
  403 seen live -- migration plan §4, `network members invites` row)
"""

import asyncio
from typing import Optional

import click
from eero import EeroClient
from eero.exceptions import EeroAccessDeniedException, EeroAPIException

from ...context import EeroCliContext, ensure_cli_context
from ...exit_codes import ExitCode
from ...formatting.members import print_invites, print_members
from ...options import apply_options, common_options
from ...transformers.members import extract_invites, extract_members
from ...utils import run_with_client


@click.group(name="members")
@click.pass_context
def members_group(ctx: click.Context) -> None:
    """View network members and pending invites.

    \b
    Commands:
      list    - Network members
      invites - Pending invites (not permitted for every account)
    """
    ensure_cli_context(ctx)


@members_group.command(name="list")
@common_options
@click.pass_context
def members_list(ctx: click.Context, output: Optional[str], network_id: Optional[str]) -> None:
    """List the network's members."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_members(client: EeroClient) -> None:
            with cli_ctx.status("Getting members..."):
                raw = await client.get_members(cli_ctx.network_id)
            print_members(cli_ctx, extract_members(raw))

        await run_with_client(get_members)

    asyncio.run(run_cmd())


@members_group.command(name="invites")
@common_options
@click.pass_context
def members_invites(ctx: click.Context, output: Optional[str], network_id: Optional[str]) -> None:
    """List the network's pending invites.

    This is an unverified read -- some accounts see a 403 here even when
    they can list members. That case is reported as a friendly message
    rather than a generic "Permission denied" error.
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_invites(client: EeroClient) -> None:
            with cli_ctx.status("Getting invites..."):
                try:
                    raw = await client.get_invites(cli_ctx.network_id)
                except EeroAccessDeniedException:
                    _report_not_permitted(cli_ctx)
                except EeroAPIException as e:
                    # commit 6 maps EeroAccessDeniedException directly; until
                    # then a 403 surfaces as the generic EeroAPIException.
                    if e.status_code == 403:
                        _report_not_permitted(cli_ctx)
                    raise
                else:
                    print_invites(cli_ctx, extract_invites(raw))

        await run_with_client(get_invites)

    asyncio.run(run_cmd())


def _report_not_permitted(cli_ctx: EeroCliContext) -> None:
    """Report a 403 on `members invites` as a friendly message and exit 4."""
    if cli_ctx.is_structured_output():
        cli_ctx.render_structured(
            {"error": "not_permitted", "message": "Not permitted for this account."},
            "eero.network.members.invites/v1",
        )
    else:
        cli_ctx.console.print(
            "[yellow]Not permitted for this account.[/yellow] "
            "[dim]Some accounts cannot view pending invites even though they "
            "can list members.[/dim]"
        )
    raise SystemExit(ExitCode.FORBIDDEN)
