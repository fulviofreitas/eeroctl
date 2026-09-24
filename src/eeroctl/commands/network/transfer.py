"""Transfer-stats read for the Eero CLI.

Command:
- eero network transfer [--device] -- get_transfer_stats(network_id=None,
  device_id=None) (client.py:1569)
"""

import asyncio
from typing import Optional

import click
from eero import EeroClient

from ...formatting.transfer import print_transfer_stats
from ...options import apply_options, common_options
from ...transformers.transfer import extract_transfer_stats
from ...utils import run_with_client


@click.command(name="transfer")
@click.option(
    "--device",
    "device_id",
    default=None,
    help="Restrict to one device (bare device id).",
)
@common_options
@click.pass_context
def network_transfer(
    ctx: click.Context,
    device_id: Optional[str],
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Show network (or one device's) transfer statistics."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_transfer(client: EeroClient) -> None:
            with cli_ctx.status("Getting transfer statistics..."):
                raw = await client.get_transfer_stats(cli_ctx.network_id, device_id)
            print_transfer_stats(cli_ctx, extract_transfer_stats(raw))

        await run_with_client(get_transfer)

    asyncio.run(run_cmd())
