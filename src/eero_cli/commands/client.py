"""Client (device) commands for the Eero CLI.

Commands:
- eero client list: List all connected devices
- eero client show: Show device details
- eero client rename: Rename a device
- eero client block: Block a device
- eero client unblock: Unblock a device
- eero client priority: Device priority management
"""

import asyncio
import sys
from typing import Literal

import click
from eero import EeroClient
from eero.const import EeroDeviceStatus
from rich.panel import Panel
from rich.table import Table

from ..context import EeroCliContext, ensure_cli_context, get_cli_context
from ..exit_codes import ExitCode
from ..output import OutputFormat
from ..safety import OperationRisk, SafetyError, confirm_or_fail
from ..utils import run_with_client


@click.group(name="client")
@click.pass_context
def client_group(ctx: click.Context) -> None:
    """Manage connected devices (clients).

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
      eero client list                    # List all devices
      eero client show "iPhone"           # Show by name
      eero client block AA:BB:CC:DD:EE:FF # Block by MAC
      eero client priority show "iPad"    # Show priority
    """
    ensure_cli_context(ctx)


@client_group.command(name="list")
@click.pass_context
def client_list(ctx: click.Context) -> None:
    """List all connected devices."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def get_devices(client: EeroClient) -> None:
            with console.status("Getting devices..."):
                devices = await client.get_devices(cli_ctx.network_id)

            if not devices:
                console.print("[yellow]No devices found[/yellow]")
                return

            if cli_ctx.is_structured_output():
                data = [d.model_dump(mode="json") for d in devices]
                cli_ctx.render_structured(data, "eero.client.list/v1")
            elif cli_ctx.output_format == OutputFormat.LIST:
                for d in devices:
                    name = d.display_name or d.hostname or d.nickname or "Unknown"
                    console.print(f"{d.id}\t{name}\t{d.ip or d.ipv4}\t{d.mac}")
            else:
                table = Table(title="Connected Devices")
                table.add_column("ID", style="dim")
                table.add_column("Name", style="cyan")
                table.add_column("IP", style="green")
                table.add_column("MAC", style="yellow")
                table.add_column("Status")
                table.add_column("Type")
                table.add_column("Connection")

                for d in devices:
                    name = d.display_name or d.hostname or d.nickname or "Unknown"

                    if d.status == EeroDeviceStatus.CONNECTED:
                        status = "[green]connected[/green]"
                    elif d.status == EeroDeviceStatus.BLOCKED:
                        status = "[red]blocked[/red]"
                    else:
                        status = "[yellow]disconnected[/yellow]"

                    table.add_row(
                        d.id or "",
                        name,
                        d.ip or d.ipv4 or "",
                        d.mac or "",
                        status,
                        d.device_type or "",
                        d.connection_type or "",
                    )

                console.print(table)

        await run_with_client(get_devices)

    asyncio.run(run_cmd())


@client_group.command(name="show")
@click.argument("client_id")
@click.pass_context
def client_show(ctx: click.Context, client_id: str) -> None:
    """Show details of a specific device.

    \b
    Arguments:
      CLIENT_ID  Device ID, MAC address, or name
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def get_device(client: EeroClient) -> None:
            with console.status("Getting devices..."):
                devices = await client.get_devices(cli_ctx.network_id)

            # Find device by ID, MAC, or name
            target = None
            for d in devices:
                if (
                    d.id == client_id
                    or d.mac == client_id
                    or d.display_name == client_id
                    or d.nickname == client_id
                    or d.hostname == client_id
                ):
                    target = d
                    break

            if not target or not target.id:
                console.print(f"[red]Device '{client_id}' not found[/red]")
                sys.exit(ExitCode.NOT_FOUND)

            # Get full details
            with console.status("Getting device details..."):
                device = await client.get_device(target.id, cli_ctx.network_id)

            if cli_ctx.is_structured_output():
                cli_ctx.render_structured(device.model_dump(mode="json"), "eero.client.show/v1")
            else:
                from ..formatting import print_device_details

                detail: Literal["brief", "full"] = (
                    "full" if cli_ctx.detail_level == "full" else "brief"
                )
                print_device_details(device, detail_level=detail)

        await run_with_client(get_device)

    asyncio.run(run_cmd())


