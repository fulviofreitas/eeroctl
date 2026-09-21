"""Guest network commands for the Eero CLI.

Commands:
- eero network guest show: Show guest network settings
- eero network guest enable: Enable guest network
- eero network guest disable: Disable guest network
- eero network guest set: Configure guest network
- eero network guest password set: Set the guest network password
- eero network guest password clear: Clear the guest network password
"""

import asyncio
import sys
from typing import Any, Optional

import click
from eero import EeroClient
from rich.panel import Panel

from ...context import EeroCliContext, get_cli_context
from ...exit_codes import ExitCode
from ...safety import SafetyContext, SafetyError, get_write_spec, require_write_confirmation
from ...transformers import extract_data, normalize_network
from ...utils import run_with_client, write_if_changed


@click.group(name="guest")
@click.pass_context
def guest_group(ctx: click.Context) -> None:
    """Manage guest network.

    \b
    Commands:
      show     - Show guest network settings
      enable   - Enable guest network
      disable  - Disable guest network
      set      - Configure guest network
      password - Manage the guest network password

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
    """Show guest network settings.

    Reads from the dedicated `get_guest_network` endpoint (client.py:1118,
    GETs the network's `guestnetwork` sub-resource) instead of the full
    network envelope this used to read `guest_network_enabled`/
    `guest_network_name`/`guest_network_password` out of. <!-- unverified
    shape --> the sub-resource's own field names are assumed to be the same
    `enabled`/`name`/`password` names, unprefixed since the response is
    already scoped -- no live sample captured yet (migration plan §5.3). The
    password stays masked in every format, exactly as before: this command
    never round-trips the real value, even to `json`/`yaml`.
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def get_guest(client: EeroClient) -> None:
            with cli_ctx.status("Getting guest network settings..."):
                raw_guest = await client.get_guest_network(cli_ctx.network_id)

            guest = extract_data(raw_guest) if isinstance(raw_guest, dict) else {}
            if not isinstance(guest, dict):
                guest = {}

            enabled = guest.get("enabled")
            name = guest.get("name")
            has_password = bool(guest.get("password"))

            data = {
                "enabled": enabled,
                "name": name,
                "password": "********" if has_password else None,
            }

            if cli_ctx.is_json_output() or cli_ctx.is_yaml_output() or cli_ctx.is_text_output():
                # `data`'s password is already masked above, so there is
                # nothing to redact further here.
                cli_ctx.render_structured(data, "eero.network.guest.show/v1")
            elif cli_ctx.is_list_output():
                cli_ctx.renderer.render_text(data, "eero.network.guest.show/v1")
            else:
                content = (
                    f"[bold]Enabled:[/bold] {'[green]Yes[/green]' if enabled else '[dim]No[/dim]'}\n"
                    f"[bold]Name:[/bold] {name or 'N/A'}\n"
                    f"[bold]Password:[/bold] {'********' if has_password else 'N/A'}"
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
    _set_guest_network(cli_ctx, "network guest enable", True, None, None, force)


@guest_group.command(name="disable")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def guest_disable(ctx: click.Context, force: bool) -> None:
    """Disable guest network."""
    cli_ctx = get_cli_context(ctx)
    _set_guest_network(cli_ctx, "network guest disable", False, None, None, force)


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
    _set_guest_network(cli_ctx, "network guest set", True, name, password, force)


async def _write_guest_password(
    client: EeroClient, password: str, network_id: Optional[str]
) -> bool:
    """Call the SDK's live-verified `set_guest_password` and report acceptance.

    Shared by `guest set --password` (which keeps calling this after its own
    `network guest set` confirmation) and `guest password set` (which has its
    own `network guest password set` WriteSpec), so both entry points issue
    the exact same write (migration plan §4 phase B row 26).
    """
    result = await client.set_guest_password(password, network_id)
    meta = result.get("meta", {}) if isinstance(result, dict) else {}
    return meta.get("code") == 200 or bool(result)


def _set_guest_network(
    cli_ctx: EeroCliContext,
    command: str,
    enable: bool,
    name: Optional[str],
    password: Optional[str],
    force: bool,
) -> None:
    """Set guest network settings."""
    console = cli_ctx.console
    action = "enable" if enable else "disable"
    effective_force = force or cli_ctx.force
    spec = get_write_spec(command)
    cli_ctx.active_write_spec = spec
    # A pure enable/disable toggle (no --name/--password) is a candidate for
    # the read-first skip-unchanged path; `guest set` always writes, since a
    # name/password change has no single boolean to compare against.
    is_pure_toggle = name is None and password is None

    try:
        require_write_confirmation(
            spec,
            target="network",
            ctx=SafetyContext(
                force=effective_force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_guest(client: EeroClient) -> None:
            if is_pure_toggle:
                # No --name/--password: a plain enable/disable toggle, so
                # read-first/skip-unchanged applies (nothing else to write).

                async def read() -> bool:
                    with cli_ctx.status("Reading current guest network settings..."):
                        raw_network = await client.get_network(cli_ctx.network_id)
                    network = normalize_network(extract_data(raw_network))
                    return bool(network.get("guest_network_enabled", not enable))

                async def write() -> Any:
                    with cli_ctx.status(f"{action.capitalize()}ing guest network..."):
                        return await client.set_guest_network(
                            enabled=enable, name=None, network_id=cli_ctx.network_id
                        )

                await write_if_changed(
                    read,
                    enable,
                    write,
                    force=effective_force,
                    console=cli_ctx.err_console,
                    read_command=spec.read_command,
                )
                return

            # `guest set --name/--password`: always writes, there is no
            # single boolean to compare a "desired" name/password against.
            with cli_ctx.status(f"{action.capitalize()}ing guest network..."):
                result = await client.set_guest_network(
                    enabled=enable,
                    name=name,
                    network_id=cli_ctx.network_id,
                )

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            network_ok = meta.get("code") == 200 or bool(result)

            password_ok = True
            if password is not None:
                with cli_ctx.status("Setting guest network password..."):
                    password_ok = await _write_guest_password(client, password, cli_ctx.network_id)

            if network_ok and password_ok:
                console.print(f"[bold green]Guest network {action}d[/bold green]")
            else:
                console.print(f"[red]Failed to {action} guest network[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_guest)

    asyncio.run(run_cmd())


@guest_group.group(name="password")
@click.pass_context
def guest_password_group(ctx: click.Context) -> None:
    """Manage the guest network's password.

    \b
    Commands:
      set    - Set the guest network password
      clear  - Clear the guest network password
    """
    pass


@guest_password_group.command(name="set")
@click.option(
    "--password",
    help="Guest network password. Omitted, you are prompted (input hidden).",
)
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def guest_password_set(ctx: click.Context, password: Optional[str], force: bool) -> None:
    """Set the guest network's password.

    Disconnects guest clients while the change propagates.

    \b
    Options:
      --password  New guest network password. Omitted, prompts for it
                  (input hidden, confirmed) instead.

    \b
    Examples:
      eero network guest password set --password "welcome123"
      eero network guest password set
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    effective_force = force or cli_ctx.force

    # --non-interactive without --password can never be satisfied (no prompt
    # will run), so this guard stays first, before any confirmation.
    if password is None and cli_ctx.non_interactive:
        console.print("[red]--password is required when --non-interactive is set[/red]")
        sys.exit(ExitCode.USAGE_ERROR)

    spec = get_write_spec("network guest password set")
    cli_ctx.active_write_spec = spec

    try:
        require_write_confirmation(
            spec,
            target="network",
            ctx=SafetyContext(
                force=effective_force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    # Only ask for the password once the write is actually going to happen --
    # a user who declines the confirmation (or fails it) is never prompted
    # for the secret in the first place.
    if password is None:
        # hide_input/confirmation_prompt: the password is never echoed to the
        # terminal, and is not logged or included in --debug output.
        password = click.prompt(
            "Guest network password",
            hide_input=True,
            confirmation_prompt=True,
        )

    async def run_cmd() -> None:
        async def set_password(client: EeroClient) -> None:
            with cli_ctx.status("Setting guest network password..."):
                ok = await _write_guest_password(client, password, cli_ctx.network_id)

            if not ok:
                console.print("[red]Failed to set guest network password[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

            if cli_ctx.is_structured_output():
                cli_ctx.render_structured(
                    {"ok": True, "command": "network guest password set"},
                    "eero.network.guest.password.set/v1",
                )
            else:
                console.print("[bold green]Guest network password set.[/bold green]")
                console.print(f"[dim]Verify with `{spec.read_command}`.[/dim]")

        await run_with_client(set_password)

    asyncio.run(run_cmd())


@guest_password_group.command(name="clear")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def guest_password_clear(ctx: click.Context, force: bool) -> None:
    """Clear the guest network's password.

    Disconnects guest clients while the change propagates.
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    effective_force = force or cli_ctx.force

    spec = get_write_spec("network guest password clear")
    cli_ctx.active_write_spec = spec

    try:
        require_write_confirmation(
            spec,
            target="network",
            ctx=SafetyContext(
                force=effective_force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def clear_password(client: EeroClient) -> None:
            with cli_ctx.status("Clearing guest network password..."):
                result = await client.clear_guest_password(cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            ok = meta.get("code") == 200 or bool(result)

            if not ok:
                console.print("[red]Failed to clear guest network password[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

            if cli_ctx.is_structured_output():
                cli_ctx.render_structured(
                    {"ok": True, "command": "network guest password clear"},
                    "eero.network.guest.password.clear/v1",
                )
            else:
                console.print("[bold green]Guest network password cleared.[/bold green]")
                console.print(f"[dim]Verify with `{spec.read_command}`.[/dim]")

        await run_with_client(clear_password)

    asyncio.run(run_cmd())
