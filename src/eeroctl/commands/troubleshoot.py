"""Troubleshooting commands for the Eero CLI.

Commands:
- eero troubleshoot connectivity: Check connectivity
- eero troubleshoot ping: Ping a host
- eero troubleshoot trace: Traceroute to a host
- eero troubleshoot doctor: Run diagnostic checks
"""

from typing import Optional

import click
from eero import EeroClient
from rich.panel import Panel
from rich.table import Table

from ..context import ensure_cli_context
from ..options import apply_options, network_option, output_option
from ..transformers import (
    extract_data,
    extract_devices,
    extract_eeros,
    normalize_device,
    normalize_eero,
    normalize_network,
)
from ..utils import with_client


def _get_network_status(network: dict) -> str:
    """Extract status from network dict."""
    status = network.get("status", "unknown")
    if isinstance(status, dict):
        status = status.get("status", "unknown")
    return str(status).lower()


@click.group(name="troubleshoot")
@click.pass_context
def troubleshoot_group(ctx: click.Context) -> None:
    """Troubleshooting and diagnostics.

    \b
    Commands:
      connectivity - Check network connectivity
      ping         - Ping a target host
      trace        - Traceroute to target
      doctor       - Run diagnostic checks

    \b
    Examples:
      eero troubleshoot connectivity
      eero troubleshoot ping --target 8.8.8.8
      eero troubleshoot doctor
    """
    ensure_cli_context(ctx)


