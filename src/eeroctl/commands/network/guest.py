"""Guest network commands for the Eero CLI.

Commands:
- eero network guest show: Show guest network settings
- eero network guest enable: Enable guest network
- eero network guest disable: Disable guest network
- eero network guest set: Configure guest network
"""

import asyncio
import sys
from typing import Optional

import click
from eero import EeroClient
from rich.panel import Panel

from ...context import EeroCliContext, get_cli_context
from ...exit_codes import ExitCode
from ...safety import OperationRisk, SafetyError, confirm_or_fail
from ...transformers import extract_data, normalize_network
from ...utils import run_with_client


@click.group(name="guest")
@click.pass_context
def guest_group(ctx: click.Context) -> None:
    """Manage guest network.

    \b
    Commands:
      show    - Show guest network settings
      enable  - Enable guest network
      disable - Disable guest network
      set     - Configure guest network

    \b
    Examples:
      eero network guest show
      eero network guest enable
      eero network guest set --name "Guest WiFi" --password "secret123"
    """
    pass


@guest_group.command(name="show")
@click.pass_context
def guest_show(ctx: click.Context) -> None:
    """Show guest network settings."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_guest(client: EeroClient) -> None:
            with cli_ctx.status("Getting guest network settings..."):
                raw_network = await client.get_network(cli_ctx.network_id)

            network = normalize_network(extract_data(raw_network))

            data = {
                "enabled": network.get("guest_network_enabled"),
                "name": network.get("guest_network_name"),
                "password": "********" if network.get("guest_network_password") else None,
            }

            if cli_ctx.is_json_output():
                renderer.render_json(data, "eero.network.guest.show/v1")
            elif cli_ctx.is_list_output():
                renderer.render_text(data, "eero.network.guest.show/v1")
            else:
                enabled = network.get("guest_network_enabled")
                content = (
                    f"[bold]Enabled:[/bold] {'[green]Yes[/green]' if enabled else '[dim]No[/dim]'}\n"
                    f"[bold]Name:[/bold] {network.get('guest_network_name') or 'N/A'}\n"
                    f"[bold]Password:[/bold] {'********' if network.get('guest_network_password') else 'N/A'}"
                )
                console.print(Panel(content, title="Guest Network", border_style="blue"))

        await run_with_client(get_guest)

    asyncio.run(run_cmd())


@guest_group.command(name="enable")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def guest_enable(ctx: click.Context, force: bool) -> None:
    """Enable guest network."""
    cli_ctx = get_cli_context(ctx)
    _set_guest_network(cli_ctx, True, None, None, force)


@guest_group.command(name="disable")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def guest_disable(ctx: click.Context, force: bool) -> None:
    """Disable guest network."""
    cli_ctx = get_cli_context(ctx)
    _set_guest_network(cli_ctx, False, None, None, force)


@guest_group.command(name="set")
@click.option("--name", help="Guest network name")
@click.option("--password", help="Guest network password")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def guest_set(
    ctx: click.Context, name: Optional[str], password: Optional[str], force: bool
) -> None:
    """Configure guest network settings.

    \b
    Options:
      --name      Guest network SSID
      --password  Guest network password

    \b
    Examples:
      eero network guest set --name "Guest WiFi" --password "welcome123"
    """
    cli_ctx = get_cli_context(ctx)
    _set_guest_network(cli_ctx, True, name, password, force)


def _set_guest_network(
    cli_ctx: EeroCliContext,
    enable: bool,
    name: Optional[str],
    password: Optional[str],
    force: bool,
) -> None:
    """Set guest network settings."""
    console = cli_ctx.console
    action = "enable" if enable else "disable"

    try:
        confirm_or_fail(
            action=f"{action} guest network",
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
        async def set_guest(client: EeroClient) -> None:
            with cli_ctx.status(f"{action.capitalize()}ing guest network..."):
                result = await client.set_guest_network(
                    enabled=enable,
                    name=name,
                    password=password,
                    network_id=cli_ctx.network_id,
                )

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print(f"[bold green]Guest network {action}d[/bold green]")
            else:
                console.print(f"[red]Failed to {action} guest network[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_guest)

    asyncio.run(run_cmd())
