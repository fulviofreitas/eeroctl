"""OUI-check read for the Eero CLI.

Command:
- eero network ouicheck <eero> -- get_ouicheck(network_id=None, *, serial,
  version) (client.py:1805, both serial/version required keyword-only)

Takes an eero identifier (ID, serial, or name/location), resolved via
`resolve_eero_identifier` (`eero/base.py:27`) -- the same helper `eero
show`/`eero connections`/`eero support` use, not reimplemented here -- and
forwards the resolved eero's serial/os_version as `serial=`/`version=`.
"""

import asyncio
import sys
from typing import Optional

import click
from eero import EeroClient

from ...exit_codes import ExitCode
from ...formatting.ouicheck import print_ouicheck
from ...options import apply_options, common_options
from ...transformers.ouicheck import extract_ouicheck
from ...utils import run_with_client
from ..eero.base import resolve_eero_identifier


@click.command(name="ouicheck")
@click.argument("eero_identifier")
@common_options
@click.pass_context
def network_ouicheck(
    ctx: click.Context,
    eero_identifier: str,
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Run an OUI check for a specific Eero node.

    \b
    Arguments:
      EERO_IDENTIFIER  Node ID, serial number, or name/location
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def get_ouicheck(client: EeroClient) -> None:
            with cli_ctx.status(f"Finding Eero '{eero_identifier}'..."):
                resolved_id, eero = await resolve_eero_identifier(
                    client, eero_identifier, cli_ctx.network_id
                )

            if not resolved_id or not eero:
                console.print(f"[red]Eero '{eero_identifier}' not found[/red]")
                console.print("[dim]Try: eero eero list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            serial = eero.get("serial")
            version = eero.get("os_version")
            if not serial or not version:
                console.print(
                    f"[red]Eero '{eero_identifier}' is missing serial/version data "
                    "needed for an OUI check[/red]"
                )
                sys.exit(ExitCode.NOT_FOUND)

            with cli_ctx.status("Running OUI check..."):
                raw = await client.get_ouicheck(cli_ctx.network_id, serial=serial, version=version)
            print_ouicheck(cli_ctx, extract_ouicheck(raw))

        await run_with_client(get_ouicheck)

    asyncio.run(run_cmd())
