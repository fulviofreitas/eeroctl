"""DNS commands for the Eero CLI.

Commands:
- eero network dns show: Show DNS settings
- eero network dns mode set: Set DNS mode
- eero network dns caching: Enable/disable DNS caching
"""

import asyncio
import sys

import click
from eero import EeroClient
from rich.panel import Panel

from ...context import EeroCliContext, get_cli_context
from ...exit_codes import ExitCode
from ...safety import OperationRisk, SafetyError, confirm_or_fail
from ...utils import run_with_client


@click.group(name="dns")
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
            elif cli_ctx.is_list_output():
                renderer.render_text(dns_data, "eero.network.dns.show/v1")
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
