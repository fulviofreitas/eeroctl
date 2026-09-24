"""DNS commands for the Eero CLI.

Commands:
- eero network dns show: Show DNS settings
- eero network dns providers: List the network's DNS provider catalogue
- eero network dns mode set: Set DNS mode
- eero network dns caching: Enable/disable DNS caching
- eero network dns clear: Switch back to automatic DNS

The mode, custom-server and caching writes reboot every eero on the network,
so those commands require a typed ``REBOOT`` confirmation unless --force is
given. The DNS-policy (content-filter) writes -- ``dns policy allow|block|
allow-cnames`` -- do not reboot the mesh; they are MEDIUM-tier writes with
their own (non-typed) confirmation.
"""

import asyncio
import ipaddress
import sys
from typing import Any, Dict, List, NoReturn, Optional, Sequence, Set, Tuple

import click
from eero import EeroClient
from rich.panel import Panel
from rich.table import Table

from ...context import EeroCliContext, get_cli_context
from ...exit_codes import ExitCode
from ...options import apply_options, force_option, network_option, output_option
from ...safety import SafetyContext, SafetyError, get_write_spec, require_write_confirmation
from ...transformers import extract_data, safe_get
from ...utils import err_console, run_with_client

DNS_PROVIDERS_SCHEMA = "eero.network.dns.providers/v1"
"""Schema identifier for ``dns providers`` structured output."""

DNS_SHOW_SCHEMA = "eero.network.dns.show/v2"
"""Schema identifier for ``dns show`` structured output.

Bumped to v2 when the payload was scoped to the DNS subtree. v1 emitted the entire
network object, which includes the Wi-Fi and guest passwords in plaintext.
"""


MAX_DNS_SERVERS_PER_FAMILY = 2
"""Client-side cap mirroring the SDK's, so bad input is rejected before the prompt.

The SDK enforces the same limit, but it raises from inside the write call --
which happens after confirmation. Validating here means a user is never asked to
approve a network reboot for input that will be rejected anyway.
"""

FALLBACK_PROVIDERS = {
    "cloudflare": {"ipv4": ["1.1.1.1", "1.0.0.1"], "ipv6": []},
    "google": {"ipv4": ["8.8.8.8", "8.8.4.4"], "ipv6": []},
    "opendns": {"ipv4": ["208.67.222.222", "208.67.220.220"], "ipv6": []},
}
"""Addresses to use when the API serves no provider catalogue.

These are the values eero-api hardcoded through 6.2.0, verified identical to the
live catalogue. Providers outside this map resolve only from the catalogue; the
CLI does not invent addresses it has no source for.
"""


def _split_servers(values: Sequence[str]) -> Tuple[List[str], List[str]]:
    """Split IP literals by address family, validating each.

    Mirrors the SDK's rules so failures surface before the confirmation prompt
    rather than after it.

    Args:
        values: Raw --servers values.

    Returns:
        (ipv4, ipv6) lists in the order supplied.

    Raises:
        click.ClickException: Never; errors exit via _fail_usage.
    """
    ipv4: List[str] = []
    ipv6: List[str] = []

    for entry in values:
        text = str(entry).strip()
        if not text:
            _fail_usage("DNS server address must not be empty.")
        if "%" in text:
            _fail_usage(f"{text!r} has a zone identifier, which is not valid for a DNS server.")
        try:
            address = ipaddress.ip_address(text)
        except ValueError:
            _fail_usage(f"{text!r} is not a valid IP address.")
        (ipv4 if address.version == 4 else ipv6).append(str(address))

    for family, group in (("IPv4", ipv4), ("IPv6", ipv6)):
        if len(group) > MAX_DNS_SERVERS_PER_FAMILY:
            _fail_usage(
                f"at most {MAX_DNS_SERVERS_PER_FAMILY} {family} DNS servers are "
                f"supported (got {len(group)}).",
                hint=(
                    "The eero app exposes primary and secondary slots per address "
                    "family. You may pass up to 2 IPv4 and 2 IPv6 servers in the "
                    "same command."
                ),
            )

    return ipv4, ipv6


def _fail_usage(message: str, hint: Optional[str] = None) -> NoReturn:
    """Report invalid input and exit with the usage error code."""
    err_console.print(f"[bold red]Error:[/bold red] {message}")
    if hint:
        err_console.print(f"[dim]Hint: {hint}[/dim]")
    sys.exit(ExitCode.USAGE_ERROR)


