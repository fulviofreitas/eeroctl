"""Eero (mesh node) commands for the Eero CLI.

Commands:
- eero eero list: List all mesh nodes
- eero eero show: Show node details
- eero eero reboot: Reboot a node
- eero eero led: LED management
- eero eero nightlight: Nightlight management (Beacon only)
- eero eero updates: Update management
"""

import asyncio
import sys
from typing import Literal

import click
from rich.panel import Panel
from rich.table import Table

from eero import EeroClient
from eero.exceptions import EeroException, EeroNotFoundException
from ..context import EeroCliContext, ensure_cli_context, get_cli_context
from ..errors import is_feature_unavailable_error, is_not_found_error
from ..exit_codes import ExitCode
from ..output import OutputFormat
from ..safety import OperationRisk, SafetyError, confirm_or_fail
from ..utils import run_with_client


@click.group(name="eero")
@click.pass_context
def eero_group(ctx: click.Context) -> None:
    """Manage Eero mesh nodes.

    \b
    Commands:
      list       - List all mesh nodes
      show       - Show node details
      reboot     - Reboot a node
      led        - LED management
      nightlight - Nightlight (Beacon only)
      updates    - Update management

    \b
    Examples:
      eero eero list                    # List all nodes
      eero eero show "Living Room"      # Show node by name
      eero eero reboot "Office" --force # Reboot node
      eero eero led show "Kitchen"      # Show LED status
    """
    ensure_cli_context(ctx)


@eero_group.command(name="list")
@click.pass_context
def eero_list(ctx: click.Context) -> None:
    """List all Eero mesh nodes."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def get_eeros(client: EeroClient) -> None:
            with console.status("Getting Eero devices..."):
                eeros = await client.get_eeros(cli_ctx.network_id)

            if not eeros:
                console.print("[yellow]No Eero devices found[/yellow]")
                return

            if cli_ctx.is_structured_output():
                data = [e.model_dump(mode="json") for e in eeros]
                cli_ctx.render_structured(data, "eero.eero.list/v1")
            elif cli_ctx.output_format == OutputFormat.LIST:
                for e in eeros:
                    console.print(f"{e.eero_id}\t{e.location}\t{e.status}")
            else:
                table = Table(title="Eero Devices")
                table.add_column("ID", style="dim")
                table.add_column("Name", style="cyan")
                table.add_column("Model", style="green")
                table.add_column("IP", style="blue")
                table.add_column("Status")
                table.add_column("Role")
                table.add_column("Connection", style="magenta")

                for e in eeros:
                    status_color = "green" if e.status == "green" else "red"
                    role = "Gateway" if e.gateway else "Leaf"
                    table.add_row(
                        e.eero_id or "",
                        str(e.location) if e.location else "",
                        e.model or "",
                        e.ip_address or "",
                        f"[{status_color}]{e.status}[/{status_color}]",
                        role,
                        e.connection_type or "",
                    )

                console.print(table)

        await run_with_client(get_eeros)

    asyncio.run(run_cmd())


@eero_group.command(name="show")
@click.argument("eero_id")
@click.pass_context
def eero_show(ctx: click.Context, eero_id: str) -> None:
    """Show details of a specific Eero node.

    \b
    Arguments:
      EERO_ID  Node ID, serial, or location name
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def get_eero(client: EeroClient) -> None:
            with console.status(f"Getting Eero '{eero_id}'..."):
                try:
                    eero = await client.get_eero(eero_id, cli_ctx.network_id)
                except (EeroNotFoundException, EeroException) as e:
                    if is_not_found_error(e):
                        console.print(f"[red]Eero '{eero_id}' not found[/red]")
                        sys.exit(ExitCode.NOT_FOUND)
                    raise

            if cli_ctx.is_structured_output():
                cli_ctx.render_structured(eero.model_dump(mode="json"), "eero.eero.show/v1")
            else:
                from ..formatting import print_eero_details

                detail: Literal["brief", "full"] = (
                    "full" if cli_ctx.detail_level == "full" else "brief"
                )
                print_eero_details(eero, detail_level=detail)

        await run_with_client(get_eero)

    asyncio.run(run_cmd())


