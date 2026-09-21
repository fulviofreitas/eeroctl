"""DHCP commands for the Eero CLI.

Commands:
- eero network dhcp show: Show DHCP/lease/connection/wan-type read view
- eero network dhcp reservations: List DHCP reservations
- eero network dhcp leases: List current DHCP leases
- eero network dhcp reservation create: Create a reservation
- eero network dhcp reservation update: Update a reservation
- eero network dhcp reservation delete: Delete a reservation
- eero network dhcp set: Configure DHCP mode and custom lease ranges
- eero network dhcp connection-mode set: Set BRIDGE/NAT connection mode
- eero network dhcp nat-randomization: NAT port randomization
"""

import asyncio
import json
import sys
from typing import Any, Optional

import click
from eero import EeroClient
from rich.table import Table

from ...const import CONNECTION_MODES, DHCP_MODES
from ...context import get_cli_context
from ...exit_codes import ExitCode
from ...options import apply_options, common_options, force_option, network_option
from ...safety import SafetyContext, SafetyError, get_write_spec, require_write_confirmation
from ...transformers import extract_data, extract_devices, normalize_device
from ...transformers.network import extract_network, extract_network_dhcp_view
from ...utils import run_with_client


def _parse_config_json(console: Any, raw: str) -> dict:
    """Parse a `--config-json` option into a non-empty dict, or exit 2.

    `reservation_data` is typed as an opaque ``Dict[str, Any]`` with no
    documented shape (migration plan §4 phase C row 33); eeroctl accepts the
    caller's JSON object verbatim rather than guessing field names.
    """
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        console.print(f"[red]Invalid --config-json: {e}[/red]")
        sys.exit(ExitCode.USAGE_ERROR)
    if not isinstance(parsed, dict) or not parsed:
        console.print("[red]--config-json must be a non-empty JSON object[/red]")
        sys.exit(ExitCode.USAGE_ERROR)
    return parsed


@click.group(name="dhcp")
@click.pass_context
def dhcp_group(ctx: click.Context) -> None:
    """Manage DHCP settings.

    \b
    Commands:
      show              - DHCP/lease/connection/wan-type read view
      reservations      - List DHCP reservations
      leases            - List current DHCP leases
      reservation       - Create/update/delete a reservation
      set               - Configure DHCP mode and custom lease ranges
      connection-mode   - Set BRIDGE/NAT connection mode
      nat-randomization - NAT port randomization
    """
    pass


@dhcp_group.command(name="show")
@common_options
@click.pass_context
def dhcp_show(ctx: click.Context, output: Optional[str], network_id: Optional[str]) -> None:
    """Show DHCP, lease, connection, IP settings, and WAN type.

    No dedicated GET exists for this; the fields are read straight from the
    `get_network` envelope (migration plan §4, `network dhcp show` row).
    `dhcp reservations`/`dhcp leases` below are unchanged.
    """
    from ...formatting.network import print_network_dhcp_view

    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_dhcp_view(client: EeroClient) -> None:
            with cli_ctx.status("Getting network details..."):
                raw = await client.get_network(cli_ctx.network_id)
            print_network_dhcp_view(cli_ctx, extract_network_dhcp_view(extract_network(raw)))

        await run_with_client(get_dhcp_view)

    asyncio.run(run_cmd())


@dhcp_group.command(name="reservations")
@click.pass_context
def dhcp_reservations(ctx: click.Context) -> None:
    """List DHCP reservations."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_reservations(client: EeroClient) -> None:
            with cli_ctx.status("Getting DHCP reservations..."):
                raw_reservations = await client.get_reservations(cli_ctx.network_id)

            reservations = (
                extract_data(raw_reservations)
                if isinstance(raw_reservations, dict)
                else raw_reservations
            )
            if isinstance(reservations, dict):
                reservations = reservations.get("reservations", [])

            if cli_ctx.is_json_output():
                renderer.render_json(reservations, "eero.network.dhcp.reservations/v1")
            else:
                if not reservations:
                    console.print("[yellow]No DHCP reservations configured[/yellow]")
                    return

                table = Table(title="DHCP Reservations")
                table.add_column("MAC", style="yellow")
                table.add_column("IP", style="green")
                table.add_column("Hostname", style="cyan")

                for res in reservations:
                    table.add_row(
                        res.get("mac", ""),
                        res.get("ip", ""),
                        res.get("hostname", ""),
                    )

                console.print(table)

        await run_with_client(get_reservations)

    asyncio.run(run_cmd())


@dhcp_group.command(name="leases")
@click.pass_context
def dhcp_leases(ctx: click.Context) -> None:
    """List current DHCP leases."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_leases(client: EeroClient) -> None:
            with cli_ctx.status("Getting DHCP leases..."):
                # Leases come from devices list
                raw_devices = await client.get_devices(cli_ctx.network_id)

            devices = extract_devices(raw_devices)
            normalized = [normalize_device(d) for d in devices]

            if cli_ctx.is_json_output():
                data = [
                    {
                        "ip": d.get("ip") or d.get("ipv4"),
                        "mac": d.get("mac"),
                        "hostname": d.get("hostname"),
                        "name": d.get("display_name") or d.get("nickname"),
                    }
                    for d in normalized
                    if d.get("ip") or d.get("ipv4")
                ]
                renderer.render_json(data, "eero.network.dhcp.leases/v1")
            else:
                table = Table(title="DHCP Leases")
                table.add_column("IP", style="green")
                table.add_column("MAC", style="yellow")
                table.add_column("Hostname", style="cyan")
                table.add_column("Name", style="blue")

                for d in normalized:
                    if d.get("ip") or d.get("ipv4"):
                        table.add_row(
                            d.get("ip") or d.get("ipv4") or "",
                            d.get("mac") or "",
                            d.get("hostname") or "",
                            d.get("display_name") or d.get("nickname") or "",
                        )

                console.print(table)

        await run_with_client(get_leases)

    asyncio.run(run_cmd())


