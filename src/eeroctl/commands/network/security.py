"""Security commands for the Eero CLI.

Commands:
- eero network security show: Show security settings
- eero network security wpa3: WPA3 encryption
- eero network security band-steering: Band steering
- eero network security upnp: UPnP
- eero network security ipv6: IPv6
- eero network security thread: Thread protocol
"""

import asyncio
import sys

import click
from eero import EeroClient
from rich.table import Table

from ...context import get_cli_context
from ...exit_codes import ExitCode
from ...safety import OperationRisk, SafetyError, confirm_or_fail
from ...utils import run_with_client


@click.group(name="security")
@click.pass_context
def security_group(ctx: click.Context) -> None:
    """Manage security settings.

    \b
    Commands:
      show           - Show security settings
      wpa3           - WPA3 encryption
      band-steering  - Band steering
      upnp           - UPnP
      ipv6           - IPv6
      thread         - Thread protocol

    \b
    Examples:
      eero network security show
      eero network security wpa3 enable
      eero network security upnp disable
    """
    pass


@security_group.command(name="show")
@click.pass_context
def security_show(ctx: click.Context) -> None:
    """Show security settings."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_security(client: EeroClient) -> None:
            with cli_ctx.status("Getting security settings..."):
                sec_data = await client.get_security_settings(cli_ctx.network_id)

            if cli_ctx.is_json_output():
                renderer.render_json(sec_data, "eero.network.security.show/v1")
            elif cli_ctx.is_list_output():
                renderer.render_text(sec_data, "eero.network.security.show/v1")
            else:
                table = Table(title="Security Settings")
                table.add_column("Setting", style="cyan")
                table.add_column("Status", justify="center")

                settings = [
                    ("WPA3", sec_data.get("wpa3", False)),
                    ("Band Steering", sec_data.get("band_steering", True)),
                    ("UPnP", sec_data.get("upnp", True)),
                    ("IPv6", sec_data.get("ipv6_upstream", False)),
                    ("Thread", sec_data.get("thread", False)),
                ]

                for name, enabled in settings:
                    status = "[green]Enabled[/green]" if enabled else "[dim]Disabled[/dim]"
                    table.add_row(name, status)

                console.print(table)

        await run_with_client(get_security)

    asyncio.run(run_cmd())


# Security toggle commands factory
def _make_security_toggle(setting_name: str, api_method: str, display_name: str):
    """Factory for security toggle command groups."""

    @click.group(name=setting_name)
    @click.pass_context
    def toggle_group(ctx: click.Context) -> None:
        pass

    @toggle_group.command(name="enable")
    @click.option("--force", "-f", is_flag=True, help="Skip confirmation")
    @click.pass_context
    def enable_cmd(ctx: click.Context, force: bool) -> None:
        _set_security_setting(ctx, api_method, display_name, True, force)

    @toggle_group.command(name="disable")
    @click.option("--force", "-f", is_flag=True, help="Skip confirmation")
    @click.pass_context
    def disable_cmd(ctx: click.Context, force: bool) -> None:
        _set_security_setting(ctx, api_method, display_name, False, force)

    enable_cmd.__doc__ = f"Enable {display_name}."
    disable_cmd.__doc__ = f"Disable {display_name}."
    toggle_group.__doc__ = f"Manage {display_name}."

    return toggle_group


def _set_security_setting(ctx, api_method: str, display_name: str, enable: bool, force: bool):
    """Set a security setting."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    action = "enable" if enable else "disable"

    try:
        confirm_or_fail(
            action=f"{action} {display_name}",
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
        async def set_setting(client: EeroClient) -> None:
            method = getattr(client, api_method)
            with cli_ctx.status(f"{action.capitalize()}ing {display_name}..."):
                result = await method(enable, cli_ctx.network_id)

            if result:
                console.print(f"[bold green]{display_name} {action}d[/bold green]")
            else:
                console.print(f"[red]Failed to {action} {display_name}[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_setting)

    asyncio.run(run_cmd())


# Create and register security toggle commands
wpa3_group = _make_security_toggle("wpa3", "set_wpa3", "WPA3")
band_steering_group = _make_security_toggle("band-steering", "set_band_steering", "band steering")
upnp_group = _make_security_toggle("upnp", "set_upnp", "UPnP")
ipv6_group = _make_security_toggle("ipv6", "set_ipv6", "IPv6")
thread_group = _make_security_toggle("thread", "set_thread_enabled", "Thread")

security_group.add_command(wpa3_group)
security_group.add_command(band_steering_group)
security_group.add_command(upnp_group)
security_group.add_command(ipv6_group)
security_group.add_command(thread_group)
