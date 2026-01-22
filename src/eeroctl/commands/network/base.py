"""Base network commands for the Eero CLI.

Commands:
- eero network list: List all networks
- eero network use: Set preferred network
- eero network show: Show network details
- eero network rename: Rename network
- eero network premium: Check Eero Plus status
"""

import asyncio
import sys
from typing import Literal, Optional

import click
from eero import EeroClient
from rich.panel import Panel
from rich.table import Table

from ...context import ensure_cli_context, get_cli_context
from ...exit_codes import ExitCode
from ...options import apply_options, force_option, network_option, output_option
from ...output import OutputFormat
from ...safety import OperationRisk, SafetyError, confirm_or_fail
from ...transformers import extract_networks
from ...transformers.network import extract_network, normalize_network
from ...utils import run_with_client, set_preferred_network


@click.group(name="network")
@click.pass_context
def network_group(ctx: click.Context) -> None:
    """Manage network settings.

    \b
    Commands:
      list      - List all networks
      use       - Set preferred network
      show      - Show network details
      rename    - Rename network (SSID)
      premium   - Check Eero Plus status
      dns       - DNS settings
      security  - Security settings
      sqm       - SQM/QoS settings
      guest     - Guest network
      backup    - Backup network (Eero Plus)
      speedtest - Speed tests
      forwards  - Port forwarding
      dhcp      - DHCP settings
      routing   - Routing information
      thread    - Thread protocol
      support   - Support bundle

    \b
    Examples:
      eero network list              # List all networks
      eero network show              # Show current network
      eero network dns show          # Show DNS settings
      eero network guest enable      # Enable guest network
    """
    ensure_cli_context(ctx)


@network_group.command(name="list")
@output_option
@click.pass_context
def network_list(ctx: click.Context, output: Optional[str]) -> None:
    """List all networks.

    Shows all networks associated with your account.
    """
    cli_ctx = apply_options(ctx, output=output)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def get_networks(client: EeroClient) -> None:
            with cli_ctx.status("Getting networks..."):
                raw_response = await client.get_networks()

            # Extract and normalize networks from raw response
            networks = extract_networks(raw_response)
            normalized = [normalize_network(n) for n in networks]

            if not normalized:
                console.print("[yellow]No networks found[/yellow]")
                return

            if cli_ctx.is_structured_output():
                data = [
                    {
                        "id": n.get("id"),
                        "name": n.get("name"),
                        "status": n.get("status"),
                        "public_ip": n.get("public_ip"),
                        "isp_name": n.get("isp_name"),
                    }
                    for n in normalized
                ]
                cli_ctx.render_structured(data, "eero.network.list/v1")
            elif cli_ctx.output_format == OutputFormat.LIST:
                for n in normalized:
                    status = n.get("status", "unknown")
                    print(
                        f"{n.get('id', '') or '':<12}  {n.get('name', '') or '':<25}  "
                        f"{status:<15}  {n.get('public_ip') or 'N/A':<15}  "
                        f"{n.get('isp_name') or 'N/A'}"
                    )
            else:
                table = Table(title="Eero Networks")
                table.add_column("ID", style="dim")
                table.add_column("Name", style="cyan")
                table.add_column("Status", style="green")
                table.add_column("Public IP", style="blue")
                table.add_column("ISP", style="magenta")

                for n in normalized:
                    status = n.get("status", "unknown")
                    if "online" in status.lower() or "connected" in status.lower():
                        status_display = f"[green]{status}[/green]"
                    elif "offline" in status.lower():
                        status_display = f"[red]{status}[/red]"
                    else:
                        status_display = f"[yellow]{status}[/yellow]"

                    table.add_row(
                        n.get("id") or "",
                        n.get("name") or "",
                        status_display,
                        n.get("public_ip") or "N/A",
                        n.get("isp_name") or "N/A",
                    )

                console.print(table)

        await run_with_client(get_networks)

    asyncio.run(run_cmd())


