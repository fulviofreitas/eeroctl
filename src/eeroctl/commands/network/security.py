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
from typing import Any

import click
from eero import EeroClient
from rich.table import Table

from ...context import get_cli_context
from ...safety import SafetyContext, SafetyError, get_write_spec, require_write_confirmation
from ...transformers import extract_data
from ...utils import run_with_client, write_if_changed


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
                raw_security = await client.get_security_settings(cli_ctx.network_id)

            sec_data = extract_data(raw_security) if isinstance(raw_security, dict) else {}

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


# Field each toggle reads back from `get_security_settings`'s `data`, so
# `write_if_changed` can tell whether a write is actually a no-op. Mirrors
# the field names `security_show` already renders (security.py:74-78).
_SECURITY_STATE_FIELD = {
    "wpa3": "wpa3",
    "band-steering": "band_steering",
    "upnp": "upnp",
    "ipv6": "ipv6_upstream",
    "thread": "thread",
}


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
        _set_security_setting(ctx, setting_name, api_method, display_name, True, force)

    @toggle_group.command(name="disable")
    @click.option("--force", "-f", is_flag=True, help="Skip confirmation")
    @click.pass_context
    def disable_cmd(ctx: click.Context, force: bool) -> None:
        _set_security_setting(ctx, setting_name, api_method, display_name, False, force)

    enable_cmd.__doc__ = f"Enable {display_name}."
    disable_cmd.__doc__ = f"Disable {display_name}."
    toggle_group.__doc__ = f"Manage {display_name}."

    return toggle_group


def _set_security_setting(
    ctx, setting_name: str, api_method: str, display_name: str, enable: bool, force: bool
):
    """Set a security setting."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    action = "enable" if enable else "disable"
    effective_force = force or cli_ctx.force
    spec = get_write_spec(f"network security {setting_name} {action}")
    cli_ctx.active_write_spec = spec
    state_field = _SECURITY_STATE_FIELD[setting_name]

    try:
        require_write_confirmation(
            spec,
            target="network",
            ctx=SafetyContext(
                force=effective_force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_setting(client: EeroClient) -> None:
            method = getattr(client, api_method)

            async def read() -> bool:
                with cli_ctx.status(f"Reading current {display_name} setting..."):
                    raw_security = await client.get_security_settings(cli_ctx.network_id)
                sec_data = extract_data(raw_security) if isinstance(raw_security, dict) else {}
                return bool(sec_data.get(state_field, not enable))

            async def write() -> Any:
                with cli_ctx.status(f"{action.capitalize()}ing {display_name}..."):
                    return await method(enable, cli_ctx.network_id)

            await write_if_changed(
                read,
                enable,
                write,
                force=effective_force,
                console=console,
                read_command=spec.read_command,
            )

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
