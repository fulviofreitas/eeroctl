"""DHCP commands for the Eero CLI.

Commands:
- eero network dhcp reservations: List DHCP reservations
- eero network dhcp leases: List current DHCP leases
"""

import asyncio

import click
from eero import EeroClient
from rich.table import Table

from ...context import get_cli_context
from ...transformers import extract_data, extract_devices, normalize_device
from ...utils import run_with_client


@click.group(name="dhcp")
@click.pass_context
def dhcp_group(ctx: click.Context) -> None:
    """Manage DHCP settings.

    \b
    Commands:
      reservations - List DHCP reservations
      leases       - List current DHCP leases
      reserve      - Create a reservation (stub)
      unreserve    - Remove a reservation (stub)
    """
    pass


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
