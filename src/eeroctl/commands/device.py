"""Device (connected device) commands for the Eero CLI.

Commands:
- eero device list: List all connected devices
- eero device show: Show device details
- eero device rename: Rename a device
- eero device block: Block a device
- eero device unblock: Unblock a device
- eero device priority: Device priority management
"""

import asyncio
import sys
from typing import Any, Dict, Literal, Optional

import click
from eero import EeroClient
from rich.panel import Panel
from rich.table import Table

from ..context import EeroCliContext, ensure_cli_context
from ..exit_codes import ExitCode
from ..options import apply_options, force_option, network_option, output_option
from ..output import OutputFormat
from ..safety import OperationRisk, SafetyError, confirm_or_fail
from ..transformers import extract_data, extract_devices, normalize_device
from ..utils import run_with_client


def _find_device(devices: list, identifier: str) -> Optional[Dict[str, Any]]:
    """Find a device by ID, MAC, or name (case-insensitive for MAC and names)."""
    identifier_lower = identifier.lower()

    for d in devices:
        dev = normalize_device(d)

        # Exact match for ID
        if dev.get("id") == identifier:
            return dev

        # Case-insensitive match for MAC
        mac = dev.get("mac") or ""
        if mac.lower() == identifier_lower:
            return dev

        # Case-insensitive match for names
        display_name = dev.get("display_name") or ""
        if display_name.lower() == identifier_lower:
            return dev

        nickname = dev.get("nickname") or ""
        if nickname.lower() == identifier_lower:
            return dev

        hostname = dev.get("hostname") or ""
        if hostname.lower() == identifier_lower:
            return dev

    return None


def _get_device_status(dev: Dict[str, Any]) -> str:
    """Get device status string."""
    if dev.get("connected"):
        if dev.get("blocked"):
            return "blocked"
        return "connected"
    return "disconnected"


@click.group(name="device")
@click.pass_context
def device_group(ctx: click.Context) -> None:
    """Manage connected devices.

    \b
    Commands:
      list     - List all connected devices
      show     - Show device details
      rename   - Rename a device
      block    - Block a device
      unblock  - Unblock a device
      priority - Bandwidth priority management

    \b
    Examples:
      eero device list                    # List all devices
      eero device show "iPhone"           # Show by name
      eero device block AA:BB:CC:DD:EE:FF # Block by MAC
      eero device priority show "iPad"    # Show priority
    """
    ensure_cli_context(ctx)


