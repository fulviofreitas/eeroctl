"""Device (connected device) commands for the Eero CLI.

Commands:
- eero device list: List all connected devices
- eero device show: Show device details
- eero device rename: Rename a device
- eero device type set: Set a device's type
- eero device block: Block a device
- eero device unblock: Unblock a device
- eero device pause: Pause a device
- eero device unpause: Unpause a device
"""

import asyncio
import sys
from typing import Any, Dict, Literal, Optional

import click
from eero import EeroClient
from eero.exceptions import EeroNotFoundException
from rich.table import Table

from ..context import EeroCliContext, ensure_cli_context
from ..exit_codes import ExitCode
from ..options import apply_options, common_options, force_option, network_option, output_option
from ..output import OutputFormat
from ..safety import SafetyContext, SafetyError, get_write_spec, require_write_confirmation
from ..transformers import extract_data, extract_devices, normalize_device
from ..utils import looks_like_sdk_reference, run_with_client, write_if_changed


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
      list    - List all connected devices
      show    - Show device details
      rename  - Rename a device
      type    - Manage a device's type
      block   - Block a device
      unblock - Unblock a device
      pause   - Pause a device
      unpause - Unpause a device
      labels  - Device labels (read only)

    \b
    Examples:
      eero device list                    # List all devices
      eero device show "iPhone"           # Show by name
      eero device block AA:BB:CC:DD:EE:FF # Block by MAC
      eero device pause "iPad"            # Pause a device
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
            # A path/URL/hostile-shaped identifier goes straight to the
            # id-validated SDK method, verbatim -- never pre-validated here
            # (migration plan §2.5 decision 2). `EeroValidationException` is
            # deliberately not caught: it propagates to `run_with_client` and
            # maps to exit 2. Only a well-shaped-but-absent id/path/URL
            # (`EeroNotFoundException`, or an empty envelope) falls through
            # to "not found"; plain names/serials/MACs skip straight to the
            # existing list-and-match resolution below.
            device: Optional[Dict[str, Any]] = None
            if looks_like_sdk_reference(device_identifier):
                with cli_ctx.status("Getting device details..."):
                    try:
                        raw_detail = await client.get_device(device_identifier, cli_ctx.network_id)
                    except EeroNotFoundException:
                        raw_detail = None

                data = extract_data(raw_detail) if isinstance(raw_detail, dict) else None
                if isinstance(data, dict) and data:
                    device = normalize_device(data)

                if device is None:
                    console.print(f"[red]Device '{device_identifier}' not found[/red]")
                    console.print("[dim]Try: eero device list[/dim]")
                    sys.exit(ExitCode.NOT_FOUND)
            else:
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
    spec = get_write_spec("device rename")
    cli_ctx.active_write_spec = spec

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

            try:
                require_write_confirmation(
                    spec,
                    target=f"{device_identifier} → {name}",
                    ctx=SafetyContext(
                        force=cli_ctx.force,
                        non_interactive=cli_ctx.non_interactive,
                        dry_run=cli_ctx.dry_run,
                    ),
                    console=cli_ctx.err_console,
                )
            except SafetyError as e:
                cli_ctx.renderer.render_error(e.message)
                sys.exit(e.exit_code)

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


@device_group.group(name="type")
@click.pass_context
def device_type_group(ctx: click.Context) -> None:
    """Manage a device's type.

    \b
    Commands:
      set  - Set a device's type
    """
    pass


