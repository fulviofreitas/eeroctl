"""Network commands for the Eero CLI.

Commands:
- eero network list: List all networks
- eero network use: Set preferred network
- eero network show: Show network details
- eero network rename: Rename network
- eero network premium: Check Eero Plus status
- eero network dns: DNS management
- eero network security: Security settings
- eero network sqm: SQM/QoS settings
- eero network guest: Guest network
- eero network backup: Backup network
- eero network speedtest: Speed tests
- eero network forwards: Port forwarding
- eero network dhcp: DHCP management
- eero network routing: Routing info
- eero network thread: Thread info
- eero network support: Support/diagnostics
"""

import asyncio
import json
import sys
from typing import Literal, Optional

import click
from eero import EeroClient
from rich.panel import Panel
from rich.table import Table

from ..context import EeroCliContext, ensure_cli_context, get_cli_context
from ..errors import is_premium_error
from ..exit_codes import ExitCode
from ..output import OutputFormat
from ..safety import OperationRisk, SafetyError, confirm_or_fail
from ..utils import run_with_client, set_preferred_network


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
@click.pass_context
def network_list(ctx: click.Context) -> None:
    """List all networks.

    Shows all networks associated with your account.
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def get_networks(client: EeroClient) -> None:
            with cli_ctx.status("Getting networks..."):
                networks = await client.get_networks()

            if not networks:
                console.print("[yellow]No networks found[/yellow]")
                return

            if cli_ctx.is_structured_output():
                data = [
                    {
                        "id": n.id,
                        "name": n.name,
                        "status": n.status.name if n.status else None,
                        "public_ip": n.public_ip,
                        "isp_name": n.isp_name,
                    }
                    for n in networks
                ]
                cli_ctx.render_structured(data, "eero.network.list/v1")
            elif cli_ctx.output_format == OutputFormat.LIST:
                for n in networks:
                    # Extract just the enum name (e.g., "ONLINE" from EeroNetworkStatus.ONLINE)
                    status = n.status.name if n.status else ""
                    # Use print() with fixed-width columns for alignment
                    print(
                        f"{n.id or '':<12}  {n.name or '':<25}  {status:<15}  "
                        f"{n.public_ip or 'N/A':<15}  {n.isp_name or 'N/A'}"
                    )
            else:
                table = Table(title="Eero Networks")
                table.add_column("ID", style="dim")
                table.add_column("Name", style="cyan")
                table.add_column("Status", style="green")
                table.add_column("Public IP", style="blue")
                table.add_column("ISP", style="magenta")

                for n in networks:
                    # Extract just the enum name (e.g., "ONLINE" from EeroNetworkStatus.ONLINE)
                    status = n.status.name if n.status else ""
                    if "online" in status.lower() or "connected" in status.lower():
                        status_display = f"[green]{status}[/green]"
                    elif "offline" in status.lower():
                        status_display = f"[red]{status}[/red]"
                    else:
                        status_display = f"[yellow]{status}[/yellow]"

                    table.add_row(
                        n.id or "",
                        n.name or "",
                        status_display,
                        n.public_ip or "N/A",
                        n.isp_name or "N/A",
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
                    net = await client.get_network(network_id)
                console.print(
                    f"[bold green]Preferred network set to '{net.name}' ({network_id})[/bold green]"
                )
            except Exception as e:
                console.print(
                    f"[yellow]Network ID set to {network_id}, but could not verify: {e}[/yellow]"
                )

        await run_with_client(set_preferred)

    asyncio.run(run_cmd())


@network_group.command(name="show")
@click.pass_context
def network_show(ctx: click.Context) -> None:
    """Show current network details.

    Displays comprehensive information about the current network
    including settings, DHCP, and recent speed test results.
    """
    cli_ctx = get_cli_context(ctx)

    async def run_cmd() -> None:
        async def get_network(client: EeroClient) -> None:
            with cli_ctx.status("Getting network details..."):
                network = await client.get_network(cli_ctx.network_id)

            if cli_ctx.is_structured_output():
                cli_ctx.render_structured(
                    network.model_dump(mode="json"),
                    "eero.network.show/v1",
                )
            else:
                from ..formatting import print_network_details

                detail: Literal["brief", "full"] = (
                    "full" if cli_ctx.detail_level == "full" else "brief"
                )
                print_network_details(network, detail_level=detail)

        await run_with_client(get_network)

    asyncio.run(run_cmd())


@network_group.command(name="rename")
@click.option("--name", required=True, help="New network name (SSID)")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def network_rename(ctx: click.Context, name: str, force: bool) -> None:
    """Rename the network (change SSID).

    Note: May require network restart to take effect.

    \b
    Options:
      --name TEXT  New network name (required)

    \b
    Examples:
      eero network rename --name "My Home WiFi"
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    try:
        confirm_or_fail(
            action="rename network",
            target=f"to '{name}'",
            risk=OperationRisk.MEDIUM,
            force=force or cli_ctx.force,
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

            if result:
                console.print(f"[bold green]Network renamed to '{name}'[/bold green]")
                console.print("[dim]Note: Network restart may be required[/dim]")
            else:
                console.print("[bold red]Failed to rename network[/bold red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_name)

    asyncio.run(run_cmd())


@network_group.command(name="premium")
@click.pass_context
def network_premium(ctx: click.Context) -> None:
    """Check Eero Plus subscription status.

    Shows whether Eero Plus/Secure is active and which
    features are available.
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def check_premium(client: EeroClient) -> None:
            with cli_ctx.status("Checking premium status..."):
                premium_data = await client.get_premium_status(cli_ctx.network_id)
                is_premium = await client.is_premium(cli_ctx.network_id)

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


# ==================== DNS Subcommand Group ====================


@network_group.group(name="dns")
@click.pass_context
def dns_group(ctx: click.Context) -> None:
    """Manage DNS settings.

    \b
    Commands:
      show       - Show current DNS settings
      mode       - Set DNS mode
      caching    - Enable/disable DNS caching

    \b
    Examples:
      eero network dns show
      eero network dns mode set google
      eero network dns caching enable
    """
    pass


@dns_group.command(name="show")
@click.pass_context
def dns_show(ctx: click.Context) -> None:
    """Show current DNS settings."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_dns(client: EeroClient) -> None:
            with cli_ctx.status("Getting DNS settings..."):
                dns_data = await client.get_dns_settings(cli_ctx.network_id)

            if cli_ctx.is_json_output():
                renderer.render_json(dns_data, "eero.network.dns.show/v1")
            else:
                caching = dns_data.get("dns_caching", False)
                mode = dns_data.get("dns_mode", "auto")
                custom_dns = dns_data.get("custom_dns", [])

                content = (
                    f"[bold]DNS Mode:[/bold] {mode}\n"
                    f"[bold]DNS Caching:[/bold] {'[green]Enabled[/green]' if caching else '[dim]Disabled[/dim]'}"
                )
                if custom_dns:
                    content += f"\n[bold]Custom DNS:[/bold] {', '.join(custom_dns)}"

                console.print(Panel(content, title="DNS Settings", border_style="blue"))

        await run_with_client(get_dns)

    asyncio.run(run_cmd())


@dns_group.group(name="mode")
@click.pass_context
def dns_mode_group(ctx: click.Context) -> None:
    """Set DNS mode."""
    pass


@dns_mode_group.command(name="set")
@click.argument("mode", type=click.Choice(["auto", "cloudflare", "google", "opendns", "custom"]))
@click.option("--servers", "-s", multiple=True, help="Custom DNS servers (for 'custom' mode)")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def dns_mode_set(ctx: click.Context, mode: str, servers: tuple, force: bool) -> None:
    """Set DNS mode.

    \b
    Modes:
      auto       - Use ISP DNS
      cloudflare - Use Cloudflare (1.1.1.1)
      google     - Use Google (8.8.8.8)
      opendns    - Use OpenDNS
      custom     - Use custom servers (requires --servers)

    \b
    Examples:
      eero network dns mode set google
      eero network dns mode set custom --servers 8.8.8.8 --servers 8.8.4.4
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    if mode == "custom" and not servers:
        console.print("[red]Error: --servers required for custom mode[/red]")
        sys.exit(ExitCode.USAGE_ERROR)

    try:
        confirm_or_fail(
            action="change DNS mode",
            target=f"to {mode}",
            risk=OperationRisk.MEDIUM,
            force=force or cli_ctx.force,
            non_interactive=cli_ctx.non_interactive,
            dry_run=cli_ctx.dry_run,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_mode(client: EeroClient) -> None:
            custom_servers = list(servers) if servers else None
            with cli_ctx.status(f"Setting DNS mode to {mode}..."):
                result = await client.set_dns_mode(mode, custom_servers, cli_ctx.network_id)

            if result:
                console.print(f"[bold green]DNS mode set to {mode}[/bold green]")
            else:
                console.print("[red]Failed to set DNS mode[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_mode)

    asyncio.run(run_cmd())


@dns_group.group(name="caching")
@click.pass_context
def dns_caching_group(ctx: click.Context) -> None:
    """Manage DNS caching."""
    pass


@dns_caching_group.command(name="enable")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def dns_caching_enable(ctx: click.Context, force: bool) -> None:
    """Enable DNS caching."""
    cli_ctx = get_cli_context(ctx)
    _set_dns_caching(cli_ctx, True, force)


@dns_caching_group.command(name="disable")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def dns_caching_disable(ctx: click.Context, force: bool) -> None:
    """Disable DNS caching."""
    cli_ctx = get_cli_context(ctx)
    _set_dns_caching(cli_ctx, False, force)


def _set_dns_caching(cli_ctx: EeroCliContext, enable: bool, force: bool) -> None:
    """Set DNS caching state."""
    console = cli_ctx.console
    action = "enable" if enable else "disable"

    try:
        confirm_or_fail(
            action=f"{action} DNS caching",
            target="network",
            risk=OperationRisk.MEDIUM,
            force=force or cli_ctx.force,
            non_interactive=cli_ctx.non_interactive,
            dry_run=cli_ctx.dry_run,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_caching(client: EeroClient) -> None:
            with cli_ctx.status(f"{action.capitalize()}ing DNS caching..."):
                result = await client.set_dns_caching(enable, cli_ctx.network_id)

            if result:
                console.print(f"[bold green]DNS caching {action}d[/bold green]")
            else:
                console.print(f"[red]Failed to {action} DNS caching[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_caching)

    asyncio.run(run_cmd())


# ==================== Security Subcommand Group ====================


@network_group.group(name="security")
@click.pass_context
def security_group(ctx: click.Context) -> None:
    """Manage security settings.

    \b
    Commands:
      show           - Show security settings
      wpa3           - WPA3 encryption
      band-steering  - Band steering
      upnp           - UPnP
      ipv6           - IPv6
      thread         - Thread protocol

    \b
    Examples:
      eero network security show
      eero network security wpa3 enable
      eero network security upnp disable
    """
    pass


@security_group.command(name="show")
@click.pass_context
def security_show(ctx: click.Context) -> None:
    """Show security settings."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_security(client: EeroClient) -> None:
            with cli_ctx.status("Getting security settings..."):
                sec_data = await client.get_security_settings(cli_ctx.network_id)

            if cli_ctx.is_json_output():
                renderer.render_json(sec_data, "eero.network.security.show/v1")
            else:
                table = Table(title="Security Settings")
                table.add_column("Setting", style="cyan")
                table.add_column("Status", justify="center")

                settings = [
                    ("WPA3", sec_data.get("wpa3", False)),
                    ("Band Steering", sec_data.get("band_steering", True)),
                    ("UPnP", sec_data.get("upnp", True)),
                    ("IPv6", sec_data.get("ipv6_upstream", False)),
                    ("Thread", sec_data.get("thread", False)),
                ]

                for name, enabled in settings:
                    status = "[green]Enabled[/green]" if enabled else "[dim]Disabled[/dim]"
                    table.add_row(name, status)

                console.print(table)

        await run_with_client(get_security)

    asyncio.run(run_cmd())


# Security toggle commands
def _make_security_toggle(setting_name: str, api_method: str, display_name: str):
    """Factory for security toggle command groups."""

    @click.group(name=setting_name)
    @click.pass_context
    def toggle_group(ctx: click.Context) -> None:
        pass

    @toggle_group.command(name="enable")
    @click.option("--force", "-f", is_flag=True, help="Skip confirmation")
    @click.pass_context
    def enable_cmd(ctx: click.Context, force: bool) -> None:
        _set_security_setting(ctx, api_method, display_name, True, force)

    @toggle_group.command(name="disable")
    @click.option("--force", "-f", is_flag=True, help="Skip confirmation")
    @click.pass_context
    def disable_cmd(ctx: click.Context, force: bool) -> None:
        _set_security_setting(ctx, api_method, display_name, False, force)

    enable_cmd.__doc__ = f"Enable {display_name}."
    disable_cmd.__doc__ = f"Disable {display_name}."
    toggle_group.__doc__ = f"Manage {display_name}."

    return toggle_group


def _set_security_setting(ctx, api_method: str, display_name: str, enable: bool, force: bool):
    """Set a security setting."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    action = "enable" if enable else "disable"

    try:
        confirm_or_fail(
            action=f"{action} {display_name}",
            target="network",
            risk=OperationRisk.MEDIUM,
            force=force or cli_ctx.force,
            non_interactive=cli_ctx.non_interactive,
            dry_run=cli_ctx.dry_run,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_setting(client: EeroClient) -> None:
            method = getattr(client, api_method)
            with cli_ctx.status(f"{action.capitalize()}ing {display_name}..."):
                result = await method(enable, cli_ctx.network_id)

            if result:
                console.print(f"[bold green]{display_name} {action}d[/bold green]")
            else:
                console.print(f"[red]Failed to {action} {display_name}[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_setting)

    asyncio.run(run_cmd())


# Create security toggle commands
wpa3_group = _make_security_toggle("wpa3", "set_wpa3", "WPA3")
band_steering_group = _make_security_toggle("band-steering", "set_band_steering", "band steering")
upnp_group = _make_security_toggle("upnp", "set_upnp", "UPnP")
ipv6_group = _make_security_toggle("ipv6", "set_ipv6", "IPv6")
thread_group = _make_security_toggle("thread", "set_thread_enabled", "Thread")

security_group.add_command(wpa3_group)
security_group.add_command(band_steering_group)
security_group.add_command(upnp_group)
security_group.add_command(ipv6_group)
security_group.add_command(thread_group)


# ==================== SQM Subcommand Group ====================


@network_group.group(name="sqm")
@click.pass_context
def sqm_group(ctx: click.Context) -> None:
    """Manage Smart Queue Management (SQM) / QoS settings.

    \b
    Commands:
      show    - Show SQM settings
      enable  - Enable SQM
      disable - Disable SQM
      set     - Configure bandwidth limits

    \b
    Examples:
      eero network sqm show
      eero network sqm enable
      eero network sqm set --upload 50 --download 200
    """
    pass


@sqm_group.command(name="show")
@click.pass_context
def sqm_show(ctx: click.Context) -> None:
    """Show SQM settings."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_sqm(client: EeroClient) -> None:
            with cli_ctx.status("Getting SQM settings..."):
                sqm_data = await client.get_sqm_settings(cli_ctx.network_id)

            if cli_ctx.is_json_output():
                renderer.render_json(sqm_data, "eero.network.sqm.show/v1")
            else:
                enabled = sqm_data.get("enabled", False)
                upload_bw = sqm_data.get("upload_bandwidth")
                download_bw = sqm_data.get("download_bandwidth")

                content = (
                    f"[bold]Enabled:[/bold] {'[green]Yes[/green]' if enabled else '[dim]No[/dim]'}"
                )
                if upload_bw:
                    content += f"\n[bold]Upload:[/bold] {upload_bw} Mbps"
                if download_bw:
                    content += f"\n[bold]Download:[/bold] {download_bw} Mbps"

                console.print(Panel(content, title="SQM Settings", border_style="blue"))

        await run_with_client(get_sqm)

    asyncio.run(run_cmd())


@sqm_group.command(name="enable")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def sqm_enable(ctx: click.Context, force: bool) -> None:
    """Enable SQM."""
    cli_ctx = get_cli_context(ctx)
    _set_sqm_enabled(cli_ctx, True, force)


@sqm_group.command(name="disable")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def sqm_disable(ctx: click.Context, force: bool) -> None:
    """Disable SQM."""
    cli_ctx = get_cli_context(ctx)
    _set_sqm_enabled(cli_ctx, False, force)


def _set_sqm_enabled(cli_ctx: EeroCliContext, enable: bool, force: bool) -> None:
    """Enable or disable SQM."""
    console = cli_ctx.console
    action = "enable" if enable else "disable"

    try:
        confirm_or_fail(
            action=f"{action} SQM",
            target="network",
            risk=OperationRisk.MEDIUM,
            force=force or cli_ctx.force,
            non_interactive=cli_ctx.non_interactive,
            dry_run=cli_ctx.dry_run,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_sqm(client: EeroClient) -> None:
            with cli_ctx.status(f"{action.capitalize()}ing SQM..."):
                result = await client.set_sqm_enabled(enable, cli_ctx.network_id)

            if result:
                console.print(f"[bold green]SQM {action}d[/bold green]")
            else:
                console.print(f"[red]Failed to {action} SQM[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_sqm)

    asyncio.run(run_cmd())


@sqm_group.command(name="set")
@click.option("--upload", "-u", type=int, help="Upload bandwidth limit (Mbps)")
@click.option("--download", "-d", type=int, help="Download bandwidth limit (Mbps)")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def sqm_set(
    ctx: click.Context, upload: Optional[int], download: Optional[int], force: bool
) -> None:
    """Configure SQM bandwidth limits.

    \b
    Options:
      --upload, -u    Upload bandwidth in Mbps
      --download, -d  Download bandwidth in Mbps

    \b
    Examples:
      eero network sqm set --upload 50 --download 200
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    if upload is None and download is None:
        console.print("[yellow]Specify --upload and/or --download[/yellow]")
        sys.exit(ExitCode.USAGE_ERROR)

    try:
        confirm_or_fail(
            action="configure SQM",
            target=f"upload={upload}Mbps download={download}Mbps",
            risk=OperationRisk.MEDIUM,
            force=force or cli_ctx.force,
            non_interactive=cli_ctx.non_interactive,
            dry_run=cli_ctx.dry_run,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def configure_sqm(client: EeroClient) -> None:
            with cli_ctx.status("Configuring SQM..."):
                result = await client.configure_sqm(
                    enabled=True,
                    upload_mbps=upload,
                    download_mbps=download,
                    network_id=cli_ctx.network_id,
                )

            if result:
                msg_parts = []
                if upload:
                    msg_parts.append(f"Upload={upload}Mbps")
                if download:
                    msg_parts.append(f"Download={download}Mbps")
                console.print(f"[bold green]SQM configured: {' '.join(msg_parts)}[/bold green]")
            else:
                console.print("[red]Failed to configure SQM[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(configure_sqm)

    asyncio.run(run_cmd())


# ==================== Guest Subcommand Group ====================


@network_group.group(name="guest")
@click.pass_context
def guest_group(ctx: click.Context) -> None:
    """Manage guest network.

    \b
    Commands:
      show    - Show guest network settings
      enable  - Enable guest network
      disable - Disable guest network
      set     - Configure guest network

    \b
    Examples:
      eero network guest show
      eero network guest enable
      eero network guest set --name "Guest WiFi" --password "secret123"
    """
    pass


@guest_group.command(name="show")
@click.pass_context
def guest_show(ctx: click.Context) -> None:
    """Show guest network settings."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_guest(client: EeroClient) -> None:
            with cli_ctx.status("Getting guest network settings..."):
                network = await client.get_network(cli_ctx.network_id)

            if cli_ctx.is_json_output():
                data = {
                    "enabled": network.guest_network_enabled,
                    "name": network.guest_network_name,
                    "password": "********" if network.guest_network_password else None,
                }
                renderer.render_json(data, "eero.network.guest.show/v1")
            else:
                enabled = network.guest_network_enabled
                content = (
                    f"[bold]Enabled:[/bold] {'[green]Yes[/green]' if enabled else '[dim]No[/dim]'}\n"
                    f"[bold]Name:[/bold] {network.guest_network_name or 'N/A'}\n"
                    f"[bold]Password:[/bold] {'********' if network.guest_network_password else 'N/A'}"
                )
                console.print(Panel(content, title="Guest Network", border_style="blue"))

        await run_with_client(get_guest)

    asyncio.run(run_cmd())


@guest_group.command(name="enable")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def guest_enable(ctx: click.Context, force: bool) -> None:
    """Enable guest network."""
    cli_ctx = get_cli_context(ctx)
    _set_guest_network(cli_ctx, True, None, None, force)


@guest_group.command(name="disable")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def guest_disable(ctx: click.Context, force: bool) -> None:
    """Disable guest network."""
    cli_ctx = get_cli_context(ctx)
    _set_guest_network(cli_ctx, False, None, None, force)


@guest_group.command(name="set")
@click.option("--name", help="Guest network name")
@click.option("--password", help="Guest network password")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def guest_set(
    ctx: click.Context, name: Optional[str], password: Optional[str], force: bool
) -> None:
    """Configure guest network settings.

    \b
    Options:
      --name      Guest network SSID
      --password  Guest network password

    \b
    Examples:
      eero network guest set --name "Guest WiFi" --password "welcome123"
    """
    cli_ctx = get_cli_context(ctx)
    _set_guest_network(cli_ctx, True, name, password, force)


def _set_guest_network(
    cli_ctx: EeroCliContext,
    enable: bool,
    name: Optional[str],
    password: Optional[str],
    force: bool,
) -> None:
    """Set guest network settings."""
    console = cli_ctx.console
    action = "enable" if enable else "disable"

    try:
        confirm_or_fail(
            action=f"{action} guest network",
            target="network",
            risk=OperationRisk.MEDIUM,
            force=force or cli_ctx.force,
            non_interactive=cli_ctx.non_interactive,
            dry_run=cli_ctx.dry_run,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_guest(client: EeroClient) -> None:
            with cli_ctx.status(f"{action.capitalize()}ing guest network..."):
                result = await client.set_guest_network(
                    enabled=enable,
                    name=name,
                    password=password,
                    network_id=cli_ctx.network_id,
                )

            if result:
                console.print(f"[bold green]Guest network {action}d[/bold green]")
            else:
                console.print(f"[red]Failed to {action} guest network[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_guest)

    asyncio.run(run_cmd())


# ==================== Backup Subcommand Group ====================


@network_group.group(name="backup")
@click.pass_context
def backup_group(ctx: click.Context) -> None:
    """Manage backup network (Eero Plus feature).

    \b
    Commands:
      show    - Show backup network settings
      enable  - Enable backup network
      disable - Disable backup network
      status  - Show current backup status
    """
    pass


@backup_group.command(name="show")
@click.pass_context
def backup_show(ctx: click.Context) -> None:
    """Show backup network configuration."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_backup(client: EeroClient) -> None:
            with cli_ctx.status("Getting backup network settings..."):
                try:
                    backup_data = await client.get_backup_network(cli_ctx.network_id)
                except Exception as e:
                    if is_premium_error(e):
                        console.print("[yellow]Backup network requires Eero Plus[/yellow]")
                        sys.exit(ExitCode.PREMIUM_REQUIRED)
                    raise

            if cli_ctx.is_json_output():
                renderer.render_json(backup_data, "eero.network.backup.show/v1")
            else:
                enabled = backup_data.get("enabled", False)
                content = (
                    f"[bold]Enabled:[/bold] {'[green]Yes[/green]' if enabled else '[dim]No[/dim]'}"
                )
                console.print(Panel(content, title="Backup Network", border_style="blue"))

        await run_with_client(get_backup)

    asyncio.run(run_cmd())


@backup_group.command(name="enable")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def backup_enable(ctx: click.Context, force: bool) -> None:
    """Enable backup network."""
    cli_ctx = get_cli_context(ctx)
    _set_backup(cli_ctx, True, force)


@backup_group.command(name="disable")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def backup_disable(ctx: click.Context, force: bool) -> None:
    """Disable backup network."""
    cli_ctx = get_cli_context(ctx)
    _set_backup(cli_ctx, False, force)


def _set_backup(cli_ctx: EeroCliContext, enable: bool, force: bool) -> None:
    """Set backup network state."""
    console = cli_ctx.console
    action = "enable" if enable else "disable"

    try:
        confirm_or_fail(
            action=f"{action} backup network",
            target="network",
            risk=OperationRisk.MEDIUM,
            force=force or cli_ctx.force,
            non_interactive=cli_ctx.non_interactive,
            dry_run=cli_ctx.dry_run,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_backup(client: EeroClient) -> None:
            with cli_ctx.status(f"{action.capitalize()}ing backup network..."):
                try:
                    result = await client.set_backup_network(enable, cli_ctx.network_id)
                except Exception as e:
                    if is_premium_error(e):
                        console.print("[yellow]Backup network requires Eero Plus[/yellow]")
                        sys.exit(ExitCode.PREMIUM_REQUIRED)
                    raise

            if result:
                console.print(f"[bold green]Backup network {action}d[/bold green]")
            else:
                console.print(f"[red]Failed to {action} backup network[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_backup)

    asyncio.run(run_cmd())


@backup_group.command(name="status")
@click.pass_context
def backup_status(ctx: click.Context) -> None:
    """Show current backup network status."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_status(client: EeroClient) -> None:
            with cli_ctx.status("Getting backup status..."):
                try:
                    status_data = await client.get_backup_status(cli_ctx.network_id)
                    is_using = await client.is_using_backup(cli_ctx.network_id)
                except Exception as e:
                    if is_premium_error(e):
                        console.print("[yellow]Backup network requires Eero Plus[/yellow]")
                        sys.exit(ExitCode.PREMIUM_REQUIRED)
                    raise

            if cli_ctx.is_json_output():
                renderer.render_json(
                    {**status_data, "using_backup": is_using}, "eero.network.backup.status/v1"
                )
            else:
                style = "yellow" if is_using else "green"
                status = "Using Backup" if is_using else "Primary Connection"
                content = f"[bold]Status:[/bold] [{style}]{status}[/{style}]"
                console.print(Panel(content, title="Backup Status", border_style=style))

        await run_with_client(get_status)

    asyncio.run(run_cmd())


# ==================== Speedtest Subcommand Group ====================


@network_group.group(name="speedtest")
@click.pass_context
def speedtest_group(ctx: click.Context) -> None:
    """Run and view speed tests.

    \b
    Commands:
      run   - Run a new speed test
      show  - Show last speed test results
    """
    pass


@speedtest_group.command(name="run")
@click.pass_context
def speedtest_run(ctx: click.Context) -> None:
    """Run a new speed test."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def run_test(client: EeroClient) -> None:
            with cli_ctx.status("Running speed test (this may take a minute)..."):
                result = await client.run_speed_test(cli_ctx.network_id)

            if cli_ctx.is_json_output():
                renderer.render_json(result, "eero.network.speedtest.run/v1")
            else:
                download = result.get("down", {}).get("value", 0)
                upload = result.get("up", {}).get("value", 0)
                latency = result.get("latency", {}).get("value", 0)

                content = (
                    f"[bold]Download:[/bold] {download} Mbps\n"
                    f"[bold]Upload:[/bold] {upload} Mbps\n"
                    f"[bold]Latency:[/bold] {latency} ms"
                )
                console.print(Panel(content, title="Speed Test Results", border_style="green"))

        await run_with_client(run_test)

    asyncio.run(run_cmd())


@speedtest_group.command(name="show")
@click.pass_context
def speedtest_show(ctx: click.Context) -> None:
    """Show last speed test results."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_results(client: EeroClient) -> None:
            with cli_ctx.status("Getting speed test results..."):
                network = await client.get_network(cli_ctx.network_id)

            speed_test = network.speed_test
            if not speed_test:
                console.print("[yellow]No speed test results available[/yellow]")
                return

            if cli_ctx.is_json_output():
                renderer.render_json(speed_test, "eero.network.speedtest.show/v1")
            else:
                download = speed_test.get("down", {}).get("value", 0)
                upload = speed_test.get("up", {}).get("value", 0)
                latency = speed_test.get("latency", {}).get("value", 0)
                tested = speed_test.get("date", "Unknown")

                content = (
                    f"[bold]Download:[/bold] {download} Mbps\n"
                    f"[bold]Upload:[/bold] {upload} Mbps\n"
                    f"[bold]Latency:[/bold] {latency} ms\n"
                    f"[bold]Tested:[/bold] {tested}"
                )
                console.print(Panel(content, title="Speed Test Results", border_style="blue"))

        await run_with_client(get_results)

    asyncio.run(run_cmd())


# ==================== Forwards Subcommand Group ====================


@network_group.group(name="forwards")
@click.pass_context
def forwards_group(ctx: click.Context) -> None:
    """Manage port forwarding rules.

    \b
    Commands:
      list   - List all port forwards
      show   - Show details of a port forward
      add    - Add a new port forward (stub)
      delete - Delete a port forward (stub)
    """
    pass


@forwards_group.command(name="list")
@click.pass_context
def forwards_list(ctx: click.Context) -> None:
    """List all port forwarding rules."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_forwards(client: EeroClient) -> None:
            with cli_ctx.status("Getting port forwards..."):
                forwards = await client.get_forwards(cli_ctx.network_id)

            if cli_ctx.is_json_output():
                renderer.render_json(forwards, "eero.network.forwards.list/v1")
            else:
                if not forwards:
                    console.print("[yellow]No port forwards configured[/yellow]")
                    return

                table = Table(title="Port Forwards")
                table.add_column("ID", style="dim")
                table.add_column("Name", style="cyan")
                table.add_column("External Port")
                table.add_column("Internal IP")
                table.add_column("Internal Port")
                table.add_column("Protocol")

                for fwd in forwards:
                    table.add_row(
                        str(fwd.get("id", "")),
                        fwd.get("name", ""),
                        str(fwd.get("external_port", "")),
                        fwd.get("internal_ip", ""),
                        str(fwd.get("internal_port", "")),
                        fwd.get("protocol", "tcp"),
                    )

                console.print(table)

        await run_with_client(get_forwards)

    asyncio.run(run_cmd())


@forwards_group.command(name="show")
@click.argument("forward_id")
@click.pass_context
def forwards_show(ctx: click.Context, forward_id: str) -> None:
    """Show details of a port forward."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_forward(client: EeroClient) -> None:
            with cli_ctx.status("Getting port forward..."):
                forwards = await client.get_forwards(cli_ctx.network_id)

            target = None
            for fwd in forwards:
                if str(fwd.get("id")) == forward_id:
                    target = fwd
                    break

            if not target:
                console.print(f"[red]Port forward '{forward_id}' not found[/red]")
                sys.exit(ExitCode.NOT_FOUND)

            if cli_ctx.is_json_output():
                renderer.render_json(target, "eero.network.forwards.show/v1")
            else:
                content = "\n".join(f"[bold]{k}:[/bold] {v}" for k, v in target.items())
                console.print(
                    Panel(content, title=f"Port Forward: {forward_id}", border_style="blue")
                )

        await run_with_client(get_forward)

    asyncio.run(run_cmd())


# ==================== DHCP Subcommand Group ====================


@network_group.group(name="dhcp")
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


# ==================== Routing Subcommand ====================


@network_group.command(name="routing")
@click.pass_context
def routing_show(ctx: click.Context) -> None:
    """Show routing information."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_routing(client: EeroClient) -> None:
            with cli_ctx.status("Getting routing information..."):
                routing = await client.get_routing(cli_ctx.network_id)

            if cli_ctx.is_json_output():
                renderer.render_json(routing, "eero.network.routing.show/v1")
            else:
                console.print(
                    Panel(
                        json.dumps(routing, indent=2),
                        title="Routing Information",
                        border_style="blue",
                    )
                )

        await run_with_client(get_routing)

    asyncio.run(run_cmd())


# ==================== Thread Subcommand ====================


@network_group.group(name="thread")
@click.pass_context
def thread_cmd_group(ctx: click.Context) -> None:
    """Manage Thread protocol settings.

    Thread is used for smart home devices. Enable/disable
    is under security settings.
    """
    pass


@thread_cmd_group.command(name="show")
@click.pass_context
def thread_show(ctx: click.Context) -> None:
    """Show Thread protocol information."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_thread(client: EeroClient) -> None:
            with cli_ctx.status("Getting Thread information..."):
                thread_data = await client.get_thread(cli_ctx.network_id)

            if cli_ctx.is_json_output():
                renderer.render_json(thread_data, "eero.network.thread.show/v1")
            else:
                console.print(
                    Panel(
                        json.dumps(thread_data, indent=2),
                        title="Thread Protocol",
                        border_style="blue",
                    )
                )

        await run_with_client(get_thread)

    asyncio.run(run_cmd())


# ==================== Support Subcommand Group ====================


@network_group.group(name="support")
@click.pass_context
def support_group(ctx: click.Context) -> None:
    """Support and diagnostics.

    \b
    Commands:
      show   - Show support information
      bundle - Export support bundle
    """
    pass


@support_group.command(name="show")
@click.pass_context
def support_show(ctx: click.Context) -> None:
    """Show support information."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_support(client: EeroClient) -> None:
            with cli_ctx.status("Getting support information..."):
                support_data = await client.get_support(cli_ctx.network_id)

            if cli_ctx.is_json_output():
                renderer.render_json(support_data, "eero.network.support.show/v1")
            else:
                console.print(
                    Panel(
                        json.dumps(support_data, indent=2),
                        title="Support Information",
                        border_style="blue",
                    )
                )

        await run_with_client(get_support)

    asyncio.run(run_cmd())


@support_group.group(name="bundle")
@click.pass_context
def bundle_group(ctx: click.Context) -> None:
    """Manage support bundles."""
    pass


@bundle_group.command(name="export")
@click.option("--out", "-o", required=True, help="Output file path")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def bundle_export(ctx: click.Context, out: str, force: bool) -> None:
    """Export support bundle to file.

    Creates a diagnostic bundle for Eero support.
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    try:
        confirm_or_fail(
            action="export support bundle",
            target=f"to {out}",
            risk=OperationRisk.MEDIUM,
            force=force or cli_ctx.force,
            non_interactive=cli_ctx.non_interactive,
            dry_run=cli_ctx.dry_run,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def export_bundle(client: EeroClient) -> None:
            with cli_ctx.status("Generating support bundle..."):
                support_data = await client.get_support(cli_ctx.network_id)
                diagnostics = await client.get_diagnostics(cli_ctx.network_id)

            bundle = {
                "support": support_data,
                "diagnostics": diagnostics,
            }

            import json

            with open(out, "w") as f:
                json.dump(bundle, f, indent=2, default=str)

            console.print(f"[bold green]Support bundle exported to {out}[/bold green]")

        await run_with_client(export_bundle)

    asyncio.run(run_cmd())