@device_group.command(name="list")
@output_option
@network_option
@click.pass_context
def device_list(ctx: click.Context, output: Optional[str], network_id: Optional[str]) -> None:
    """List all connected devices."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def get_devices(client: EeroClient) -> None:
            with cli_ctx.status("Getting devices..."):
                raw_response = await client.get_devices(cli_ctx.network_id)

            devices = extract_devices(raw_response)
            normalized = [normalize_device(d) for d in devices]

            if not normalized:
                console.print("[yellow]No devices found[/yellow]")
                return

            if cli_ctx.is_structured_output():
                cli_ctx.render_structured(normalized, "eero.device.list/v1")
            elif cli_ctx.output_format == OutputFormat.LIST:
                for d in normalized:
                    name = (
                        d.get("display_name") or d.get("hostname") or d.get("nickname") or "Unknown"
                    )
                    status = _get_device_status(d)
                    device_type = d.get("device_type") or ""
                    connection = d.get("connection_type") or ""
                    print(
                        f"{d.get('id') or '':<14}  {name:<30}  "
                        f"{d.get('ip') or d.get('ipv4') or '':<15}  "
                        f"{d.get('mac') or '':<17}  {status:<12}  "
                        f"{device_type:<20}  {connection}"
                    )
            else:
                table = Table(title="Connected Devices")
                table.add_column("ID", style="dim")
                table.add_column("Name", style="cyan")
                table.add_column("IP", style="green")
                table.add_column("MAC", style="yellow")
                table.add_column("Status")
                table.add_column("Type")
                table.add_column("Connection")

                for d in normalized:
                    name = (
                        d.get("display_name") or d.get("hostname") or d.get("nickname") or "Unknown"
                    )
                    status = _get_device_status(d)
                    if status == "connected":
                        status_display = "[green]connected[/green]"
                    elif status == "blocked":
                        status_display = "[red]blocked[/red]"
                    else:
                        status_display = "[yellow]disconnected[/yellow]"

                    table.add_row(
                        d.get("id") or "",
                        name,
                        d.get("ip") or d.get("ipv4") or "",
                        d.get("mac") or "",
                        status_display,
                        d.get("device_type") or "",
                        d.get("connection_type") or "",
                    )

                console.print(table)

        await run_with_client(get_devices)

    asyncio.run(run_cmd())


@device_group.command(name="show")
@click.argument("device_identifier")
@output_option
@network_option
@click.pass_context
def device_show(
    ctx: click.Context, device_identifier: str, output: Optional[str], network_id: Optional[str]
) -> None:
    """Show details of a specific device.

    \b
    Arguments:
      DEVICE_IDENTIFIER  Device ID, MAC address, or name
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def get_device(client: EeroClient) -> None:
            with cli_ctx.status("Finding device..."):
                raw_response = await client.get_devices(cli_ctx.network_id)

            devices = extract_devices(raw_response)
            target = _find_device(devices, device_identifier)

            if not target or not target.get("id"):
                console.print(f"[red]Device '{device_identifier}' not found[/red]")
                console.print("[dim]Try: eero device list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            # Get full details
            with cli_ctx.status("Getting device details..."):
                raw_detail = await client.get_device(target["id"], cli_ctx.network_id)

            device = normalize_device(extract_data(raw_detail))

            if cli_ctx.is_structured_output():
                cli_ctx.render_structured(device, "eero.device.show/v1")
            elif cli_ctx.is_list_output():
                # Curated key-value output matching table fields
                from ..formatting.device import get_device_list_data

                list_data = get_device_list_data(device)
                for key, value in list_data.items():
                    print(f"{key}: {value if value is not None else '-'}")
            else:
                from ..formatting import print_device_details

                detail: Literal["brief", "full"] = (
                    "full" if cli_ctx.detail_level == "full" else "brief"
                )
                print_device_details(device, detail_level=detail)

        await run_with_client(get_device)

    asyncio.run(run_cmd())


@device_group.command(name="rename")
@click.argument("device_identifier")
@click.option("--name", required=True, help="New nickname for the device")
@network_option
@click.pass_context
def device_rename(
    ctx: click.Context, device_identifier: str, name: str, network_id: Optional[str]
) -> None:
    """Rename a device.

    \b
    Arguments:
      DEVICE_IDENTIFIER  Device ID, MAC address, or name

    \b
    Options:
      --name TEXT  New nickname (required)
    """
    cli_ctx = apply_options(ctx, network_id=network_id)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def rename_device(client: EeroClient) -> None:
            # Find device first
            with cli_ctx.status("Finding device..."):
                raw_response = await client.get_devices(cli_ctx.network_id)

            devices = extract_devices(raw_response)
            target = _find_device(devices, device_identifier)

            if not target or not target.get("id"):
                console.print(f"[red]Device '{device_identifier}' not found[/red]")
                console.print("[dim]Try: eero device list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            with cli_ctx.status(f"Renaming device to '{name}'..."):
                result = await client.set_device_nickname(target["id"], name, cli_ctx.network_id)

            # Check result
            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print(f"[bold green]Device renamed to '{name}'[/bold green]")
            else:
                console.print("[red]Failed to rename device[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(rename_device)

    asyncio.run(run_cmd())


@device_group.command(name="block")
@click.argument("device_identifier")
@force_option
@network_option
@click.pass_context
def device_block(
    ctx: click.Context, device_identifier: str, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Block a device from the network.

    \b
    Arguments:
      DEVICE_IDENTIFIER  Device ID, MAC address, or name
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    _set_device_blocked(cli_ctx, device_identifier, True)


@device_group.command(name="unblock")
@click.argument("device_identifier")
@force_option
@network_option
@click.pass_context
def device_unblock(
    ctx: click.Context, device_identifier: str, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Unblock a device.

    \b
    Arguments:
      DEVICE_IDENTIFIER  Device ID, MAC address, or name
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    _set_device_blocked(cli_ctx, device_identifier, False)


def _set_device_blocked(cli_ctx: EeroCliContext, device_identifier: str, blocked: bool) -> None:
    """Block or unblock a device."""
    console = cli_ctx.console
    action = "block" if blocked else "unblock"

    async def run_cmd() -> None:
        async def toggle_block(client: EeroClient) -> None:
            # Find device first
            with cli_ctx.status("Finding device..."):
                raw_response = await client.get_devices(cli_ctx.network_id)

            devices = extract_devices(raw_response)
            target = _find_device(devices, device_identifier)

            if not target or not target.get("id"):
                console.print(f"[red]Device '{device_identifier}' not found[/red]")
                console.print("[dim]Try: eero device list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            device_name = (
                target.get("display_name")
                or target.get("nickname")
                or target.get("hostname")
                or device_identifier
            )

            try:
                confirm_or_fail(
                    action=action,
                    target=device_name,
                    risk=OperationRisk.MEDIUM,
                    force=cli_ctx.force,
                    non_interactive=cli_ctx.non_interactive,
                    dry_run=cli_ctx.dry_run,
                    console=cli_ctx.console,
                )
            except SafetyError as e:
                cli_ctx.renderer.render_error(e.message)
                sys.exit(e.exit_code)

            with cli_ctx.status(f"{action.capitalize()}ing {device_name}..."):
                result = await client.block_device(target["id"], blocked, cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print(f"[bold green]Device {action}ed[/bold green]")
            else:
                console.print(f"[red]Failed to {action} device[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(toggle_block)

    asyncio.run(run_cmd())


# ==================== Priority Subcommand Group ====================


@device_group.group(name="priority")
@click.pass_context
def priority_group(ctx: click.Context) -> None:
    """Manage device bandwidth priority.

    \b
    Commands:
      show - Show priority status
      on   - Enable priority
      off  - Disable priority
    """
    pass


@priority_group.command(name="show")
@click.argument("device_identifier")
@output_option
@network_option
@click.pass_context
def priority_show(
    ctx: click.Context, device_identifier: str, output: Optional[str], network_id: Optional[str]
) -> None:
    """Show priority status for a device."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_priority(client: EeroClient) -> None:
            # Find device first
            with cli_ctx.status("Finding device..."):
                raw_response = await client.get_devices(cli_ctx.network_id)

            devices = extract_devices(raw_response)
            target = _find_device(devices, device_identifier)

            if not target or not target.get("id"):
                console.print(f"[red]Device '{device_identifier}' not found[/red]")
                console.print("[dim]Try: eero device list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            with cli_ctx.status("Getting priority status..."):
                raw_priority = await client.get_device_priority(target["id"], cli_ctx.network_id)

            priority_data = extract_data(raw_priority)

            if cli_ctx.is_json_output():
                renderer.render_json(priority_data, "eero.device.priority.show/v1")
            elif cli_ctx.is_list_output():
                renderer.render_text(priority_data, "eero.device.priority.show/v1")
            else:
                prioritized = priority_data.get("prioritized", False)
                duration = priority_data.get("duration", 0)

                content = (
                    f"[bold]Prioritized:[/bold] "
                    f"{'[green]Yes[/green]' if prioritized else '[dim]No[/dim]'}"
                )
                if prioritized and duration > 0:
                    content += f"\n[bold]Duration:[/bold] {duration} minutes"

                console.print(Panel(content, title="Priority Status", border_style="blue"))

        await run_with_client(get_priority)

    asyncio.run(run_cmd())


@priority_group.command(name="on")
@click.argument("device_identifier")
@click.option("--minutes", "-m", type=int, default=0, help="Duration in minutes (0=indefinite)")
@network_option
@click.pass_context
def priority_on(
    ctx: click.Context, device_identifier: str, minutes: int, network_id: Optional[str]
) -> None:
    """Enable priority for a device.

    \b
    Options:
      --minutes, -m  Duration (0=indefinite)
    """
    cli_ctx = apply_options(ctx, network_id=network_id)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def set_priority(client: EeroClient) -> None:
            # Find device first
            with cli_ctx.status("Finding device..."):
                raw_response = await client.get_devices(cli_ctx.network_id)

            devices = extract_devices(raw_response)
            target = _find_device(devices, device_identifier)

            if not target or not target.get("id"):
                console.print(f"[red]Device '{device_identifier}' not found[/red]")
                console.print("[dim]Try: eero device list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            duration_str = f" for {minutes} minutes" if minutes > 0 else " (indefinite)"
            with cli_ctx.status(f"Prioritizing device{duration_str}..."):
                # TODO: prioritize_device method not yet implemented in eero-api
                result = await client.prioritize_device(target["id"], minutes, cli_ctx.network_id)  # type: ignore[attr-defined]

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print(f"[bold green]Device prioritized{duration_str}[/bold green]")
            else:
                console.print("[red]Failed to prioritize device[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_priority)

    asyncio.run(run_cmd())


@priority_group.command(name="off")
@click.argument("device_identifier")
@network_option
@click.pass_context
def priority_off(ctx: click.Context, device_identifier: str, network_id: Optional[str]) -> None:
    """Remove priority from a device."""
    cli_ctx = apply_options(ctx, network_id=network_id)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def remove_priority(client: EeroClient) -> None:
            # Find device first
            with cli_ctx.status("Finding device..."):
                raw_response = await client.get_devices(cli_ctx.network_id)

            devices = extract_devices(raw_response)
            target = _find_device(devices, device_identifier)

            if not target or not target.get("id"):
                console.print(f"[red]Device '{device_identifier}' not found[/red]")
                console.print("[dim]Try: eero device list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            with cli_ctx.status("Removing priority..."):
                # TODO: deprioritize_device method not yet implemented in eero-api
                result = await client.deprioritize_device(target["id"], cli_ctx.network_id)  # type: ignore[attr-defined]

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print("[bold green]Priority removed[/bold green]")
            else:
                console.print("[red]Failed to remove priority[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(remove_priority)

    asyncio.run(run_cmd())
