"""Account-scoped commands for the Eero CLI.

Commands:
- eero account premium -- get_premium_customer (client.py:2310)

`get_premium_customer` is the only phase-A facade method that takes no
`network_id` at all (eero-api 8.0.1 migration plan §4, `account premium` row:
"account-scoped"), so this command has no `--network-id` option.
"""

import asyncio
from typing import Optional

import click
from eero import EeroClient

from ..context import ensure_cli_context
from ..formatting.account import print_account_premium
from ..options import apply_options, output_option
from ..transformers.account import extract_premium_customer
from ..utils import run_with_client


@click.group(name="account")
@click.pass_context
def account_group(ctx: click.Context) -> None:
    """Account-scoped commands (not tied to a specific network).

    \b
    Commands:
      premium - Account-wide premium/subscription status

    \b
    Examples:
      eero account premium
    """
    ensure_cli_context(ctx)


@account_group.command(name="premium")
@output_option
@click.pass_context
def account_premium(ctx: click.Context, output: Optional[str]) -> None:
    """Show account-wide premium/subscription status."""
    cli_ctx = apply_options(ctx, output=output)

    async def run_cmd() -> None:
        async def get_premium(client: EeroClient) -> None:
            with cli_ctx.status("Getting account premium status..."):
                raw = await client.get_premium_customer()
            print_account_premium(cli_ctx, extract_premium_customer(raw))

        await run_with_client(get_premium)

    asyncio.run(run_cmd())