@eero_group.command(name="reboot")
@click.argument("eero_id")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def eero_reboot(ctx: click.Context, eero_id: str, force: bool) -> None:
    """Reboot an Eero node.

    This is a disruptive operation that will temporarily
    disconnect clients connected to this node.

    \b
    Arguments:
      EERO_ID  Node ID, serial, or location name
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def reboot_eero(client: EeroClient) -> None:
            # First resolve the eero to get its name
            with console.status(f"Finding Eero '{eero_id}'..."):
                try:
                    eero = await client.get_eero(eero_id, cli_ctx.network_id)
                except (EeroNotFoundException, EeroException) as e:
                    if is_not_found_error(e):
                        console.print(f"[red]Eero '{eero_id}' not found[/red]")
                        sys.exit(ExitCode.NOT_FOUND)
                    raise

            eero_name = str(eero.location) if eero.location else eero.serial or eero_id

            try:
                confirm_or_fail(
                    action="reboot",
                    target=eero_name,
                    risk=OperationRisk.MEDIUM,
                    force=force or cli_ctx.force,
                    non_interactive=cli_ctx.non_interactive,
                    dry_run=cli_ctx.dry_run,
                    console=cli_ctx.console,
                )
            except SafetyError as e:
                cli_ctx.renderer.render_error(e.message)
                sys.exit(e.exit_code)

            with console.status(f"Rebooting {eero_name}..."):
                result = await client.reboot_eero(eero.eero_id, cli_ctx.network_id)

            if result:
                console.print(f"[bold green]Reboot initiated for {eero_name}[/bold green]")
            else:
                console.print(f"[red]Failed to reboot {eero_name}[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(reboot_eero)

    asyncio.run(run_cmd())


# ==================== LED Subcommand Group ====================


@eero_group.group(name="led")
@click.pass_context
def led_group(ctx: click.Context) -> None:
    """Manage LED settings.

    \b
    Commands:
      show       - Show LED status
      on         - Turn LED on
      off        - Turn LED off
      brightness - Set LED brightness
    """
    pass


@led_group.command(name="show")
@click.argument("eero_id")
@click.pass_context
def led_show(ctx: click.Context, eero_id: str) -> None:
    """Show LED status for an Eero node."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_led(client: EeroClient) -> None:
            # Resolve eero first (by ID, serial, location, or MAC)
            with console.status(f"Finding Eero '{eero_id}'..."):
                try:
                    eero = await client.get_eero(eero_id, cli_ctx.network_id)
                except EeroNotFoundException:
                    console.print(f"[red]Eero '{eero_id}' not found[/red]")
                    sys.exit(ExitCode.NOT_FOUND)

            with console.status("Getting LED status..."):
                led_data = await client.get_led_status(eero.eero_id, cli_ctx.network_id)

            if cli_ctx.is_json_output():
                renderer.render_json(led_data, "eero.eero.led.show/v1")
            else:
                led_on = led_data.get("led_on", False)
                brightness = led_data.get("led_brightness", 100)

                content = (
                    f"[bold]Status:[/bold] {'[green]On[/green]' if led_on else '[dim]Off[/dim]'}\n"
                    f"[bold]Brightness:[/bold] {brightness}%"
                )
                console.print(Panel(content, title="LED Settings", border_style="blue"))

        await run_with_client(get_led)

    asyncio.run(run_cmd())


@led_group.command(name="on")
@click.argument("eero_id")
@click.pass_context
def led_on(ctx: click.Context, eero_id: str) -> None:
    """Turn LED on."""
    cli_ctx = get_cli_context(ctx)
    _set_led(cli_ctx, eero_id, True)


@led_group.command(name="off")
@click.argument("eero_id")
@click.pass_context
def led_off(ctx: click.Context, eero_id: str) -> None:
    """Turn LED off."""
    cli_ctx = get_cli_context(ctx)
    _set_led(cli_ctx, eero_id, False)


