"""DHCP commands for the Eero CLI.

Commands:
- eero network dhcp show: Show DHCP/lease/connection/wan-type read view
- eero network dhcp reservations: List DHCP reservations
- eero network dhcp leases: List current DHCP leases
"""

import asyncio
from typing import Optional

import click
from eero import EeroClient
from rich.table import Table

from ...context import get_cli_context
from ...options import apply_options, common_options
from ...transformers import extract_data, extract_devices, normalize_device
from ...transformers.network import extract_network, extract_network_dhcp_view
from ...utils import run_with_client


@click.group(name="dhcp")
@click.pass_context
def dhcp_group(ctx: click.Context) -> None:
    """Manage DHCP settings.

    \b
    Commands:
      show         - DHCP/lease/connection/wan-type read view
      reservations - List DHCP reservations
      leases       - List current DHCP leases
      reserve      - Create a reservation (stub)
      unreserve    - Remove a reservation (stub)
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
