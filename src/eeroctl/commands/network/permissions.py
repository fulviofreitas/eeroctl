"""Permissions read for the Eero CLI.

Command:
- eero network permissions -- get_permissions (client.py:2369)

Plain, live-verified GET -- no confirmation, no writes. Also usable as a
pre-flight hint for 403s from other commands (migration plan §4, `network
permissions` row).
"""

import asyncio
from typing import Optional

import click
from eero import EeroClient

from ...formatting.permissions import print_permissions
from ...options import apply_options, common_options
from ...transformers.permissions import extract_permissions
from ...utils import run_with_client


@click.command(name="permissions")
@common_options
@click.pass_context
def network_permissions(
    ctx: click.Context, output: Optional[str], network_id: Optional[str]
) -> None:
    """Show the caller's role and per-capability permissions on this network."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_permissions(client: EeroClient) -> None:
            with cli_ctx.status("Getting permissions..."):
                raw = await client.get_permissions(cli_ctx.network_id)
            print_permissions(cli_ctx, extract_permissions(raw))

        await run_with_client(get_permissions)

    asyncio.run(run_cmd())