@client_group.command(name="rename")
@click.argument("client_id")
@click.option("--name", required=True, help="New nickname for the device")
@click.pass_context
def client_rename(ctx: click.Context, client_id: str, name: str) -> None:
    """Rename a device.

    \b
    Arguments:
      CLIENT_ID  Device ID, MAC address, or name

    \b
    Options:
      --name TEXT  New nickname (required)
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def rename_device(client: EeroClient) -> None:
            # Find device first
            with console.status("Finding device..."):
                devices = await client.get_devices(cli_ctx.network_id)

            target = None
            for d in devices:
                if (
                    d.id == client_id
                    or d.mac == client_id
                    or d.display_name == client_id
                    or d.nickname == client_id
                ):
                    target = d
                    break

            if not target or not target.id:
                console.print(f"[red]Device '{client_id}' not found[/red]")
                sys.exit(ExitCode.NOT_FOUND)

            with console.status(f"Renaming device to '{name}'..."):
                result = await client.set_device_nickname(target.id, name, cli_ctx.network_id)

            if result:
                console.print(f"[bold green]Device renamed to '{name}'[/bold green]")
            else:
                console.print("[red]Failed to rename device[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(rename_device)

    asyncio.run(run_cmd())


@client_group.command(name="block")
@click.argument("client_id")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def client_block(ctx: click.Context, client_id: str, force: bool) -> None:
    """Block a device from the network.

    \b
    Arguments:
      CLIENT_ID  Device ID, MAC address, or name
    """
    cli_ctx = get_cli_context(ctx)
    _set_device_blocked(cli_ctx, client_id, True, force)


@client_group.command(name="unblock")
@click.argument("client_id")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def client_unblock(ctx: click.Context, client_id: str, force: bool) -> None:
    """Unblock a device.

    \b
    Arguments:
      CLIENT_ID  Device ID, MAC address, or name
    """
    cli_ctx = get_cli_context(ctx)
    _set_device_blocked(cli_ctx, client_id, False, force)


def _set_device_blocked(
    cli_ctx: EeroCliContext, client_id: str, blocked: bool, force: bool
) -> None:
    """Block or unblock a device."""
    console = cli_ctx.console
    action = "block" if blocked else "unblock"

    async def run_cmd() -> None:
        async def toggle_block(client: EeroClient) -> None:
            # Find device first
            with console.status("Finding device..."):
                devices = await client.get_devices(cli_ctx.network_id)

            target = None
            for d in devices:
                if (
                    d.id == client_id
                    or d.mac == client_id
                    or d.display_name == client_id
                    or d.nickname == client_id
                ):
                    target = d
                    break

            if not target or not target.id:
                console.print(f"[red]Device '{client_id}' not found[/red]")
                sys.exit(ExitCode.NOT_FOUND)

            device_name = target.display_name or target.nickname or target.hostname or client_id

            try:
                confirm_or_fail(
                    action=action,
                    target=device_name,
                    risk=OperationRisk.MEDIUM,
                    force=force or cli_ctx.force,
                    non_interactive=cli_ctx.non_interactive,
                    dry_run=cli_ctx.dry_run,
                    console=cli_ctx.console,
                )
            except SafetyError as e:
                cli_ctx.renderer.render_error(e.message)
                sys.exit(e.exit_code)

            with console.status(f"{action.capitalize()}ing {device_name}..."):
                result = await client.block_device(target.id, blocked, cli_ctx.network_id)

            if result:
                console.print(f"[bold green]Device {action}ed[/bold green]")
            else:
                console.print(f"[red]Failed to {action} device[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(toggle_block)

    asyncio.run(run_cmd())


# ==================== Priority Subcommand Group ====================


@client_group.group(name="priority")
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
@click.argument("client_id")
@click.pass_context
def priority_show(ctx: click.Context, client_id: str) -> None:
    """Show priority status for a device."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_priority(client: EeroClient) -> None:
            # Find device first
            with console.status("Finding device..."):
                devices = await client.get_devices(cli_ctx.network_id)

            target = None
            for d in devices:
                if (
                    d.id == client_id
                    or d.mac == client_id
                    or d.display_name == client_id
                    or d.nickname == client_id
                ):
                    target = d
                    break

            if not target or not target.id:
                console.print(f"[red]Device '{client_id}' not found[/red]")
                sys.exit(ExitCode.NOT_FOUND)

            with console.status("Getting priority status..."):
                priority_data = await client.get_device_priority(target.id, cli_ctx.network_id)

            if cli_ctx.is_json_output():
                renderer.render_json(priority_data, "eero.client.priority.show/v1")
            else:
                prioritized = priority_data.get("prioritized", False)
                duration = priority_data.get("duration", 0)

                content = f"[bold]Prioritized:[/bold] {'[green]Yes[/green]' if prioritized else '[dim]No[/dim]'}"
                if prioritized and duration > 0:
                    content += f"\n[bold]Duration:[/bold] {duration} minutes"

                console.print(Panel(content, title="Priority Status", border_style="blue"))

        await run_with_client(get_priority)

    asyncio.run(run_cmd())


