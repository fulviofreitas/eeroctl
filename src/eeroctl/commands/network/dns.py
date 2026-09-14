"""DNS commands for the Eero CLI.

Commands:
- eero network dns show: Show DNS settings
- eero network dns mode set: Set DNS mode
- eero network dns caching: Enable/disable DNS caching
"""

import asyncio
import ipaddress
import sys
from typing import Any, Dict, List, Optional

import click
from eero import EeroClient
from rich.panel import Panel

from ...context import EeroCliContext, get_cli_context
from ...exit_codes import ExitCode
from ...options import apply_options, network_option, output_option
from ...safety import OperationRisk, SafetyError, confirm_or_fail
from ...transformers import extract_data, safe_get
from ...utils import run_with_client

DNS_SHOW_SCHEMA = "eero.network.dns.show/v2"
"""Schema identifier for ``dns show`` structured output.

Bumped to v2 when the payload was scoped to the DNS subtree. v1 emitted the entire
network object, which includes the Wi-Fi and guest passwords in plaintext.
"""


DNS_CONFIRMATION_PHRASE = "REBOOT"
"""Phrase the user must type to approve a DNS write.

Names the consequence rather than the command. Passed explicitly so every DNS
subcommand asks for the same word; the auto-derived default would produce
CHANGEDNSMODE, ENABLEDNSCACHING and so on.
"""

REBOOT_WARNING = (
    "Applying a DNS change reboots every eero on the network. All clients lose "
    "Wi-Fi and internet while the mesh restarts. The outage begins a few minutes "
    "after this command returns, not immediately."
)
"""Warning emitted on every DNS write path, including --force.

Observed 2026-09-12: two DNS writes were followed ~5 minutes later by all four
nodes rebooting within a 17-second window. The SDK logs an equivalent warning,
but eeroctl does not route the eero.api.dns logger through Rich, so that is not
reliably visible to a user.
"""


def _write_succeeded(result: Any) -> bool:
    """Check an API write response for success.

    Validates ``meta.code`` rather than truthiness. eero-api 6.x fabricated a
    ``{"meta": {"code": 400}}`` response for an invalid mode without contacting
    the API; that dict is truthy, so ``if result:`` reported success for a write
    the SDK had already rejected.

    A missing or unrecognised ``meta.code`` is treated as failure. Assuming
    success from an unfamiliar shape is the failure mode this replaces.

    Args:
        result: Raw ``{"meta": ..., "data": ...}`` response from a write call.

    Returns:
        True when ``meta.code`` is a 2xx status.
    """
    if not isinstance(result, dict):
        return False

    meta = result.get("meta")
    if not isinstance(meta, dict):
        return False

    code = meta.get("code")
    return isinstance(code, int) and 200 <= code < 300


def _confirm_dns_write(
    cli_ctx: EeroCliContext,
    action: str,
    target: str,
    force: bool,
) -> bool:
    """Warn about the reboot, then require typed confirmation for a DNS write.

    The warning is unconditional. ``--force`` correctly skips the prompt, but a
    scripted caller should still be told a reboot was triggered.

    Args:
        cli_ctx: CLI context carrying the safety flags.
        action: Description of the action, e.g. "change DNS mode".
        target: Target of the action, e.g. "to custom".
        force: Per-command --force value.

    Returns:
        True if the caller should proceed with the write.

    Raises:
        SystemExit: With ExitCode.SAFETY_RAIL when confirmation fails or is
            required but unavailable.
    """
    cli_ctx.renderer.render_warning(REBOOT_WARNING)

    try:
        return confirm_or_fail(
            action=action,
            target=target,
            risk=OperationRisk.HIGH,
            confirmation_phrase=DNS_CONFIRMATION_PHRASE,
            force=force or cli_ctx.force,
            non_interactive=cli_ctx.non_interactive,
            dry_run=cli_ctx.dry_run,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)


def _format_ip(value: Any) -> str:
    """Render an IP address in its canonical compact form.

    The API stores IPv6 fully expanded (``2606:4700:4700:0:0:0:0:1111``); this
    renders it as ``2606:4700:4700::1111``. Non-IP values pass through unchanged
    so a shape change upstream degrades to raw display rather than an exception.
    """
    try:
        return str(ipaddress.ip_address(str(value)))
    except ValueError:
        return str(value)