@troubleshoot_group.command(name="connectivity")
@output_option
@network_option
@click.pass_context
@with_client
async def troubleshoot_connectivity(
    ctx: click.Context, client: EeroClient, output: Optional[str], network_id: Optional[str]
) -> None:
    """Check network connectivity status."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console

    with cli_ctx.status("Checking connectivity..."):
        raw_network = await client.get_network(cli_ctx.network_id)
        raw_diagnostics = await client.get_diagnostics(cli_ctx.network_id)

    network = normalize_network(extract_data(raw_network))
    diagnostics = extract_data(raw_diagnostics) if isinstance(raw_diagnostics, dict) else {}

    if cli_ctx.is_structured_output():
        data = {
            "network_status": network.get("status"),
            "public_ip": network.get("public_ip"),
            "isp": network.get("isp_name"),
            "diagnostics": diagnostics,
        }
        cli_ctx.render_structured(data, "eero.troubleshoot.connectivity/v1")
    else:
        status = network.get("status", "unknown")
        if "online" in status.lower() or "connected" in status.lower():
            status_display = f"[green]{status}[/green]"
        elif "offline" in status.lower():
            status_display = f"[red]{status}[/red]"
        else:
            status_display = f"[yellow]{status}[/yellow]"

        content = (
            f"[bold]Status:[/bold] {status_display}\n"
            f"[bold]Public IP:[/bold] {network.get('public_ip') or 'N/A'}\n"
            f"[bold]ISP:[/bold] {network.get('isp_name') or 'N/A'}"
        )

        # Add health info if available
        health = network.get("health", {})
        if health and isinstance(health, dict):
            internet_status = health.get("internet", {}).get("status", "Unknown")
            content += f"\n[bold]Internet Status:[/bold] {internet_status}"

        console.print(Panel(content, title="Connectivity Status", border_style="blue"))


@troubleshoot_group.command(name="ping")
@click.option("--target", "-t", required=True, help="Target host or IP")
@click.option("--from", "from_eero", help="Eero node to ping from (ID or name)")
@output_option
@network_option
@click.pass_context
@with_client
async def troubleshoot_ping(
    ctx: click.Context,
    client: EeroClient,
    target: str,
    from_eero: Optional[str],
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Ping a target host.

    Note: This is a placeholder - actual ping functionality
    depends on Eero API support.

    \b
    Options:
      --target, -t  Target host or IP (required)
      --from        Eero node to ping from
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console

    console.print(
        "[yellow]Note: Direct ping functionality may not be available in Eero API[/yellow]"
    )
    console.print(f"[dim]Target: {target}[/dim]")
    if from_eero:
        console.print(f"[dim]From: {from_eero}[/dim]")

    with cli_ctx.status("Running diagnostics..."):
        raw_diagnostics = await client.get_diagnostics(cli_ctx.network_id)

    diagnostics = extract_data(raw_diagnostics) if isinstance(raw_diagnostics, dict) else {}

    if cli_ctx.is_structured_output():
        cli_ctx.render_structured(
            {
                "target": target,
                "from_eero": from_eero,
                "note": "Direct ping not available via API",
                "diagnostics": diagnostics,
            },
            "eero.troubleshoot.ping/v1",
        )
    else:
        console.print(
            Panel(
                f"[bold]Target:[/bold] {target}\n"
                f"[bold]From:[/bold] {from_eero or 'gateway'}\n\n"
                "[dim]Ping results would appear here if API supports it.[/dim]\n"
                "[dim]Use `eero troubleshoot doctor` for full diagnostics.[/dim]",
                title="Ping",
                border_style="blue",
            )
        )


@troubleshoot_group.command(name="trace")
@click.option("--target", "-t", required=True, help="Target host or IP")
@click.option("--from", "from_eero", help="Eero node to trace from (ID or name)")
@output_option
@network_option
@click.pass_context
@with_client
async def troubleshoot_trace(
    ctx: click.Context,
    client: EeroClient,
    target: str,
    from_eero: Optional[str],
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Traceroute to a target host.

    Note: This is a placeholder - actual traceroute functionality
    depends on Eero API support.

    \b
    Options:
      --target, -t  Target host or IP (required)
      --from        Eero node to trace from
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console

    console.print(
        "[yellow]Note: Direct traceroute functionality may not be available in Eero API[/yellow]"
    )
    console.print(f"[dim]Target: {target}[/dim]")

    with cli_ctx.status("Running diagnostics..."):
        _ = await client.get_diagnostics(cli_ctx.network_id)
        raw_routing = await client.get_routing(cli_ctx.network_id)

    routing = extract_data(raw_routing) if isinstance(raw_routing, dict) else {}

    if cli_ctx.is_structured_output():
        cli_ctx.render_structured(
            {
                "target": target,
                "from_eero": from_eero,
                "note": "Direct traceroute not available via API",
                "routing": routing,
            },
            "eero.troubleshoot.trace/v1",
        )
    else:
        console.print(
            Panel(
                f"[bold]Target:[/bold] {target}\n"
                f"[bold]From:[/bold] {from_eero or 'gateway'}\n\n"
                "[dim]Traceroute results would appear here if API supports it.[/dim]\n"
                "[dim]Use `eero network routing` for routing information.[/dim]",
                title="Traceroute",
                border_style="blue",
            )
        )


@troubleshoot_group.command(name="doctor")
@output_option
@network_option
@click.pass_context
@with_client
async def troubleshoot_doctor(
    ctx: click.Context, client: EeroClient, output: Optional[str], network_id: Optional[str]
) -> None:
    """Run diagnostic checks on the network.

    Performs a comprehensive health check of your Eero network
    including connectivity, mesh health, and configuration.
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console

    checks = []

    with cli_ctx.status("Running diagnostics..."):
        # Check network status
        try:
            raw_network = await client.get_network(cli_ctx.network_id)
            network = normalize_network(extract_data(raw_network))
            status = network.get("status", "unknown")
            if "online" in status.lower() or "connected" in status.lower():
                checks.append(("Network Status", "pass", status))
            else:
                checks.append(("Network Status", "fail", status))
        except Exception as e:
            checks.append(("Network Status", "fail", str(e)))

        # Check eeros
        try:
            raw_eeros = await client.get_eeros(cli_ctx.network_id)
            eeros = extract_eeros(raw_eeros)
            normalized_eeros = [normalize_eero(e) for e in eeros]
            online_count = sum(1 for e in normalized_eeros if e.get("status") == "green")
            total_count = len(normalized_eeros)
            if online_count == total_count:
                checks.append(("Mesh Nodes", "pass", f"{online_count}/{total_count} online"))
            elif online_count > 0:
                checks.append(("Mesh Nodes", "warn", f"{online_count}/{total_count} online"))
            else:
                checks.append(("Mesh Nodes", "fail", f"0/{total_count} online"))
        except Exception as e:
            checks.append(("Mesh Nodes", "fail", str(e)))

        # Check devices
        try:
            raw_devices = await client.get_devices(cli_ctx.network_id)
            devices = extract_devices(raw_devices)
            normalized_devices = [normalize_device(d) for d in devices]
            connected = sum(1 for d in normalized_devices if d.get("connected"))
            checks.append(("Connected Devices", "info", f"{connected} devices"))
        except Exception as e:
            checks.append(("Connected Devices", "warn", str(e)))

        # Check diagnostics
        try:
            _ = await client.get_diagnostics(cli_ctx.network_id)
            checks.append(("Diagnostics API", "pass", "Available"))
        except Exception:
            checks.append(("Diagnostics API", "warn", "Not available"))

        # Check premium status
        try:
            raw_premium = await client.is_premium(cli_ctx.network_id)
            is_premium = raw_premium if isinstance(raw_premium, bool) else False
            if isinstance(raw_premium, dict):
                is_premium = raw_premium.get("data", {}).get("premium", False)
            checks.append(("Eero Plus", "info", "Active" if is_premium else "Not active"))
        except Exception:
            checks.append(("Eero Plus", "info", "Unknown"))

    if cli_ctx.is_structured_output():
        data = {
            "checks": [
                {"name": name, "status": status, "message": msg} for name, status, msg in checks
            ],
            "overall": "pass" if all(s != "fail" for _, s, _ in checks) else "fail",
        }
        cli_ctx.render_structured(data, "eero.troubleshoot.doctor/v1")
    else:
        table = Table(title="Network Health Check")
        table.add_column("Check", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Details")

        for name, status, message in checks:
            if status == "pass":
                status_display = "[green]✓ PASS[/green]"
            elif status == "fail":
                status_display = "[red]✗ FAIL[/red]"
            elif status == "warn":
                status_display = "[yellow]⚠ WARN[/yellow]"
            else:
                status_display = "[blue]ℹ INFO[/blue]"

            table.add_row(name, status_display, message)

        console.print(table)

        # Overall status
        has_failures = any(s == "fail" for _, s, _ in checks)
        has_warnings = any(s == "warn" for _, s, _ in checks)

        if has_failures:
            console.print("\n[bold red]⚠ Issues detected. Review the checks above.[/bold red]")
        elif has_warnings:
            console.print("\n[bold yellow]⚠ Some warnings detected.[/bold yellow]")
        else:
            console.print("\n[bold green]✓ All checks passed![/bold green]")