@priority_group.command(name="on")
@click.argument("client_id")
@click.option("--minutes", "-m", type=int, default=0, help="Duration in minutes (0=indefinite)")
@click.pass_context
def priority_on(ctx: click.Context, client_id: str, minutes: int) -> None:
    """Enable priority for a device.

    \b
    Options:
      --minutes, -m  Duration (0=indefinite)
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def set_priority(client: EeroClient) -> None:
            # Find device first
            with console.status("Finding device..."):
                devices = await client.get_devices(cli_ctx.network_id)

            target = None
            for d in devices:
                if (
                    d.id == client_id
                    or d.mac == client_id
                    or d.display_name == client_id
                    or d.nickname == client_id
                ):
                    target = d
                    break

            if not target or not target.id:
                console.print(f"[red]Device '{client_id}' not found[/red]")
                sys.exit(ExitCode.NOT_FOUND)

            duration_str = f" for {minutes} minutes" if minutes > 0 else " (indefinite)"
            with console.status(f"Prioritizing device{duration_str}..."):
                result = await client.prioritize_device(target.id, minutes, cli_ctx.network_id)

            if result:
                console.print(f"[bold green]Device prioritized{duration_str}[/bold green]")
            else:
                console.print("[red]Failed to prioritize device[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_priority)

    asyncio.run(run_cmd())


@priority_group.command(name="off")
@click.argument("client_id")
@click.pass_context
def priority_off(ctx: click.Context, client_id: str) -> None:
    """Remove priority from a device."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def remove_priority(client: EeroClient) -> None:
            # Find device first
            with console.status("Finding device..."):
                devices = await client.get_devices(cli_ctx.network_id)

            target = None
            for d in devices:
                if (
                    d.id == client_id
                    or d.mac == client_id
                    or d.display_name == client_id
                    or d.nickname == client_id
                ):
                    target = d
                    break

            if not target or not target.id:
                console.print(f"[red]Device '{client_id}' not found[/red]")
                sys.exit(ExitCode.NOT_FOUND)

            with console.status("Removing priority..."):
                result = await client.deprioritize_device(target.id, cli_ctx.network_id)

            if result:
                console.print("[bold green]Priority removed[/bold green]")
            else:
                console.print("[red]Failed to remove priority[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(remove_priority)

    asyncio.run(run_cmd())