@dhcp_group.group(name="reservation")
@click.pass_context
def reservation_group(ctx: click.Context) -> None:
    """Create, update or delete a DHCP reservation.

    \b
    Commands:
      create - Create a reservation
      update - Update a reservation
      delete - Delete a reservation
    """
    pass


@reservation_group.command(name="create")
@click.option(
    "--config-json",
    required=True,
    help='Reservation definition as a JSON object, e.g. \'{"mac": "...", "ip": "..."}\'',
)
@force_option
@network_option
@click.pass_context
def reservation_create(
    ctx: click.Context, config_json: str, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Create a DHCP reservation.

    The shape of the reservation object is not documented by the SDK; pass
    exactly what the API expects via --config-json.
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.console
    reservation_data = _parse_config_json(console, config_json)

    spec = get_write_spec("network dhcp reservation create")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target="network",
            ctx=SafetyContext(
                force=cli_ctx.force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
            console=cli_ctx.console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def create(client: EeroClient) -> None:
            with cli_ctx.status("Creating DHCP reservation..."):
                result = await client.create_reservation(reservation_data, cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") in (200, 201) or result:
                console.print("[bold green]DHCP reservation created.[/bold green]")
                console.print(f"[dim]Verify with `{spec.read_command}`.[/dim]")
            else:
                console.print("[red]Failed to create DHCP reservation[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(create)

    asyncio.run(run_cmd())


@reservation_group.command(name="update")
@click.argument("reservation_id")
@click.option(
    "--config-json",
    required=True,
    help="Fields to update, as a JSON object (at least one field required)",
)
@force_option
@network_option
@click.pass_context
def reservation_update(
    ctx: click.Context,
    reservation_id: str,
    config_json: str,
    force: Optional[bool],
    network_id: Optional[str],
) -> None:
    """Update a DHCP reservation.

    \b
    Arguments:
      RESERVATION_ID  The reservation's id
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.console
    reservation_data = _parse_config_json(console, config_json)

    spec = get_write_spec("network dhcp reservation update")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target=reservation_id,
            ctx=SafetyContext(
                force=cli_ctx.force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
            console=cli_ctx.console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def update(client: EeroClient) -> None:
            with cli_ctx.status("Updating DHCP reservation..."):
                result = await client.update_reservation(
                    reservation_id, reservation_data, cli_ctx.network_id
                )

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print("[bold green]DHCP reservation updated.[/bold green]")
                console.print(f"[dim]Verify with `{spec.read_command}`.[/dim]")
            else:
                console.print("[red]Failed to update DHCP reservation[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(update)

    asyncio.run(run_cmd())


@reservation_group.command(name="delete")
@click.argument("reservation_id")
@click.option(
    "--delete-forwards/--keep-forwards",
    default=None,
    help="Also delete port forwards tied to this reservation.",
)
@force_option
@network_option
@click.pass_context
def reservation_delete(
    ctx: click.Context,
    reservation_id: str,
    delete_forwards: Optional[bool],
    force: Optional[bool],
    network_id: Optional[str],
) -> None:
    """Delete a DHCP reservation.

    \b
    Arguments:
      RESERVATION_ID  The reservation's id
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.console

    spec = get_write_spec("network dhcp reservation delete")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target=reservation_id,
            ctx=SafetyContext(
                force=cli_ctx.force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
            console=cli_ctx.console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def delete(client: EeroClient) -> None:
            with cli_ctx.status("Deleting DHCP reservation..."):
                result = await client.delete_reservation(
                    reservation_id,
                    cli_ctx.network_id,
                    delete_forwards=delete_forwards,
                )

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print("[bold green]DHCP reservation deleted.[/bold green]")
            else:
                console.print("[red]Failed to delete DHCP reservation[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(delete)

    asyncio.run(run_cmd())


@dhcp_group.command(name="set")
@click.option("--mode", type=click.Choice(DHCP_MODES), help="DHCP mode")
@click.option("--start-ip", help="Custom lease range start IP")
@click.option("--end-ip", help="Custom lease range end IP")
@click.option("--subnet-ip", help="Custom subnet IP")
@click.option("--subnet-mask", help="Custom subnet mask")
@click.option(
    "--config-json",
    help='Raw "custom_v2" object as JSON, for shapes the discrete flags do not cover',
)
@force_option
@network_option
@click.pass_context
def dhcp_set(
    ctx: click.Context,
    mode: Optional[str],
    start_ip: Optional[str],
    end_ip: Optional[str],
    subnet_ip: Optional[str],
    subnet_mask: Optional[str],
    config_json: Optional[str],
    force: Optional[bool],
    network_id: Optional[str],
) -> None:
    """Configure DHCP mode and/or custom lease ranges.

    Applying this change reboots every eero on the network. At least one of
    --mode, --start-ip/--end-ip/--subnet-ip/--subnet-mask, or --config-json
    is required.
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.console

    custom_fields = {
        k: v
        for k, v in {
            "start_ip": start_ip,
            "end_ip": end_ip,
            "subnet_ip": subnet_ip,
            "subnet_mask": subnet_mask,
        }.items()
        if v is not None
    }
    custom = custom_fields or None
    custom_v2 = _parse_config_json(console, config_json) if config_json is not None else None

    if mode is None and custom is None and custom_v2 is None:
        console.print(
            "[red]At least one of --mode, --start-ip/--end-ip/--subnet-ip/"
            "--subnet-mask, or --config-json is required[/red]"
        )
        sys.exit(ExitCode.USAGE_ERROR)

    spec = get_write_spec("network dhcp set")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target="network",
            ctx=SafetyContext(
                force=cli_ctx.force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
            console=cli_ctx.console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_dhcp(client: EeroClient) -> None:
            with cli_ctx.status("Configuring DHCP..."):
                result = await client.set_dhcp(
                    cli_ctx.network_id, mode=mode, custom=custom, custom_v2=custom_v2
                )

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print("[bold green]DHCP settings applied.[/bold green]")
                console.print(f"[dim]Verify with `{spec.read_command}`.[/dim]")
            else:
                console.print("[red]Failed to apply DHCP settings[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_dhcp)

    asyncio.run(run_cmd())


@dhcp_group.group(name="connection-mode")
@click.pass_context
def connection_mode_group(ctx: click.Context) -> None:
    """Manage the network's connection mode (BRIDGE/NAT).

    \b
    Commands:
      set - Set the connection mode
    """
    pass


@connection_mode_group.command(name="set")
@click.argument("mode", type=click.Choice(CONNECTION_MODES))
@force_option
@network_option
@click.pass_context
def connection_mode_set(
    ctx: click.Context, mode: str, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Set the network's connection mode.

    Applying this change reboots every eero on the network.

    \b
    Arguments:
      MODE  One of: BRIDGE, NAT
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.console

    spec = get_write_spec("network dhcp connection-mode set")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target=mode,
            ctx=SafetyContext(
                force=cli_ctx.force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
            console=cli_ctx.console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_mode(client: EeroClient) -> None:
            with cli_ctx.status(f"Setting connection mode to '{mode}'..."):
                result = await client.set_connection_mode(mode, cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print(f"[bold green]Connection mode set to '{mode}'.[/bold green]")
                console.print(f"[dim]Verify with `{spec.read_command}`.[/dim]")
            else:
                console.print("[red]Failed to set connection mode[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_mode)

    asyncio.run(run_cmd())


@dhcp_group.group(name="nat-randomization")
@click.pass_context
def nat_randomization_group(ctx: click.Context) -> None:
    """Manage NAT port randomization.

    \b
    Commands:
      enable  - Enable NAT port randomization
      disable - Disable NAT port randomization
    """
    pass


def _set_nat_randomization(cli_ctx, enable: bool, force: Optional[bool]) -> None:
    console = cli_ctx.console
    action = "enable" if enable else "disable"
    spec = get_write_spec(f"network dhcp nat-randomization {action}")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target="network",
            ctx=SafetyContext(
                force=cli_ctx.force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
            console=cli_ctx.console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_nat(client: EeroClient) -> None:
            with cli_ctx.status(f"{action.capitalize()}ing NAT port randomization..."):
                result = await client.set_nat_port_randomization(enable, cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print(f"[bold green]NAT port randomization {action}d.[/bold green]")
                console.print(f"[dim]Verify with `{spec.read_command}`.[/dim]")
            else:
                console.print(f"[red]Failed to {action} NAT port randomization[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_nat)

    asyncio.run(run_cmd())


@nat_randomization_group.command(name="enable")
@force_option
@network_option
@click.pass_context
def nat_randomization_enable(
    ctx: click.Context, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Enable NAT port randomization.

    Applying this change reboots every eero on the network.
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    _set_nat_randomization(cli_ctx, True, force)


@nat_randomization_group.command(name="disable")
@force_option
@network_option
@click.pass_context
def nat_randomization_disable(
    ctx: click.Context, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Disable NAT port randomization.

    Applying this change reboots every eero on the network.
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    _set_nat_randomization(cli_ctx, False, force)
