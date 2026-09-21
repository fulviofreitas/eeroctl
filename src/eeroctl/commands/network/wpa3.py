"""WPA3-per-band read for the Eero CLI.

Command:
- eero network wpa3 show -- get_wpa3_per_band (client.py:2736)

Distinct from the existing `network security wpa3 enable/disable` whole-network
toggle (`set_wpa3`, client.py:2210): this is the newer per-band read/write
family (`set_wpa3_per_band`, client.py:2743) -- phase A ships the read only.
"""

import asyncio
from typing import Optional

import click
from eero import EeroClient

from ...formatting.wpa3 import print_wpa3_per_band
from ...options import apply_options, common_options
from ...transformers.wpa3 import extract_wpa3_per_band
from ...utils import run_with_client


@click.group(name="wpa3")
@click.pass_context
def wpa3_per_band_group(ctx: click.Context) -> None:
    """View WPA3 per-band settings.

    \b
    Commands:
      show - Current per-band WPA3 mode
    """
    pass


@wpa3_per_band_group.command(name="show")
@common_options
@click.pass_context
def wpa3_per_band_show(
    ctx: click.Context, output: Optional[str], network_id: Optional[str]
) -> None:
    """Show the current per-band WPA3 mode."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_wpa3(client: EeroClient) -> None:
            with cli_ctx.status("Getting WPA3 per-band settings..."):
                raw = await client.get_wpa3_per_band(cli_ctx.network_id)
            print_wpa3_per_band(cli_ctx, extract_wpa3_per_band(raw))

        await run_with_client(get_wpa3)

    asyncio.run(run_cmd())
