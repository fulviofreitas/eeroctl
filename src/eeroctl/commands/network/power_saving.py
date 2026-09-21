"""Power-saving schedule reads for the Eero CLI.

Commands:
- eero network power-saving schedules list -- get_power_saving_schedules
  (client.py:2830, verified)

Phase A ships the read only; phase C adds `schedules create/update/delete`
(`create_power_saving_schedule`/`update_power_saving_schedule`/
`delete_power_saving_schedule`, client.py:2837/2858/2881) and the
`set_power_saving` toggle.
"""

import asyncio
from typing import Optional

import click
from eero import EeroClient

from ...formatting.power_saving import print_power_saving_schedules
from ...options import apply_options, common_options
from ...transformers.power_saving import extract_power_saving_schedules
from ...utils import run_with_client


@click.group(name="power-saving")
@click.pass_context
def power_saving_group(ctx: click.Context) -> None:
    """Manage power-saving settings.

    \b
    Commands:
      schedules - Power-saving schedules
    """
    pass


@power_saving_group.group(name="schedules")
@click.pass_context
def power_saving_schedules_group(ctx: click.Context) -> None:
    """Manage power-saving schedules.

    \b
    Commands:
      list - List power-saving schedules
    """
    pass


@power_saving_schedules_group.command(name="list")
@common_options
@click.pass_context
def power_saving_schedules_list(
    ctx: click.Context, output: Optional[str], network_id: Optional[str]
) -> None:
    """List power-saving schedules."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_schedules(client: EeroClient) -> None:
            with cli_ctx.status("Getting power-saving schedules..."):
                raw = await client.get_power_saving_schedules(cli_ctx.network_id)
            print_power_saving_schedules(cli_ctx, extract_power_saving_schedules(raw))

        await run_with_client(get_schedules)

    asyncio.run(run_cmd())
