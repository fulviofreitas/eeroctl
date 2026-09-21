"""Eero connections and support reads for the Eero CLI.

Commands:
- eero eero connections <id> -- get_connections (client.py:661)
- eero eero support <id>     -- get_eero_support (client.py:3114, takes a
  bare serial; 404 on some nodes -> "unavailable", exit 0 per Q7)

Both resolve their `<id>` argument (ID, serial, or name/location) via
`resolve_eero_identifier` (`eero/base.py:27`), the same helper `eero show`/
`eero led`/`eero nightlight` already use -- not reimplemented here.
"""

import asyncio
import sys
from typing import Optional

import click
from eero import EeroClient
from eero.exceptions import EeroNotFoundException

from ...exit_codes import ExitCode
from ...formatting.eero import (
    print_connections,
    print_eero_support,
    print_eero_support_unavailable,
)
from ...options import apply_options, common_options
from ...transformers.eero import extract_connections, extract_eero_support
from ...utils import run_with_client
from .base import eero_group, resolve_eero_identifier


@eero_group.command(name="connections")
@click.argument("eero_identifier")
@common_options
@click.pass_context
def eero_connections(
    ctx: click.Context,
    eero_identifier: str,
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Show connections for a specific Eero node.

    \b
    Arguments:
      EERO_IDENTIFIER  Node ID, serial number, or name/location
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def get_connections(client: EeroClient) -> None:
            with cli_ctx.status(f"Finding Eero '{eero_identifier}'..."):
                resolved_id, eero = await resolve_eero_identifier(
                    client, eero_identifier, cli_ctx.network_id
                )

            if not resolved_id or not eero:
                console.print(f"[red]Eero '{eero_identifier}' not found[/red]")
                console.print("[dim]Try: eero eero list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            with cli_ctx.status("Getting connections..."):
                raw = await client.get_connections(resolved_id, cli_ctx.network_id)
            print_connections(cli_ctx, extract_connections(raw))

        await run_with_client(get_connections)

    asyncio.run(run_cmd())


@eero_group.command(name="support")
@click.argument("eero_identifier")
@common_options
@click.pass_context
def eero_support(
    ctx: click.Context,
    eero_identifier: str,
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Show support data for a specific Eero node.

    Takes the node's serial, resolved via EERO_IDENTIFIER; exits 0 with an
    "unavailable" line (and `data: null` in structured output) on nodes that
    don't have support data, per Q7 in the migration plan.

    \b
    Arguments:
      EERO_IDENTIFIER  Node ID, serial number, or name/location
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def get_support(client: EeroClient) -> None:
            with cli_ctx.status(f"Finding Eero '{eero_identifier}'..."):
                resolved_id, eero = await resolve_eero_identifier(
                    client, eero_identifier, cli_ctx.network_id
                )

            if not resolved_id or not eero:
                console.print(f"[red]Eero '{eero_identifier}' not found[/red]")
                console.print("[dim]Try: eero eero list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            serial = eero.get("serial")
            if not serial:
                console.print(f"[red]Eero '{eero_identifier}' has no serial number[/red]")
                sys.exit(ExitCode.NOT_FOUND)

            with cli_ctx.status("Getting support data..."):
                try:
                    raw = await client.get_eero_support(serial)
                except EeroNotFoundException:
                    print_eero_support_unavailable(cli_ctx)
                    return
            print_eero_support(cli_ctx, extract_eero_support(raw))

        await run_with_client(get_support)

    asyncio.run(run_cmd())