def _dns_view(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Project the raw network response onto the DNS-relevant subtree.

    ``get_dns_settings`` is ``GET networks/{id}``, so the response carries the whole
    network object: Wi-Fi and guest passwords in plaintext, the WAN IP, geo-location,
    and every node's serial and MAC. Structured output must expose only DNS.

    This is an allowlist, deliberately. A denylist would leak each new sensitive
    field the API adds until someone noticed.

    Args:
        raw: Full ``{"meta": ..., "data": ...}`` response from ``get_dns_settings``.

    Returns:
        A dict with just the ``dns`` and ``ipv6.name_servers`` subtrees.
    """
    data = extract_data(raw)
    if not isinstance(data, dict):
        return {"dns": {}, "ipv6": {"name_servers": {}}}

    return {
        "dns": data.get("dns") or {},
        "ipv6": {"name_servers": safe_get(data, "ipv6", "name_servers", default={}) or {}},
    }


def _dns_panel(view: Dict[str, Any]) -> Panel:
    """Build the table-output panel from a scoped DNS view.

    Absent fields render as ``unknown`` rather than a plausible default. Showing
    "auto" for a field that was never read is what let the original bug survive.
    """
    dns: Dict[str, Any] = view.get("dns") or {}
    name_servers: Dict[str, Any] = safe_get(view, "ipv6", "name_servers", default={}) or {}

    caching = dns.get("caching")
    custom_ips: List[Any] = safe_get(dns, "custom", "ips", default=[]) or []
    parent_ips: List[Any] = safe_get(dns, "parent", "ips", default=[]) or []
    ipv6_ips: List[Any] = name_servers.get("custom") or []

    lines = [f"[bold]DNS Mode:[/bold] {dns.get('mode') or '[dim]unknown[/dim]'}"]

    if caching is None:
        lines.append("[bold]DNS Caching:[/bold] [dim]unknown[/dim]")
    else:
        state = "[green]Enabled[/green]" if caching else "[dim]Disabled[/dim]"
        lines.append(f"[bold]DNS Caching:[/bold] {state}")

    if custom_ips:
        lines.append(
            f"[bold]Custom DNS (IPv4):[/bold] {', '.join(_format_ip(ip) for ip in custom_ips)}"
        )

    lines.append(f"[bold]IPv6 DNS Mode:[/bold] {name_servers.get('mode') or '[dim]unknown[/dim]'}")

    if ipv6_ips:
        lines.append(
            f"[bold]Custom DNS (IPv6):[/bold] {', '.join(_format_ip(ip) for ip in ipv6_ips)}"
        )

    if parent_ips:
        lines.append(f"[bold]ISP-assigned:[/bold] {', '.join(_format_ip(ip) for ip in parent_ips)}")

    return Panel("\n".join(lines), title="DNS Settings", border_style="blue")


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
@output_option
@network_option
@click.pass_context
def dns_show(ctx: click.Context, output: Optional[str], network_id: Optional[str]) -> None:
    """Show current DNS settings."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_dns(client: EeroClient) -> None:
            with cli_ctx.status("Getting DNS settings..."):
                dns_data = await client.get_dns_settings(cli_ctx.network_id)

            view = _dns_view(dns_data)

            if cli_ctx.is_structured_output():
                cli_ctx.render_structured(view, DNS_SHOW_SCHEMA)
            elif cli_ctx.is_list_output():
                renderer.render_text(view, DNS_SHOW_SCHEMA)
            else:
                console.print(_dns_panel(view))

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

    if not _confirm_dns_write(cli_ctx, "change DNS mode", f"to {mode}", force):
        return

    async def run_cmd() -> None:
        async def set_mode(client: EeroClient) -> None:
            custom_servers = list(servers) if servers else None
            with cli_ctx.status(f"Setting DNS mode to {mode}..."):
                result = await client.set_dns_mode(mode, custom_servers, cli_ctx.network_id)

            if _write_succeeded(result):
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

    if not _confirm_dns_write(cli_ctx, f"{action} DNS caching", "on this network", force):
        return

    async def run_cmd() -> None:
        async def set_caching(client: EeroClient) -> None:
            with cli_ctx.status(f"{action.capitalize()}ing DNS caching..."):
                result = await client.set_dns_caching(enable, cli_ctx.network_id)

            if _write_succeeded(result):
                console.print(f"[bold green]DNS caching {action}d[/bold green]")
            else:
                console.print(f"[red]Failed to {action} DNS caching[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_caching)

    asyncio.run(run_cmd())
