"""Backup network commands for the Eero CLI (Eero Plus feature).

Commands:
- eero network backup show: Show backup network settings
- eero network backup enable: Enable backup network
- eero network backup disable: Disable backup network
- eero network backup status: Show current backup status
"""

import asyncio
import sys

import click
from eero import EeroClient
from rich.panel import Panel

from ...context import EeroCliContext, get_cli_context
from ...errors import is_premium_error
from ...exit_codes import ExitCode
from ...safety import OperationRisk, SafetyError, confirm_or_fail
from ...utils import run_with_client


@click.group(name="backup")
@click.pass_context
def backup_group(ctx: click.Context) -> None:
    """Manage backup network (Eero Plus feature).

    \b
    Commands:
      show    - Show backup network settings
      enable  - Enable backup network
      disable - Disable backup network
      status  - Show current backup status
    """
    pass


@backup_group.command(name="show")
@click.pass_context
def backup_show(ctx: click.Context) -> None:
    """Show backup network configuration."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_backup(client: EeroClient) -> None:
            with cli_ctx.status("Getting backup network settings..."):
                try:
                    backup_data = await client.get_backup_network(cli_ctx.network_id)
                except Exception as e:
                    if is_premium_error(e):
                        console.print("[yellow]Backup network requires Eero Plus[/yellow]")
                        sys.exit(ExitCode.PREMIUM_REQUIRED)
                    raise

            if cli_ctx.is_json_output():
                renderer.render_json(backup_data, "eero.network.backup.show/v1")
            else:
                enabled = backup_data.get("enabled", False)
                content = (
                    f"[bold]Enabled:[/bold] {'[green]Yes[/green]' if enabled else '[dim]No[/dim]'}"
                )
                console.print(Panel(content, title="Backup Network", border_style="blue"))

        await run_with_client(get_backup)

    asyncio.run(run_cmd())


@backup_group.command(name="enable")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def backup_enable(ctx: click.Context, force: bool) -> None:
    """Enable backup network."""
    cli_ctx = get_cli_context(ctx)
    _set_backup(cli_ctx, True, force)


@backup_group.command(name="disable")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def backup_disable(ctx: click.Context, force: bool) -> None:
    """Disable backup network."""
    cli_ctx = get_cli_context(ctx)
    _set_backup(cli_ctx, False, force)


def _set_backup(cli_ctx: EeroCliContext, enable: bool, force: bool) -> None:
    """Set backup network state."""
    console = cli_ctx.console
    action = "enable" if enable else "disable"

    try:
        confirm_or_fail(
            action=f"{action} backup network",
            target="network",
            risk=OperationRisk.MEDIUM,
            force=force or cli_ctx.force,
            non_interactive=cli_ctx.non_interactive,
            dry_run=cli_ctx.dry_run,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_backup(client: EeroClient) -> None:
            with cli_ctx.status(f"{action.capitalize()}ing backup network..."):
                try:
                    result = await client.set_backup_network(enable, cli_ctx.network_id)
                except Exception as e:
                    if is_premium_error(e):
                        console.print("[yellow]Backup network requires Eero Plus[/yellow]")
                        sys.exit(ExitCode.PREMIUM_REQUIRED)
                    raise

            if result:
                console.print(f"[bold green]Backup network {action}d[/bold green]")
            else:
                console.print(f"[red]Failed to {action} backup network[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_backup)

    asyncio.run(run_cmd())


@backup_group.command(name="status")
@click.pass_context
def backup_status(ctx: click.Context) -> None:
    """Show current backup network status."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_status(client: EeroClient) -> None:
            with cli_ctx.status("Getting backup status..."):
                try:
                    status_data = await client.get_backup_status(cli_ctx.network_id)
                    # TODO: is_using_backup method not yet implemented in eero-api
                    is_using = await client.is_using_backup(cli_ctx.network_id)  # type: ignore[attr-defined]
                except Exception as e:
                    if is_premium_error(e):
                        console.print("[yellow]Backup network requires Eero Plus[/yellow]")
                        sys.exit(ExitCode.PREMIUM_REQUIRED)
                    raise

            if cli_ctx.is_json_output():
                renderer.render_json(
                    {**status_data, "using_backup": is_using}, "eero.network.backup.status/v1"
                )
            else:
                style = "yellow" if is_using else "green"
                status = "Using Backup" if is_using else "Primary Connection"
                content = f"[bold]Status:[/bold] [{style}]{status}[/{style}]"
                console.print(Panel(content, title="Backup Status", border_style=style))

        await run_with_client(get_status)

    asyncio.run(run_cmd())