@device_type_group.command(name="set")
@click.argument("device_identifier")
@click.argument("device_type")
@force_option
@network_option
@click.pass_context
def device_type_set(
    ctx: click.Context,
    device_identifier: str,
    device_type: str,
    force: Optional[bool],
    network_id: Optional[str],
) -> None:
    """Set a device's type.

    \b
    Arguments:
      DEVICE_IDENTIFIER  Device ID, MAC address, or name
      DEVICE_TYPE        The new device type
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.console
    spec = get_write_spec("device type set")
    cli_ctx.active_write_spec = spec

    async def run_cmd() -> None:
        async def set_type(client: EeroClient) -> None:
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
                require_write_confirmation(
                    spec,
                    target=device_name,
                    ctx=SafetyContext(
                        force=cli_ctx.force,
                        non_interactive=cli_ctx.non_interactive,
                        dry_run=cli_ctx.dry_run,
                    ),
                    console=cli_ctx.err_console,
                )
            except SafetyError as e:
                cli_ctx.renderer.render_error(e.message)
                sys.exit(e.exit_code)

            # Already fetched above (target["device_type"]), so no extra read
            # round-trip is needed for the skip-unchanged check.
            async def read() -> str:
                return target.get("device_type") or ""

            async def write() -> Any:
                with cli_ctx.status(f"Setting device type to '{device_type}'..."):
                    return await client.set_device_type(
                        target["id"], device_type, cli_ctx.network_id
                    )

            await write_if_changed(
                read,
                device_type,
                write,
                force=cli_ctx.force,
                console=cli_ctx.err_console,
                read_command=spec.read_command,
            )

        await run_with_client(set_type)

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
    spec = get_write_spec(f"device {action}")
    cli_ctx.active_write_spec = spec

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
                require_write_confirmation(
                    spec,
                    target=device_name,
                    ctx=SafetyContext(
                        force=cli_ctx.force,
                        non_interactive=cli_ctx.non_interactive,
                        dry_run=cli_ctx.dry_run,
                    ),
                    console=cli_ctx.err_console,
                )
            except SafetyError as e:
                cli_ctx.renderer.render_error(e.message)
                sys.exit(e.exit_code)

            # Already fetched above (target["blacklisted"]), so no extra read
            # round-trip is needed for the skip-unchanged check.
            async def read() -> bool:
                return bool(target.get("blacklisted", not blocked))

            async def write() -> Any:
                with cli_ctx.status(f"{action.capitalize()}ing {device_name}..."):
                    if blocked:
                        return await client.block_device(target["id"], cli_ctx.network_id)
                    return await client.unblock_device(target["id"], cli_ctx.network_id)

            await write_if_changed(
                read,
                blocked,
                write,
                force=cli_ctx.force,
                console=cli_ctx.err_console,
                read_command=spec.read_command,
            )

        await run_with_client(toggle_block)

    asyncio.run(run_cmd())


@device_group.command(name="pause")
@click.argument("device_identifier")
@force_option
@network_option
@click.pass_context
def device_pause(
    ctx: click.Context, device_identifier: str, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Pause a device's internet access.

    \b
    Arguments:
      DEVICE_IDENTIFIER  Device ID, MAC address, or name
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    _set_device_paused(cli_ctx, device_identifier, True)


@device_group.command(name="unpause")
@click.argument("device_identifier")
@force_option
@network_option
@click.pass_context
def device_unpause(
    ctx: click.Context, device_identifier: str, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Unpause a device's internet access.

    \b
    Arguments:
      DEVICE_IDENTIFIER  Device ID, MAC address, or name
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    _set_device_paused(cli_ctx, device_identifier, False)


def _set_device_paused(cli_ctx: EeroCliContext, device_identifier: str, paused: bool) -> None:
    """Pause or unpause a device."""
    console = cli_ctx.console
    action = "pause" if paused else "unpause"
    spec = get_write_spec(f"device {action}")
    cli_ctx.active_write_spec = spec

    async def run_cmd() -> None:
        async def toggle_pause(client: EeroClient) -> None:
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
                require_write_confirmation(
                    spec,
                    target=device_name,
                    ctx=SafetyContext(
                        force=cli_ctx.force,
                        non_interactive=cli_ctx.non_interactive,
                        dry_run=cli_ctx.dry_run,
                    ),
                    console=cli_ctx.err_console,
                )
            except SafetyError as e:
                cli_ctx.renderer.render_error(e.message)
                sys.exit(e.exit_code)

            # Already fetched above (target["paused"]), so no extra read
            # round-trip is needed for the skip-unchanged check.
            async def read() -> bool:
                return bool(target.get("paused", not paused))

            async def write() -> Any:
                with cli_ctx.status(f"{action.capitalize()}ing {device_name}..."):
                    return await client.pause_device(target["id"], paused, cli_ctx.network_id)

            await write_if_changed(
                read,
                paused,
                write,
                force=cli_ctx.force,
                console=cli_ctx.err_console,
                read_command=spec.read_command,
            )

        await run_with_client(toggle_pause)

    asyncio.run(run_cmd())


# ==================== Device Labels (read-only) ====================
#
# get_device_labels (client.py:879) is a plain GET; set_device_labels is a
# documented no-op write (HTTP 200, never applies -- api/devices.py:381-387,
# migration plan §3.2), so there is no `device labels set` command.


@device_group.group(name="labels")
@click.pass_context
def device_labels_group(ctx: click.Context) -> None:
    """View device labels.

    \b
    Commands:
      show <device-identifier> - Show a device's labels
    """
    pass


@device_labels_group.command(name="show")
@click.argument("device_identifier")
@common_options
@click.pass_context
def device_labels_show(
    ctx: click.Context,
    device_identifier: str,
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Show a device's labels.

    \b
    Arguments:
      DEVICE_IDENTIFIER  Device ID, MAC address, or name
    """
    from ..formatting.generic import render_generic

    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def get_labels(client: EeroClient) -> None:
            with cli_ctx.status("Finding device..."):
                raw_devices = await client.get_devices(cli_ctx.network_id)

            devices = extract_devices(raw_devices)
            target = _find_device(devices, device_identifier)

            if not target or not target.get("id"):
                console.print(f"[red]Device '{device_identifier}' not found[/red]")
                console.print("[dim]Try: eero device list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            with cli_ctx.status("Getting device labels..."):
                raw = await client.get_device_labels(target["id"], cli_ctx.network_id)

            render_generic(cli_ctx, extract_data(raw), "eero.device.labels.show/v1")

        await run_with_client(get_labels)

    asyncio.run(run_cmd())
