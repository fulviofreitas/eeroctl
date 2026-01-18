"""Update commands for the Eero CLI.

Commands:
- eero eero updates show: Show update status
- eero eero updates check: Check for updates
"""

import asyncio

import click
from eero import EeroClient
from rich.panel import Panel

from ...context import get_cli_context
from ...utils import run_with_client


@click.group(name="updates")
@click.pass_context
def updates_group(ctx: click.Context) -> None:
    """Manage updates.

    \b
    Commands:
      show  - Show update status
      check - Check for updates
    """
    pass


@updates_group.command(name="show")
@click.pass_context
def updates_show(ctx: click.Context) -> None:
    """Show update status."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_updates(client: EeroClient) -> None:
            with cli_ctx.status("Getting update status..."):
                updates = await client.get_updates(cli_ctx.network_id)

            if cli_ctx.is_json_output():
                renderer.render_json(updates, "eero.eero.updates.show/v1")
            else:
                has_update = updates.get("has_update", False)
                target = updates.get("target_firmware", "N/A")

                content = (
                    f"[bold]Update Available:[/bold] {'[green]Yes[/green]' if has_update else '[dim]No[/dim]'}\n"
                    f"[bold]Target Firmware:[/bold] {target}"
                )
                console.print(Panel(content, title="Update Status", border_style="blue"))

        await run_with_client(get_updates)

    asyncio.run(run_cmd())


@updates_group.command(name="check")
@click.pass_context
def updates_check(ctx: click.Context) -> None:
    """Check for available updates."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def check_updates(client: EeroClient) -> None:
            with cli_ctx.status("Checking for updates..."):
                updates = await client.get_updates(cli_ctx.network_id)

            has_update = updates.get("has_update", False)
            if has_update:
                target = updates.get("target_firmware", "N/A")
                console.print(f"[bold green]Update available: {target}[/bold green]")
            else:
                console.print("[dim]No updates available[/dim]")

        await run_with_client(check_updates)

    asyncio.run(run_cmd())
