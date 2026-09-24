"""PPPoE commands for the Eero CLI.

Commands:
- eero eero pppoe set: Configure PPPoE credentials
"""

import asyncio
import sys
from typing import Optional

import click
from eero import EeroClient

from ...context import get_cli_context
from ...exit_codes import ExitCode
from ...safety import SafetyContext, SafetyError, get_write_spec, require_write_confirmation
from ...utils import run_with_client
from .base import resolve_eero_identifier


@click.group(name="pppoe")
@click.pass_context
def pppoe_group(ctx: click.Context) -> None:
    """Manage PPPoE configuration.

    \b
    Commands:
      set - Configure PPPoE username/password
    """
    pass


@pppoe_group.command(name="set")
@click.argument("eero_identifier")
@click.option("--username", required=True, help="PPPoE username")
@click.option("--password", help="PPPoE password. Omitted, you are prompted (input hidden).")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def pppoe_set(
    ctx: click.Context,
    eero_identifier: str,
    username: str,
    password: Optional[str],
    force: bool,
) -> None:
    """Configure PPPoE credentials for an eero.

    \b
    Arguments:
      EERO_IDENTIFIER  Node ID, serial number, or name/location

    \b
    Options:
      --username TEXT  PPPoE username (required)
      --password TEXT  PPPoE password. Omitted, prompts for it (input
                        hidden, confirmed) instead.
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.err_console
    effective_force = force or cli_ctx.force

    # --non-interactive without --password can never be satisfied (no prompt
    # will run), so this guard stays first, before any confirmation.
    if password is None and cli_ctx.non_interactive:
        console.print("[red]--password is required when --non-interactive is set[/red]")
        sys.exit(ExitCode.USAGE_ERROR)

    spec = get_write_spec("eero pppoe set")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target=eero_identifier,
            ctx=SafetyContext(
                force=effective_force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
            console=cli_ctx.err_console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    # Only ask for the password once the write is actually going to happen.
    if password is None:
        password = click.prompt(
            "PPPoE password",
            hide_input=True,
            confirmation_prompt=True,
            err=True,
        )

    async def run_cmd() -> None:
        async def set_pppoe(client: EeroClient) -> None:
            with cli_ctx.status(f"Finding Eero '{eero_identifier}'..."):
                resolved_id, eero = await resolve_eero_identifier(
                    client, eero_identifier, cli_ctx.network_id
                )

            if not resolved_id or not eero:
                console.print(f"[red]Eero '{eero_identifier}' not found[/red]")
                console.print("[dim]Try: eero eero list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            eero_id_str = str(resolved_id)
            with cli_ctx.status("Configuring PPPoE..."):
                # `set_pppoe` has no `network_id` parameter (client.py:2726).
                result = await client.set_pppoe(eero_id_str, username=username, password=password)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print("[bold green]PPPoE configured.[/bold green]")
            else:
                console.print("[red]Failed to configure PPPoE[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_pppoe)

    asyncio.run(run_cmd())