@network_group.command(name="use")
@click.argument("network_id")
@click.pass_context
def network_use(ctx: click.Context, network_id: str) -> None:
    """Set preferred network for future commands.

    \b
    Arguments:
      NETWORK_ID  The network ID to use

    \b
    Examples:
      eero network use abc123
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def set_preferred(client: EeroClient) -> None:
            client.set_preferred_network(network_id)
            set_preferred_network(network_id)

            try:
                with cli_ctx.status(f"Verifying network {network_id}..."):
                    raw_response = await client.get_network(network_id)
                net = normalize_network(extract_network(raw_response))
                console.print(
                    f"[bold green]Preferred network set to '{net.get('name')}' "
                    f"({network_id})[/bold green]"
                )
            except Exception as e:
                console.print(
                    f"[yellow]Network ID set to {network_id}, but could not verify: {e}[/yellow]"
                )

        await run_with_client(set_preferred)

    asyncio.run(run_cmd())


@network_group.command(name="show")
@output_option
@network_option
@click.pass_context
def network_show(ctx: click.Context, output: Optional[str], network_id: Optional[str]) -> None:
    """Show current network details.

    Displays comprehensive information about the current network
    including settings, DHCP, and recent speed test results.
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_network(client: EeroClient) -> None:
            with cli_ctx.status("Getting network details..."):
                raw_response = await client.get_network(cli_ctx.network_id)

            network = normalize_network(extract_network(raw_response))

            if cli_ctx.is_structured_output():
                # Remove _raw for structured output
                output_data = {k: v for k, v in network.items() if k != "_raw"}
                cli_ctx.render_structured(output_data, "eero.network.show/v1")
            else:
                from ...formatting import print_network_details

                detail: Literal["brief", "full"] = (
                    "full" if cli_ctx.detail_level == "full" else "brief"
                )
                print_network_details(network, detail_level=detail)

        await run_with_client(get_network)

    asyncio.run(run_cmd())


@network_group.command(name="rename")
@click.option("--name", required=True, help="New network name (SSID)")
@force_option
@network_option
@click.pass_context
def network_rename(
    ctx: click.Context, name: str, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Rename the network (change SSID).

    Note: May require network restart to take effect.

    \b
    Options:
      --name TEXT  New network name (required)

    \b
    Examples:
      eero network rename --name "My Home WiFi"
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.console

    try:
        confirm_or_fail(
            action="rename network",
            target=f"to '{name}'",
            risk=OperationRisk.MEDIUM,
            force=cli_ctx.force,
            non_interactive=cli_ctx.non_interactive,
            dry_run=cli_ctx.dry_run,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_name(client: EeroClient) -> None:
            with cli_ctx.status(f"Renaming network to '{name}'..."):
                result = await client.set_network_name(name, cli_ctx.network_id)

            # Check if successful (raw response has meta.code)
            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            success = meta.get("code", 0) in (200, 201, 204)

            if success:
                console.print(f"[bold green]Network renamed to '{name}'[/bold green]")
                console.print("[dim]Note: Network restart may be required[/dim]")
            else:
                console.print("[bold red]Failed to rename network[/bold red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_name)

    asyncio.run(run_cmd())


@network_group.command(name="premium")
@output_option
@network_option
@click.pass_context
def network_premium(ctx: click.Context, output: Optional[str], network_id: Optional[str]) -> None:
    """Check Eero Plus subscription status.

    Shows whether Eero Plus/Secure is active and which
    features are available.
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def check_premium(client: EeroClient) -> None:
            with cli_ctx.status("Checking premium status..."):
                raw_response = await client.get_premium_status(cli_ctx.network_id)

            # Extract premium data from raw response
            premium_data = raw_response.get("data", {}) if isinstance(raw_response, dict) else {}

            # Determine if premium is active
            is_premium = premium_data.get("active", False) or premium_data.get("is_active", False)
            if not is_premium:
                # Check for subscription info
                subscription = premium_data.get("subscription", {})
                is_premium = subscription.get("status") == "active"

            if cli_ctx.is_json_output():
                renderer.render_json(
                    {**premium_data, "is_active": is_premium},
                    "eero.network.premium/v1",
                )
            else:
                status_style = "green" if is_premium else "yellow"
                status_text = "Active" if is_premium else "Not Active"

                content = f"[bold]Eero Plus:[/bold] [{status_style}]{status_text}[/{status_style}]"
                if "plan" in premium_data:
                    content += f"\n[bold]Plan:[/bold] {premium_data['plan']}"
                if "expires_at" in premium_data:
                    content += f"\n[bold]Expires:[/bold] {premium_data['expires_at']}"

                console.print(
                    Panel(
                        content,
                        title="Premium Status",
                        border_style="blue" if is_premium else "yellow",
                    )
                )

        await run_with_client(check_premium)

    asyncio.run(run_cmd())


# Import and register subcommand groups after network_group is defined
from .advanced import routing_show, support_group, thread_cmd_group  # noqa: E402
from .backup import backup_group  # noqa: E402
from .dhcp import dhcp_group  # noqa: E402
from .dns import dns_group  # noqa: E402
from .forwards import forwards_group  # noqa: E402
from .guest import guest_group  # noqa: E402
from .security import security_group  # noqa: E402
from .speedtest import speedtest_group  # noqa: E402
from .sqm import sqm_group  # noqa: E402

# Register all subcommand groups
network_group.add_command(dns_group)
network_group.add_command(security_group)
network_group.add_command(sqm_group)
network_group.add_command(guest_group)
network_group.add_command(backup_group)
network_group.add_command(speedtest_group)
network_group.add_command(forwards_group)
network_group.add_command(dhcp_group)
network_group.add_command(routing_show)
network_group.add_command(thread_cmd_group)
network_group.add_command(support_group)
