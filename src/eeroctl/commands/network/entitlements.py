"""Entitlements and device-capability reads for the Eero CLI.

Commands:
- eero network entitlements show          -- get_entitlement_features (client.py:2292)
- eero network entitlements upsell        -- get_upsell_features (client.py:2300)
- eero network entitlements capabilities  -- get_model_capabilities (client.py:2305)

`network entitlements show` replaces the dead `is_premium` call
`troubleshoot doctor` used to reach for (eero-api 8.0.1 migration plan §4,
`network entitlements show` row); `troubleshoot doctor`'s own premium check is
rewired onto `get_entitlement_features` too (see `commands/troubleshoot.py`).
All three are plain, live-verified GETs -- no confirmation, no writes.
"""

import asyncio
from typing import Optional

import click
from eero import EeroClient

from ...context import ensure_cli_context
from ...formatting.entitlements import (
    print_entitlements_capabilities,
    print_entitlements_show,
    print_entitlements_upsell,
)
from ...options import apply_options, common_options
from ...transformers.entitlements import extract_entitlements
from ...utils import run_with_client


@click.group(name="entitlements")
@click.pass_context
def entitlements_group(ctx: click.Context) -> None:
    """View premium entitlements and per-model device capabilities.

    \b
    Commands:
      show          - Premium features entitled to this network
      upsell        - Features available via upgrade
      capabilities  - Per-model feature capabilities

    \b
    Examples:
      eero network entitlements show
      eero network entitlements upsell --output json
    """
    ensure_cli_context(ctx)


@entitlements_group.command(name="show")
@common_options
@click.pass_context
def entitlements_show(ctx: click.Context, output: Optional[str], network_id: Optional[str]) -> None:
    """Show premium features entitled to this network."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_entitlements(client: EeroClient) -> None:
            with cli_ctx.status("Getting entitlements..."):
                raw = await client.get_entitlement_features(cli_ctx.network_id)
            print_entitlements_show(cli_ctx, extract_entitlements(raw))

        await run_with_client(get_entitlements)

    asyncio.run(run_cmd())


@entitlements_group.command(name="upsell")
@common_options
@click.pass_context
def entitlements_upsell(
    ctx: click.Context, output: Optional[str], network_id: Optional[str]
) -> None:
    """Show features available via upgrade."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_upsell(client: EeroClient) -> None:
            with cli_ctx.status("Getting upsell features..."):
                raw = await client.get_upsell_features(cli_ctx.network_id)
            print_entitlements_upsell(cli_ctx, extract_entitlements(raw))

        await run_with_client(get_upsell)

    asyncio.run(run_cmd())


@entitlements_group.command(name="capabilities")
@common_options
@click.pass_context
def entitlements_capabilities(
    ctx: click.Context, output: Optional[str], network_id: Optional[str]
) -> None:
    """Show per-model device feature capabilities."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_capabilities(client: EeroClient) -> None:
            with cli_ctx.status("Getting model capabilities..."):
                raw = await client.get_model_capabilities(cli_ctx.network_id)
            print_entitlements_capabilities(cli_ctx, extract_entitlements(raw))

        await run_with_client(get_capabilities)

    asyncio.run(run_cmd())