def _set_led(cli_ctx: EeroCliContext, eero_id: str, enabled: bool) -> None:
    """Set LED state."""
    console = cli_ctx.console
    action = "on" if enabled else "off"

    async def run_cmd() -> None:
        async def set_led(client: EeroClient) -> None:
            # Resolve eero first (by ID, serial, location, or MAC)
            with console.status(f"Finding Eero '{eero_id}'..."):
                try:
                    eero = await client.get_eero(eero_id, cli_ctx.network_id)
                except EeroNotFoundException:
                    console.print(f"[red]Eero '{eero_id}' not found[/red]")
                    sys.exit(ExitCode.NOT_FOUND)

            with console.status(f"Turning LED {action}..."):
                result = await client.set_led(eero.eero_id, enabled, cli_ctx.network_id)

            if result:
                console.print(f"[bold green]LED turned {action}[/bold green]")
            else:
                console.print(f"[red]Failed to turn LED {action}[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_led)

    asyncio.run(run_cmd())


@led_group.command(name="brightness")
@click.argument("eero_id")
@click.argument("value", type=click.IntRange(0, 100))
@click.pass_context
def led_brightness(ctx: click.Context, eero_id: str, value: int) -> None:
    """Set LED brightness (0-100)."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def set_brightness(client: EeroClient) -> None:
            # Resolve eero first (by ID, serial, location, or MAC)
            with console.status(f"Finding Eero '{eero_id}'..."):
                try:
                    eero = await client.get_eero(eero_id, cli_ctx.network_id)
                except EeroNotFoundException:
                    console.print(f"[red]Eero '{eero_id}' not found[/red]")
                    sys.exit(ExitCode.NOT_FOUND)

            with console.status(f"Setting LED brightness to {value}%..."):
                result = await client.set_led_brightness(eero.eero_id, value, cli_ctx.network_id)

            if result:
                console.print(f"[bold green]LED brightness set to {value}%[/bold green]")
            else:
                console.print("[red]Failed to set LED brightness[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_brightness)

    asyncio.run(run_cmd())


# ==================== Nightlight Subcommand Group ====================


@eero_group.group(name="nightlight")
@click.pass_context
def nightlight_group(ctx: click.Context) -> None:
    """Manage nightlight (Eero Beacon only).

    \b
    Commands:
      show       - Show nightlight settings
      on         - Turn nightlight on
      off        - Turn nightlight off
      brightness - Set brightness
      schedule   - Set schedule
    """
    pass


@nightlight_group.command(name="show")
@click.argument("eero_id")
@click.pass_context
def nightlight_show(ctx: click.Context, eero_id: str) -> None:
    """Show nightlight settings."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_nightlight(client: EeroClient) -> None:
            # Resolve eero first (by ID, serial, location, or MAC)
            with console.status(f"Finding Eero '{eero_id}'..."):
                try:
                    eero = await client.get_eero(eero_id, cli_ctx.network_id)
                except EeroNotFoundException:
                    console.print(f"[red]Eero '{eero_id}' not found[/red]")
                    sys.exit(ExitCode.NOT_FOUND)

            with console.status("Getting nightlight settings..."):
                try:
                    nl_data = await client.get_nightlight(eero.eero_id, cli_ctx.network_id)
                except Exception as e:
                    if is_feature_unavailable_error(e, "beacon"):
                        console.print(
                            "[yellow]Nightlight is only available on Eero Beacon devices[/yellow]"
                        )
                        sys.exit(ExitCode.FEATURE_UNAVAILABLE)
                    raise

            if cli_ctx.is_json_output():
                renderer.render_json(nl_data, "eero.eero.nightlight.show/v1")
            else:
                enabled = nl_data.get("enabled", False)
                brightness = nl_data.get("brightness", 100)
                schedule_enabled = nl_data.get("schedule_enabled", False)

                content = (
                    f"[bold]Enabled:[/bold] {'[green]Yes[/green]' if enabled else '[dim]No[/dim]'}\n"
                    f"[bold]Brightness:[/bold] {brightness}%"
                )
                if schedule_enabled:
                    on_time = nl_data.get("on_time", "N/A")
                    off_time = nl_data.get("off_time", "N/A")
                    content += f"\n[bold]Schedule:[/bold] {on_time} - {off_time}"

                console.print(Panel(content, title="Nightlight Settings", border_style="blue"))

        await run_with_client(get_nightlight)

    asyncio.run(run_cmd())


@nightlight_group.command(name="on")
@click.argument("eero_id")
@click.pass_context
def nightlight_on(ctx: click.Context, eero_id: str) -> None:
    """Turn nightlight on."""
    cli_ctx = get_cli_context(ctx)
    _set_nightlight(cli_ctx, eero_id, True)


@nightlight_group.command(name="off")
@click.argument("eero_id")
@click.pass_context
def nightlight_off(ctx: click.Context, eero_id: str) -> None:
    """Turn nightlight off."""
    cli_ctx = get_cli_context(ctx)
    _set_nightlight(cli_ctx, eero_id, False)


def _set_nightlight(cli_ctx: EeroCliContext, eero_id: str, enabled: bool) -> None:
    """Set nightlight state."""
    console = cli_ctx.console
    action = "on" if enabled else "off"

    async def run_cmd() -> None:
        async def set_nl(client: EeroClient) -> None:
            # Resolve eero first (by ID, serial, location, or MAC)
            with console.status(f"Finding Eero '{eero_id}'..."):
                try:
                    eero = await client.get_eero(eero_id, cli_ctx.network_id)
                except EeroNotFoundException:
                    console.print(f"[red]Eero '{eero_id}' not found[/red]")
                    sys.exit(ExitCode.NOT_FOUND)

            with console.status(f"Turning nightlight {action}..."):
                try:
                    result = await client.set_nightlight(
                        eero.eero_id, enabled=enabled, network_id=cli_ctx.network_id
                    )
                except Exception as e:
                    if is_feature_unavailable_error(e, "beacon"):
                        console.print(
                            "[yellow]Nightlight is only available on Eero Beacon devices[/yellow]"
                        )
                        sys.exit(ExitCode.FEATURE_UNAVAILABLE)
                    raise

            if result:
                console.print(f"[bold green]Nightlight turned {action}[/bold green]")
            else:
                console.print(f"[red]Failed to turn nightlight {action}[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_nl)

    asyncio.run(run_cmd())


@nightlight_group.command(name="brightness")
@click.argument("eero_id")
@click.argument("value", type=click.IntRange(0, 100))
@click.pass_context
def nightlight_brightness(ctx: click.Context, eero_id: str, value: int) -> None:
    """Set nightlight brightness (0-100)."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def set_brightness(client: EeroClient) -> None:
            # Resolve eero first (by ID, serial, location, or MAC)
            with console.status(f"Finding Eero '{eero_id}'..."):
                try:
                    eero = await client.get_eero(eero_id, cli_ctx.network_id)
                except EeroNotFoundException:
                    console.print(f"[red]Eero '{eero_id}' not found[/red]")
                    sys.exit(ExitCode.NOT_FOUND)

            with console.status(f"Setting nightlight brightness to {value}%..."):
                try:
                    result = await client.set_nightlight_brightness(
                        eero.eero_id, value, cli_ctx.network_id
                    )
                except Exception as e:
                    if is_feature_unavailable_error(e, "beacon"):
                        console.print(
                            "[yellow]Nightlight is only available on Eero Beacon devices[/yellow]"
                        )
                        sys.exit(ExitCode.FEATURE_UNAVAILABLE)
                    raise

            if result:
                console.print(f"[bold green]Nightlight brightness set to {value}%[/bold green]")
            else:
                console.print("[red]Failed to set nightlight brightness[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_brightness)

    asyncio.run(run_cmd())


@nightlight_group.command(name="schedule")
@click.argument("eero_id")
@click.option("--on-time", required=True, help="Time to turn on (HH:MM)")
@click.option("--off-time", required=True, help="Time to turn off (HH:MM)")
@click.pass_context
def nightlight_schedule(ctx: click.Context, eero_id: str, on_time: str, off_time: str) -> None:
    """Set nightlight schedule."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def set_schedule(client: EeroClient) -> None:
            # Resolve eero first (by ID, serial, location, or MAC)
            with console.status(f"Finding Eero '{eero_id}'..."):
                try:
                    eero = await client.get_eero(eero_id, cli_ctx.network_id)
                except EeroNotFoundException:
                    console.print(f"[red]Eero '{eero_id}' not found[/red]")
                    sys.exit(ExitCode.NOT_FOUND)

            with console.status("Setting nightlight schedule..."):
                try:
                    result = await client.set_nightlight_schedule(
                        eero.eero_id, True, on_time, off_time, cli_ctx.network_id
                    )
                except Exception as e:
                    if is_feature_unavailable_error(e, "beacon"):
                        console.print(
                            "[yellow]Nightlight is only available on Eero Beacon devices[/yellow]"
                        )
                        sys.exit(ExitCode.FEATURE_UNAVAILABLE)
                    raise

            if result:
                console.print(f"[bold green]Schedule set: {on_time} - {off_time}[/bold green]")
            else:
                console.print("[red]Failed to set schedule[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_schedule)

    asyncio.run(run_cmd())


# ==================== Updates Subcommand Group ====================


@eero_group.group(name="updates")
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
            with console.status("Getting update status..."):
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
            with console.status("Checking for updates..."):
                updates = await client.get_updates(cli_ctx.network_id)

            has_update = updates.get("has_update", False)
            if has_update:
                target = updates.get("target_firmware", "N/A")
                console.print(f"[bold green]Update available: {target}[/bold green]")
            else:
                console.print("[dim]No updates available[/dim]")

        await run_with_client(check_updates)

    asyncio.run(run_cmd())