def _catalogue(view: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return the provider catalogue the API serves, if any.

    The API owns this list (``data.dns.default_test_servers``); eeroctl does not
    hardcode provider names, so a provider added server-side works without a
    release here.
    """
    entries = safe_get(view, "dns", "default_test_servers", default=[]) or []
    return [e for e in entries if isinstance(e, dict) and e.get("name")]


def _resolve_provider(name: str, view: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Resolve a provider name to its IPv4 and IPv6 addresses.

    Matches case-insensitively: the API serves Title-Case names ("Cloudflare"),
    while users type lowercase.

    Args:
        name: Provider name as typed.
        view: Scoped DNS view from the pre-write read.

    Returns:
        (ipv4, ipv6) address lists for the provider.
    """
    entries = _catalogue(view)

    for entry in entries:
        if str(entry.get("name", "")).strip().lower() == name.strip().lower():
            return (
                [str(ip) for ip in entry.get("ipv4") or []],
                [str(ip) for ip in entry.get("ipv6") or []],
            )

    fallback = FALLBACK_PROVIDERS.get(name.strip().lower())
    if fallback is not None:
        err_console.print(
            "[yellow]Warning:[/yellow] the network served no DNS provider catalogue; "
            f"using eeroctl's built-in addresses for {name}."
        )
        return list(fallback["ipv4"]), list(fallback["ipv6"])

    if entries:
        available = ", ".join(str(e["name"]) for e in entries)
        _fail_usage(
            f"{name!r} is not a valid DNS mode.",
            hint=f"Expected auto, custom, or one of: {available}.",
        )
    _fail_usage(
        f"{name!r} is not a valid DNS mode, and the network served no provider "
        "catalogue to resolve it against.",
        hint="Expected auto or custom. Run 'eero network dns providers' to list providers.",
    )


def _normalise(addresses: Sequence[str]) -> Set[str]:
    """Normalise addresses for order- and format-insensitive comparison.

    The API stores IPv6 fully expanded (2606:4700:4700:0:0:0:0:1111) while the
    provider catalogue serves it compressed (2606:4700:4700::1111). Comparing
    the two as strings always reports a difference, which would defeat the
    no-op check and reboot the network on every run.
    """
    normalised: Set[str] = set()
    for entry in addresses:
        try:
            normalised.add(str(ipaddress.ip_address(str(entry))))
        except ValueError:
            normalised.add(str(entry))
    return normalised


def _current_state(view: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the comparable DNS state from a scoped view."""
    dns: Dict[str, Any] = view.get("dns") or {}
    name_servers: Dict[str, Any] = safe_get(view, "ipv6", "name_servers", default={}) or {}
    return {
        "ipv4_mode": str(dns.get("mode") or "").lower(),
        "ipv6_mode": str(name_servers.get("mode") or "").lower(),
        "ipv4": _normalise(safe_get(dns, "custom", "ips", default=[]) or []),
        "ipv6": _normalise(name_servers.get("custom") or []),
    }


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
    command: str,
    target: str,
    force: bool,
) -> bool:
    """Require confirmation for a DNS write, per its registered :class:`WriteSpec`.

    Every DNS write command is a mesh-reboot write (``reboots="mesh"``), so
    :func:`require_write_confirmation` unconditionally prints the reboot
    warning -- even under ``--force`` -- and requires the typed ``REBOOT``
    phrase interactively.

    Args:
        cli_ctx: CLI context carrying the safety flags.
        command: The DNS write's command path, e.g. "network dns mode set",
            used to look up its :class:`~eeroctl.safety.WriteSpec`.
        target: Target of the action, e.g. "to custom".
        force: Per-command --force value.

    Returns:
        True if the caller should proceed with the write.

    Raises:
        SystemExit: With ExitCode.SAFETY_RAIL when confirmation fails or is
            required but unavailable.
    """
    spec = get_write_spec(command)
    cli_ctx.active_write_spec = spec

    try:
        return require_write_confirmation(
            spec,
            target=target,
            ctx=SafetyContext(
                force=force or cli_ctx.force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
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
      providers  - List the DNS providers this network offers
      mode       - Set DNS mode
      caching    - Enable/disable DNS caching
      clear      - Switch back to automatic DNS, retaining stored servers

    \b
    Every DNS write reboots all eeros on the network.

    \b
    Examples:
      eero network dns show
      eero network dns providers
      eero network dns mode set google
      eero network dns caching enable
      eero network dns clear
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
@click.argument("mode")
@click.option(
    "--servers",
    "-s",
    multiple=True,
    help="Custom DNS servers. May mix IPv4 and IPv6; up to 2 per family.",
)
@click.option(
    "--family",
    type=click.Choice(["ipv4", "ipv6", "both"]),
    default=None,
    help="Restrict the change to one address family. Default: IPv4 for providers, both otherwise.",
)
@click.option("--force", "-f", is_flag=True, help="Skip confirmation and rewrite if unchanged")
@network_option
@click.pass_context
def dns_mode_set(
    ctx: click.Context,
    mode: str,
    servers: tuple,
    family: Optional[str],
    force: bool,
    network_id: Optional[str],
) -> None:
    """Set DNS mode.

    \b
    MODE is one of:
      auto     - Use ISP-assigned DNS (retains any stored custom servers)
      custom   - Use custom servers (--servers), or re-enable stored ones
      <name>   - A provider from your network's DNS catalogue

    Provider names come from the network itself rather than a fixed list, so
    whatever your eeros offer will work. Run 'eero network dns providers' to
    see them.

    \b
    Applying any DNS change reboots every eero on the network.

    \b
    Examples:
      eero network dns mode set google
      eero network dns mode set google --family both
      eero network dns mode set custom --servers 1.1.1.1 --servers 2606:4700:4700::1111
      eero network dns mode set auto
    """
    cli_ctx = apply_options(ctx, network_id=network_id)
    console_out = cli_ctx.err_console

    # Validate --servers before anything else, so invalid input never reaches
    # the confirmation prompt.
    ipv4_arg, ipv6_arg = _split_servers(servers)
    requested = mode.strip().lower()

    if requested == "custom" and not servers and family:
        _fail_usage("--family has no effect on 'custom' without --servers.")

    async def run_cmd() -> None:
        async def apply(client: EeroClient) -> None:
            with cli_ctx.status("Reading current DNS settings..."):
                view = _dns_view(await client.get_dns_settings(cli_ctx.network_id))

            current = _current_state(view)
            effective_force = force or cli_ctx.force

            if requested in ("auto", "automatic"):
                target_family = None if family in (None, "both") else family
                desired = _desired_for_auto(current, target_family)
                describe = "to automatic (ISP-assigned)"

                async def write() -> Any:
                    return await client.clear_custom_dns(target_family, cli_ctx.network_id)

            elif requested == "custom":
                if not servers:
                    # Mode-only re-enable: the API retains stored servers across a
                    # switch to automatic, so flipping the selector brings them back.
                    desired = {**current, "ipv4_mode": "custom", "ipv6_mode": "custom"}
                    describe = "to custom (re-enabling stored servers)"

                    async def write() -> Any:
                        return await client.set_dns_mode("custom", None, cli_ctx.network_id)

                else:
                    desired, write = _plan_custom(
                        client, cli_ctx, current, ipv4_arg, ipv6_arg, family
                    )
                    describe = "to custom"

            else:
                provider_v4, provider_v6 = _resolve_provider(mode, view)
                # Providers default to IPv4 only, matching prior behaviour: a
                # preset should not silently rewrite IPv6 nobody mentioned.
                scope = family or "ipv4"
                desired, write = _plan_custom(
                    client,
                    cli_ctx,
                    current,
                    provider_v4,
                    provider_v6,
                    None if scope == "both" else scope,
                )
                describe = f"to {mode}"

            if _states_match(current, desired):
                if not effective_force:
                    console_out.print(
                        "[dim]DNS already configured as requested; no change made.[/dim]"
                    )
                    return
                cli_ctx.renderer.render_warning(
                    "DNS already configured as requested; rewriting anyway because "
                    "--force was passed. This will reboot the network."
                )

            if not _confirm_dns_write(cli_ctx, "network dns mode set", describe, force):
                return

            with cli_ctx.status(f"Setting DNS mode {describe}..."):
                result = await write()

            if _write_succeeded(result):
                console_out.print(f"[bold green]DNS mode set {describe}[/bold green]")
            else:
                console_out.print("[red]Failed to set DNS mode[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(apply)

    asyncio.run(run_cmd())


def _desired_for_auto(current: Dict[str, Any], family: Optional[str]) -> Dict[str, Any]:
    """Build the state a switch to automatic would produce.

    Non-destructive: the API retains the stored servers, so only the mode
    selectors change.
    """
    desired = dict(current)
    if family in (None, "ipv4"):
        desired["ipv4_mode"] = "automatic"
    if family in (None, "ipv6"):
        desired["ipv6_mode"] = "automatic"
    return desired


def _plan_custom(
    client: EeroClient,
    cli_ctx: EeroCliContext,
    current: Dict[str, Any],
    ipv4: Sequence[str],
    ipv6: Sequence[str],
    family: Optional[str],
) -> Tuple[Dict[str, Any], Any]:
    """Build the desired state and the write for a custom-server change.

    A family absent from the request is left untouched, matching the SDK.

    Returns:
        (desired state, zero-argument coroutine function performing the write)
    """
    desired = dict(current)
    network_id = cli_ctx.network_id

    if family == "ipv4":
        if not ipv4:
            _fail_usage("no IPv4 servers to apply for --family ipv4.")
        desired["ipv4_mode"] = "custom"
        desired["ipv4"] = _normalise(ipv4)

        async def write() -> Any:
            return await client.set_custom_dns_ipv4(list(ipv4), network_id)

    elif family == "ipv6":
        if not ipv6:
            _fail_usage("no IPv6 servers to apply for --family ipv6.")
        desired["ipv6_mode"] = "custom"
        desired["ipv6"] = _normalise(ipv6)

        async def write() -> Any:
            return await client.set_custom_dns_ipv6(list(ipv6), network_id)

    else:
        combined = [*ipv4, *ipv6]
        if not combined:
            _fail_usage(
                "no DNS servers supplied.",
                hint="Use 'eero network dns clear' to switch back to automatic DNS.",
            )
        if ipv4:
            desired["ipv4_mode"] = "custom"
            desired["ipv4"] = _normalise(ipv4)
        if ipv6:
            desired["ipv6_mode"] = "custom"
            desired["ipv6"] = _normalise(ipv6)

        async def write() -> Any:
            return await client.set_custom_dns(combined, network_id)

    return desired, write


def _states_match(current: Dict[str, Any], desired: Dict[str, Any]) -> bool:
    """Compare current and desired DNS state.

    Modes are normalised ("auto" and "automatic" are the same selector) and
    server lists compared as sets of canonical addresses.
    """

    def mode_eq(a: str, b: str) -> bool:
        auto = {"auto", "automatic"}
        return (a in auto and b in auto) or a == b

    return (
        mode_eq(current["ipv4_mode"], desired["ipv4_mode"])
        and mode_eq(current["ipv6_mode"], desired["ipv6_mode"])
        and current["ipv4"] == desired["ipv4"]
        and current["ipv6"] == desired["ipv6"]
    )


@dns_group.command(name="providers")
@output_option
@network_option
@click.pass_context
def dns_providers(ctx: click.Context, output: Optional[str], network_id: Optional[str]) -> None:
    """List the DNS providers this network offers.

    These names are served by the network itself and are the valid values for
    'eero network dns mode set'.
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console_out = cli_ctx.console

    async def run_cmd() -> None:
        async def get_providers(client: EeroClient) -> None:
            with cli_ctx.status("Getting DNS providers..."):
                view = _dns_view(await client.get_dns_settings(cli_ctx.network_id))

            entries = _catalogue(view)

            if cli_ctx.is_structured_output() or cli_ctx.is_list_output():
                payload = {"providers": entries}
                if cli_ctx.is_list_output():
                    cli_ctx.renderer.render_text(payload, DNS_PROVIDERS_SCHEMA)
                else:
                    cli_ctx.render_structured(payload, DNS_PROVIDERS_SCHEMA)
                return

            if not entries:
                console_out.print("[yellow]This network served no DNS provider catalogue.[/yellow]")
                sys.exit(ExitCode.NOT_FOUND)

            table = Table(title="DNS Providers", border_style="blue")
            table.add_column("Name", style="cyan")
            table.add_column("IPv4")
            table.add_column("IPv6")
            for entry in entries:
                table.add_row(
                    str(entry.get("name", "")),
                    ", ".join(_format_ip(ip) for ip in entry.get("ipv4") or []) or "-",
                    ", ".join(_format_ip(ip) for ip in entry.get("ipv6") or []) or "-",
                )
            console_out.print(table)

        await run_with_client(get_providers)

    asyncio.run(run_cmd())


@dns_group.command(name="clear")
@click.option(
    "--family",
    type=click.Choice(["ipv4", "ipv6"]),
    default=None,
    help="Clear only one address family. Default: both.",
)
@click.option("--force", "-f", is_flag=True, help="Skip confirmation and rewrite if unchanged")
@network_option
@click.pass_context
def dns_clear(
    ctx: click.Context, family: Optional[str], force: bool, network_id: Optional[str]
) -> None:
    """Switch DNS back to automatic (ISP-assigned).

    This is non-destructive: the network retains the configured servers rather
    than discarding them, matching the eero app's "ISP DNS (Default)" option.
    Re-enable them later with 'eero network dns mode set custom'.

    \b
    Applying this reboots every eero on the network.
    """
    cli_ctx = apply_options(ctx, network_id=network_id)
    console_out = cli_ctx.err_console
    scope = f" ({family})" if family else ""

    async def run_cmd() -> None:
        async def clear(client: EeroClient) -> None:
            with cli_ctx.status("Reading current DNS settings..."):
                view = _dns_view(await client.get_dns_settings(cli_ctx.network_id))

            current = _current_state(view)
            effective_force = force or cli_ctx.force

            if _states_match(current, _desired_for_auto(current, family)):
                if not effective_force:
                    console_out.print("[dim]DNS is already automatic; no change made.[/dim]")
                    return
                cli_ctx.renderer.render_warning(
                    "DNS is already automatic; rewriting anyway because --force was "
                    "passed. This will reboot the network."
                )

            if not _confirm_dns_write(
                cli_ctx, "network dns clear", f"on this network{scope}", force
            ):
                return

            with cli_ctx.status("Clearing custom DNS..."):
                result = await client.clear_custom_dns(family, cli_ctx.network_id)

            if _write_succeeded(result):
                console_out.print(
                    f"[bold green]DNS switched to automatic{scope}; "
                    "stored servers retained[/bold green]"
                )
            else:
                console_out.print("[red]Failed to clear custom DNS[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(clear)

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
    console = cli_ctx.err_console
    action = "enable" if enable else "disable"

    if not _confirm_dns_write(cli_ctx, f"network dns caching {action}", "on this network", force):
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


# ==================== DNS Content-Filtering Policy (read-only, phase A) ====================
#
# get_advanced_content_filter (client.py:2428) is a premium, plain GET; unlike
# every other command in this module it is not a DNS write and does not
# reboot the mesh, so it gets its own subgroup rather than living under
# `dns show`/`dns mode`/`dns caching`/`dns clear` above.


@dns_group.group(name="policy")
@click.pass_context
def dns_policy_group(ctx: click.Context) -> None:
    """Manage DNS content-filtering policy (Eero Plus feature).

    \b
    Commands:
      show          - Allowed/blocked domain lists
      allow         - Allow a domain network-wide
      block         - Block a domain network-wide
      allow-cnames  - Allow one or more CNAME domains network-wide
    """
    pass


@dns_policy_group.command(name="show")
@output_option
@network_option
@click.pass_context
def dns_policy_show(ctx: click.Context, output: Optional[str], network_id: Optional[str]) -> None:
    """Show DNS content-filtering allow/block lists (Eero Plus feature)."""
    from ...formatting.dns_policy import print_dns_policy
    from ...transformers.dns_policy import extract_dns_policy

    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_policy(client: EeroClient) -> None:
            with cli_ctx.status("Getting DNS content-filtering policy..."):
                raw = await client.get_advanced_content_filter(cli_ctx.network_id)
            print_dns_policy(cli_ctx, extract_dns_policy(raw))

        await run_with_client(get_policy)

    asyncio.run(run_cmd())


# ==================== DNS Content-Filtering Policy writes (phase C) ====================
#
# `allow_domain`/`block_domain`/`allow_cnames` (client.py:2435,2473,2462) are
# network-wide, premium (Eero Plus) DNS content-filtering writes -- distinct
# from `profile dns allow/block` (`allow_domain_for_profiles`/
# `block_domain_for_profiles`), which scope the same policy to one or more
# profiles. Unverified, no mesh reboot (migration plan §4 phase C row 41).
# `EeroPremiumRequiredException` is left to propagate to `run_with_client`'s
# normal `handle_cli_error` mapping (exit 11) rather than caught here.


@dns_policy_group.command(name="allow")
@click.argument("domain")
@click.option("--delete", "is_delete", is_flag=True, help="Remove domain from the allow list")
@click.option(
    "--keep-profiles",
    "keep_profiles",
    multiple=True,
    help="Profile id to leave unaffected by this change (repeatable).",
)
@force_option
@network_option
@click.pass_context
def dns_policy_allow(
    ctx: click.Context,
    domain: str,
    is_delete: bool,
    keep_profiles: Tuple[str, ...],
    force: Optional[bool],
    network_id: Optional[str],
) -> None:
    """Allow a domain network-wide (Eero Plus feature).

    \b
    Arguments:
      DOMAIN  Domain to allow
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console_ = cli_ctx.err_console

    spec = get_write_spec("network dns policy allow")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target=domain,
            ctx=SafetyContext(
                force=cli_ctx.force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
            console=console_,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def allow(client: EeroClient) -> None:
            with cli_ctx.status(f"Allowing '{domain}'..."):
                result = await client.allow_domain(
                    domain,
                    cli_ctx.network_id,
                    is_delete=is_delete or None,
                    keep_profiles=list(keep_profiles) or None,
                )

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console_.print(f"[bold green]'{domain}' allowed[/bold green]")
                console_.print(f"[dim]Verify with `{spec.read_command}`.[/dim]")
            else:
                console_.print(f"[red]Failed to allow '{domain}'[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(allow)

    asyncio.run(run_cmd())


@dns_policy_group.command(name="block")
@click.argument("domain")
@click.option("--delete", "is_delete", is_flag=True, help="Remove domain from the block list")
@click.option(
    "--keep-profiles",
    "keep_profiles",
    multiple=True,
    help="Profile id to leave unaffected by this change (repeatable).",
)
@force_option
@network_option
@click.pass_context
def dns_policy_block(
    ctx: click.Context,
    domain: str,
    is_delete: bool,
    keep_profiles: Tuple[str, ...],
    force: Optional[bool],
    network_id: Optional[str],
) -> None:
    """Block a domain network-wide (Eero Plus feature).

    \b
    Arguments:
      DOMAIN  Domain to block
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console_ = cli_ctx.err_console

    spec = get_write_spec("network dns policy block")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target=domain,
            ctx=SafetyContext(
                force=cli_ctx.force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
            console=console_,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def block(client: EeroClient) -> None:
            with cli_ctx.status(f"Blocking '{domain}'..."):
                result = await client.block_domain(
                    domain,
                    cli_ctx.network_id,
                    is_delete=is_delete or None,
                    keep_profiles=list(keep_profiles) or None,
                )

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console_.print(f"[bold green]'{domain}' blocked[/bold green]")
                console_.print(f"[dim]Verify with `{spec.read_command}`.[/dim]")
            else:
                console_.print(f"[red]Failed to block '{domain}'[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(block)

    asyncio.run(run_cmd())


@dns_policy_group.command(name="allow-cnames")
@click.argument("domains", nargs=-1, required=True)
@force_option
@network_option
@click.pass_context
def dns_policy_allow_cnames(
    ctx: click.Context,
    domains: Tuple[str, ...],
    force: Optional[bool],
    network_id: Optional[str],
) -> None:
    """Allow one or more CNAME domains network-wide (Eero Plus feature).

    \b
    Arguments:
      DOMAINS  One or more CNAME domains to allow
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console_ = cli_ctx.err_console

    spec = get_write_spec("network dns policy allow-cnames")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target=", ".join(domains),
            ctx=SafetyContext(
                force=cli_ctx.force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
            console=console_,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def allow_cnames(client: EeroClient) -> None:
            with cli_ctx.status("Allowing CNAME domains..."):
                result = await client.allow_cnames(list(domains), cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console_.print("[bold green]CNAME domains allowed[/bold green]")
                console_.print(f"[dim]Verify with `{spec.read_command}`.[/dim]")
            else:
                console_.print("[red]Failed to allow CNAME domains[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(allow_cnames)

    asyncio.run(run_cmd())
