"""Subnet reads for the Eero CLI.

Commands:
- eero network subnets show                    -- get_subnets_config
  (client.py:2991)
- eero network subnets filters show <subnet-id> -- get_subnet_content_filters
  (client.py:3023)

Both are plain GETs; the subnet id for `filters show` names a nested
sub-resource -- passed to the SDK verbatim, which validates it (no
client-side link parsing needed here). Phase C adds `set_subnets_config`,
`delete_subnet`, and `set_subnet_content_filters`.
"""

import asyncio
from typing import Optional

import click
from eero import EeroClient

from ...formatting.subnets import print_subnet_content_filters, print_subnets_config
from ...options import apply_options, common_options
from ...transformers.subnets import extract_subnet_content_filters, extract_subnets_config
from ...utils import run_with_client


@click.group(name="subnets")
@click.pass_context
def subnets_group(ctx: click.Context) -> None:
    """View subnet configuration and content filters.

    \b
    Commands:
      show    - Subnet configuration
      filters - Per-subnet content filters
    """
    pass


@subnets_group.command(name="show")
@common_options
@click.pass_context
def subnets_show(ctx: click.Context, output: Optional[str], network_id: Optional[str]) -> None:
    """Show subnet configuration."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_subnets(client: EeroClient) -> None:
            with cli_ctx.status("Getting subnet configuration..."):
                raw = await client.get_subnets_config(cli_ctx.network_id)
            print_subnets_config(cli_ctx, extract_subnets_config(raw))

        await run_with_client(get_subnets)

    asyncio.run(run_cmd())


@subnets_group.group(name="filters")
@click.pass_context
def subnet_filters_group(ctx: click.Context) -> None:
    """View per-subnet content filters.

    \b
    Commands:
      show <subnet-id> - Content filters for one subnet
    """
    pass


@subnet_filters_group.command(name="show")
@click.argument("subnet_id")
@common_options
@click.pass_context
def subnet_filters_show(
    ctx: click.Context, subnet_id: str, output: Optional[str], network_id: Optional[str]
) -> None:
    """Show content filters for one subnet.

    \b
    Arguments:
      SUBNET_ID  The subnet's id, as returned by 'network subnets show'
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_filters(client: EeroClient) -> None:
            with cli_ctx.status(f"Getting content filters for subnet {subnet_id}..."):
                raw = await client.get_subnet_content_filters(subnet_id, cli_ctx.network_id)
            print_subnet_content_filters(cli_ctx, extract_subnet_content_filters(raw))

        await run_with_client(get_filters)

    asyncio.run(run_cmd())
