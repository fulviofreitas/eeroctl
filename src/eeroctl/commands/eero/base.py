"""Base Eero commands for the Eero CLI.

Commands:
- eero eero list: List all mesh nodes
- eero eero show: Show node details
- eero eero reboot: Reboot a node
"""

import asyncio
import sys
from typing import Literal, Optional

import click
from eero import EeroClient
from eero.exceptions import EeroException, EeroNotFoundException
from rich.table import Table

from ...context import ensure_cli_context
from ...errors import is_not_found_error
from ...exit_codes import ExitCode
from ...options import apply_options, network_option, output_option
from ...output import OutputFormat
from ...safety import OperationRisk, SafetyError, confirm_or_fail
from ...utils import run_with_client


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
@output_option
@network_option
@click.pass_context
def eero_list(ctx: click.Context, output: Optional[str], network_id: Optional[str]) -> None:
    """List all Eero mesh nodes."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def get_eeros(client: EeroClient) -> None:
            with cli_ctx.status("Getting Eero devices..."):
                eeros = await client.get_eeros(cli_ctx.network_id)

            if not eeros:
                console.print("[yellow]No Eero devices found[/yellow]")
                return

            if cli_ctx.is_structured_output():
                data = [e.model_dump(mode="json") for e in eeros]
                cli_ctx.render_structured(data, "eero.eero.list/v1")
            elif cli_ctx.output_format == OutputFormat.LIST:
                for e in eeros:
                    role = "Gateway" if e.gateway else "Leaf"
                    # Use print() with fixed-width columns for alignment
                    print(
                        f"{e.eero_id or '':<14}  {str(e.location) if e.location else '':<20}  "
                        f"{e.model or '':<15}  {e.ip_address or '':<15}  {e.status or '':<10}  "
                        f"{role:<8}  {e.connection_type or ''}"
                    )
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
@output_option
@network_option
@click.pass_context
def eero_show(
    ctx: click.Context, eero_id: str, output: Optional[str], network_id: Optional[str]
) -> None:
    """Show details of a specific Eero node.

    \b
    Arguments:
      EERO_ID  Node ID, serial, or location name
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def get_eero(client: EeroClient) -> None:
            with cli_ctx.status(f"Getting Eero '{eero_id}'..."):
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
                from ...formatting import print_eero_details

                detail: Literal["brief", "full"] = (
                    "full" if cli_ctx.detail_level == "full" else "brief"
                )
                print_eero_details(eero, detail_level=detail)

        await run_with_client(get_eero)

    asyncio.run(run_cmd())


@eero_group.command(name="reboot")
@click.argument("eero_id")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@network_option
@click.pass_context
def eero_reboot(ctx: click.Context, eero_id: str, force: bool, network_id: Optional[str]) -> None:
    """Reboot an Eero node.

    This is a disruptive operation that will temporarily
    disconnect clients connected to this node.

    \b
    Arguments:
      EERO_ID  Node ID, serial, or location name
    """
    cli_ctx = apply_options(ctx, network_id=network_id)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def reboot_eero(client: EeroClient) -> None:
            # First resolve the eero to get its name
            with cli_ctx.status(f"Finding Eero '{eero_id}'..."):
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

            with cli_ctx.status(f"Rebooting {eero_name}..."):
                result = await client.reboot_eero(eero.eero_id, cli_ctx.network_id)

            if result:
                console.print(f"[bold green]Reboot initiated for {eero_name}[/bold green]")
            else:
                console.print(f"[red]Failed to reboot {eero_name}[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(reboot_eero)

    asyncio.run(run_cmd())


# Import and register subcommand groups after eero_group is defined
from .led import led_group  # noqa: E402
from .nightlight import nightlight_group  # noqa: E402
from .updates import updates_group  # noqa: E402

# Register all subcommand groups
eero_group.add_command(led_group)
eero_group.add_command(nightlight_group)
eero_group.add_command(updates_group)
