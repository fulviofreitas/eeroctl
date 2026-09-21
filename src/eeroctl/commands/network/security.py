"""Security commands for the Eero CLI.

Commands:
- eero network security show: Show security settings
- eero network security wpa3: WPA3 encryption
- eero network security band-steering: Band steering
- eero network security upnp: UPnP
- eero network security ipv6: IPv6
- eero network security thread: Thread protocol
- eero network security mlo set: Multi-link operation mode
- eero network security passpoint: Passpoint
- eero network security proxied-nodes: Proxied nodes
"""

import asyncio
import sys
from typing import Any

import click
from eero import EeroClient
from rich.table import Table

from ...const import MLO_MODES
from ...context import get_cli_context
from ...formatting.wpa3 import print_fast_transition
from ...options import apply_options, common_options
from ...safety import SafetyContext, SafetyError, get_write_spec, require_write_confirmation
from ...transformers import extract_data
from ...transformers.wpa3 import extract_fast_transition
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
      fast-transition - 802.11r fast transition (read-only in phase A)
      mlo            - Multi-link operation mode
      passpoint      - Passpoint
      proxied-nodes  - Proxied nodes

    \b
    Examples:
      eero network security show
      eero network security wpa3 enable
      eero network security upnp disable
      eero network security fast-transition show
    """
    pass


@security_group.command(name="show")
@click.pass_context
def security_show(ctx: click.Context) -> None:
    """Show security settings.

    Extended with `mlo_mode`, `passpoint`, `proxied_nodes`, and `ddns`, read
    straight from the `get_network` envelope since no dedicated GETs exist
    for them (migration plan §4, `network security show` (extend) row).
    """
    from ...formatting.generic import redact_sensitive
    from ...transformers.network import extract_network, extract_network_security_extras

    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_security(client: EeroClient) -> None:
            with cli_ctx.status("Getting security settings..."):
                raw_security = await client.get_security_settings(cli_ctx.network_id)
                raw_network = await client.get_network(cli_ctx.network_id)

            sec_data = extract_data(raw_security) if isinstance(raw_security, dict) else {}
            extras = extract_network_security_extras(extract_network(raw_network))

            if cli_ctx.is_json_output():
                # json is the user's explicit opt-in to the raw payload (see
                # formatting/generic.py); extras are not redacted here.
                renderer.render_json({**sec_data, **extras}, "eero.network.security.show/v1")
            elif cli_ctx.is_list_output():
                # `ddns` may carry a provider username/token (migration plan
                # §4, `network security show` (extend) row); this bespoke
                # render_text call bypasses the generic renderer, so redact
                # extras the same way it would.
                safe_extras = redact_sensitive(extras)
                renderer.render_text({**sec_data, **safe_extras}, "eero.network.security.show/v1")
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

                safe_extras = redact_sensitive(extras)
                extras_table = Table(title="Extended Security Settings")
                extras_table.add_column("Field", style="cyan")
                extras_table.add_column("Value")
                for key in ("mlo_mode", "passpoint", "proxied_nodes", "ddns"):
                    extras_table.add_row(key, str(safe_extras.get(key)))
                console.print(extras_table)

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
                console=cli_ctx.err_console,
                read_command=spec.read_command,
            )

        await run_with_client(set_setting)

    asyncio.run(run_cmd())


# `passpoint`/`proxied_nodes` have no dedicated GET -- they live on the raw
# `get_network` envelope, the same fields the phase-A extended `security
# show` reads (migration plan §2.7). This factory mirrors
# `_make_security_toggle` but reads its current state from there instead of
# `get_security_settings`.
def _make_network_field_toggle(
    setting_name: str, api_method: str, display_name: str, state_field: str
):
    """Factory for security toggle command groups backed by `get_network`."""

    @click.group(name=setting_name)
    @click.pass_context
    def toggle_group(ctx: click.Context) -> None:
        pass

    @toggle_group.command(name="enable")
    @click.option("--force", "-f", is_flag=True, help="Skip confirmation")
    @click.pass_context
    def enable_cmd(ctx: click.Context, force: bool) -> None:
        _set_network_field_setting(
            ctx, setting_name, api_method, display_name, state_field, True, force
        )

    @toggle_group.command(name="disable")
    @click.option("--force", "-f", is_flag=True, help="Skip confirmation")
    @click.pass_context
    def disable_cmd(ctx: click.Context, force: bool) -> None:
        _set_network_field_setting(
            ctx, setting_name, api_method, display_name, state_field, False, force
        )

    enable_cmd.__doc__ = f"Enable {display_name}."
    disable_cmd.__doc__ = f"Disable {display_name}."
    toggle_group.__doc__ = f"Manage {display_name}."

    return toggle_group


def _set_network_field_setting(
    ctx,
    setting_name: str,
    api_method: str,
    display_name: str,
    state_field: str,
    enable: bool,
    force: bool,
):
    """Set a security setting whose current state lives on `get_network`."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    action = "enable" if enable else "disable"
    effective_force = force or cli_ctx.force
    spec = get_write_spec(f"network security {setting_name} {action}")
    cli_ctx.active_write_spec = spec

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
                    raw_network = await client.get_network(cli_ctx.network_id)
                net_data = extract_data(raw_network) if isinstance(raw_network, dict) else {}
                return bool(net_data.get(state_field, not enable))

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


