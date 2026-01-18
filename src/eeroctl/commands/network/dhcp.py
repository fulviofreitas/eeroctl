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
                reservations = await client.get_reservations(cli_ctx.network_id)

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
                devices = await client.get_devices(cli_ctx.network_id)

            if cli_ctx.is_json_output():
                data = [
                    {
                        "ip": d.ip or d.ipv4,
                        "mac": d.mac,
                        "hostname": d.hostname,
                        "name": d.display_name or d.nickname,
                    }
                    for d in devices
                    if d.ip or d.ipv4
                ]
                renderer.render_json(data, "eero.network.dhcp.leases/v1")
            else:
                table = Table(title="DHCP Leases")
                table.add_column("IP", style="green")
                table.add_column("MAC", style="yellow")
                table.add_column("Hostname", style="cyan")
                table.add_column("Name", style="blue")

                for d in devices:
                    if d.ip or d.ipv4:
                        table.add_row(
                            d.ip or d.ipv4 or "",
                            d.mac or "",
                            d.hostname or "",
                            d.display_name or d.nickname or "",
                        )

                console.print(table)

        await run_with_client(get_leases)

    asyncio.run(run_cmd())
