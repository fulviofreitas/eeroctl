"""Base Eero commands for the Eero CLI.

Commands:
- eero eero list: List all mesh nodes
- eero eero show: Show node details
- eero eero reboot: Reboot a node
"""

import asyncio
import sys
from typing import Any, Dict, Literal, Optional, Tuple

import click
from eero import EeroClient
from eero.exceptions import EeroException, EeroNotFoundException
from rich.table import Table

from ...context import ensure_cli_context
from ...exit_codes import ExitCode
from ...options import apply_options, force_option, network_option, output_option
from ...output import OutputFormat
from ...safety import OperationRisk, SafetyError, confirm_or_fail
from ...transformers import extract_data, extract_eeros, normalize_eero
from ...utils import run_with_client


async def resolve_eero_identifier(
    client: EeroClient,
    identifier: str,
    network_id: Optional[str],
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """Resolve an eero identifier (ID, serial, or name) to the actual eero ID.

    Args:
        client: EeroClient instance
        identifier: Eero ID, serial number, or name/location
        network_id: Network ID to search in

    Returns:
        Tuple of (resolved_id, normalized_eero_data) or (None, None) if not found
    """
    # First, check if identifier looks like a numeric ID
    if identifier.isdigit():
        # Try direct lookup by ID first
        try:
            raw_response = await client.get_eero(identifier, network_id)
            eero_data = normalize_eero(extract_data(raw_response))
            return identifier, eero_data
        except (EeroNotFoundException, EeroException):
            # Not a valid ID, continue to search by other fields
            pass

    # Fetch all eeros and search by name, location, or serial
    raw_eeros = await client.get_eeros(network_id)
    eeros = extract_eeros(raw_eeros)
    normalized = [normalize_eero(e) for e in eeros]

    identifier_lower = identifier.lower()

    for eero in normalized:
        # Match by serial (case-insensitive)
        serial = eero.get("serial") or ""
        if serial.lower() == identifier_lower:
            return eero.get("id"), eero

        # Match by name (case-insensitive)
        name = eero.get("name") or ""
        if name.lower() == identifier_lower:
            return eero.get("id"), eero

        # Match by location (case-insensitive)
        location = eero.get("location") or ""
        if location.lower() == identifier_lower:
            return eero.get("id"), eero

    # No match found
    return None, None


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
                raw_response = await client.get_eeros(cli_ctx.network_id)

            eeros = extract_eeros(raw_response)
            normalized = [normalize_eero(e) for e in eeros]

            if not normalized:
                console.print("[yellow]No Eero devices found[/yellow]")
                return

            if cli_ctx.is_structured_output():
                cli_ctx.render_structured(normalized, "eero.eero.list/v1")
            elif cli_ctx.output_format == OutputFormat.LIST:
                for e in normalized:
                    role = "Gateway" if e.get("is_gateway") else "Leaf"
                    name = e.get("name") or e.get("location") or ""
                    print(
                        f"{e.get('id') or '':<14}  {name:<20}  "
                        f"{e.get('model') or '':<15}  {e.get('ip_address') or '':<15}  "
                        f"{e.get('status') or '':<10}  {role:<8}  "
                        f"{e.get('connection_type') or ''}"
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

                for e in normalized:
                    status = e.get("status", "unknown")
                    status_color = "green" if status == "green" else "red"
                    role = "Gateway" if e.get("is_gateway") else "Leaf"
                    name = e.get("name") or e.get("location") or ""
                    table.add_row(
                        e.get("id") or "",
                        name,
                        e.get("model") or "",
                        e.get("ip_address") or "",
                        f"[{status_color}]{status}[/{status_color}]",
                        role,
                        e.get("connection_type") or "",
                    )

                console.print(table)

        await run_with_client(get_eeros)

    asyncio.run(run_cmd())


@eero_group.command(name="show")
@click.argument("eero_identifier")
@output_option
@network_option
@click.pass_context
def eero_show(
    ctx: click.Context, eero_identifier: str, output: Optional[str], network_id: Optional[str]
) -> None:
    """Show details of a specific Eero node.

    \b
    Arguments:
      EERO_IDENTIFIER  Node ID, serial number, or name/location
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def get_eero(client: EeroClient) -> None:
            with cli_ctx.status(f"Finding Eero '{eero_identifier}'..."):
                resolved_id, eero = await resolve_eero_identifier(
                    client, eero_identifier, cli_ctx.network_id
                )

            if not resolved_id or not eero:
                console.print(f"[red]Eero '{eero_identifier}' not found[/red]")
                console.print("[dim]Try: eero eero list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            if cli_ctx.is_structured_output():
                cli_ctx.render_structured(eero, "eero.eero.show/v1")
            else:
                from ...formatting import print_eero_details

                detail: Literal["brief", "full"] = (
                    "full" if cli_ctx.detail_level == "full" else "brief"
                )
                print_eero_details(eero, detail_level=detail)

        await run_with_client(get_eero)

    asyncio.run(run_cmd())


@eero_group.command(name="reboot")
@click.argument("eero_identifier")
@force_option
@network_option
@click.pass_context
def eero_reboot(
    ctx: click.Context, eero_identifier: str, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Reboot an Eero node.

    This is a disruptive operation that will temporarily
    disconnect clients connected to this node.

    \b
    Arguments:
      EERO_IDENTIFIER  Node ID, serial number, or name/location
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def reboot_eero(client: EeroClient) -> None:
            # Resolve the eero identifier to get its ID and name
            with cli_ctx.status(f"Finding Eero '{eero_identifier}'..."):
                resolved_id, eero = await resolve_eero_identifier(
                    client, eero_identifier, cli_ctx.network_id
                )

            if not resolved_id or not eero:
                console.print(f"[red]Eero '{eero_identifier}' not found[/red]")
                console.print("[dim]Try: eero eero list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            eero_name = (
                eero.get("name") or eero.get("location") or eero.get("serial") or eero_identifier
            )

            try:
                confirm_or_fail(
                    action="reboot",
                    target=eero_name,
                    risk=OperationRisk.MEDIUM,
                    force=cli_ctx.force,
                    non_interactive=cli_ctx.non_interactive,
                    dry_run=cli_ctx.dry_run,
                    console=cli_ctx.console,
                )
            except SafetyError as e:
                cli_ctx.renderer.render_error(e.message)
                sys.exit(e.exit_code)

            with cli_ctx.status(f"Rebooting {eero_name}..."):
                result = await client.reboot_eero(resolved_id, cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
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