@security_group.group(name="mlo")
@click.pass_context
def mlo_group(ctx: click.Context) -> None:
    """Manage multi-link operation (MLO) mode.

    \b
    Commands:
      set - Set the MLO mode
    """
    pass


@mlo_group.command(name="set")
@click.argument("mode", type=click.Choice(MLO_MODES))
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def mlo_set(ctx: click.Context, mode: str, force: bool) -> None:
    """Set the network's MLO mode.

    Applying this change reboots every eero on the network.

    \b
    Arguments:
      MODE  One of: disabled, single, multi
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    effective_force = force or cli_ctx.force
    spec = get_write_spec("network security mlo set")
    cli_ctx.active_write_spec = spec

    try:
        require_write_confirmation(
            spec,
            target=mode,
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
        async def set_mlo(client: EeroClient) -> None:
            async def read() -> str:
                with cli_ctx.status("Reading current MLO mode..."):
                    raw_network = await client.get_network(cli_ctx.network_id)
                net_data = extract_data(raw_network) if isinstance(raw_network, dict) else {}
                return str(net_data.get("mlo_mode") or "")

            async def write() -> Any:
                with cli_ctx.status(f"Setting MLO mode to '{mode}'..."):
                    return await client.set_mlo_mode(mode, cli_ctx.network_id)

            await write_if_changed(
                read,
                mode,
                write,
                force=effective_force,
                console=console,
                read_command=spec.read_command,
            )

        await run_with_client(set_mlo)

    asyncio.run(run_cmd())


# Create and register security toggle commands
wpa3_group = _make_security_toggle("wpa3", "set_wpa3", "WPA3")
band_steering_group = _make_security_toggle("band-steering", "set_band_steering", "band steering")
upnp_group = _make_security_toggle("upnp", "set_upnp", "UPnP")
ipv6_group = _make_security_toggle("ipv6", "set_ipv6", "IPv6")
thread_group = _make_security_toggle("thread", "set_thread_enabled", "Thread")
passpoint_group = _make_network_field_toggle(
    "passpoint", "set_passpoint_enabled", "Passpoint", "passpoint"
)
proxied_nodes_group = _make_network_field_toggle(
    "proxied-nodes", "set_proxied_nodes", "proxied nodes", "proxied_nodes"
)

security_group.add_command(wpa3_group)
security_group.add_command(band_steering_group)
security_group.add_command(upnp_group)
security_group.add_command(ipv6_group)
security_group.add_command(thread_group)


# ==================== Fast Transition (read-only, phase A) ====================
#
# get_fast_transition (client.py:2770) is a plain GET; the writer
# (set_fast_transition) is phase C. Its own subgroup, distinct from the
# enable/disable toggle factory above.


@security_group.group(name="fast-transition")
@click.pass_context
def fast_transition_group(ctx: click.Context) -> None:
    """View 802.11r fast transition settings.

    \b
    Commands:
      show - Current fast-transition setting
    """
    pass


@fast_transition_group.command(name="show")
@common_options
@click.pass_context
def fast_transition_show(ctx: click.Context, output, network_id) -> None:
    """Show the current fast-transition setting."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_fast_transition(client: EeroClient) -> None:
            with cli_ctx.status("Getting fast-transition settings..."):
                raw = await client.get_fast_transition(cli_ctx.network_id)
            print_fast_transition(cli_ctx, extract_fast_transition(raw))

        await run_with_client(get_fast_transition)

    asyncio.run(run_cmd())


security_group.add_command(passpoint_group)
security_group.add_command(proxied_nodes_group)
