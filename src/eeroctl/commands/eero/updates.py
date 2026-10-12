"""Update commands for the Eero CLI.

Commands:
- eero eero updates show: Show update status
- eero eero updates check: Check for updates
- eero eero updates apply: Apply a pending update
- eero eero updates hour set: Set the preferred update hour
"""

import asyncio
import sys
from typing import Any, Optional

import click
from eero import EeroClient
from rich.panel import Panel

from ...context import get_cli_context
from ...exit_codes import ExitCode
from ...options import apply_options, force_option, network_option
from ...safety import SafetyContext, SafetyError, get_write_spec, require_write_confirmation
from ...transformers import extract_data
from ...utils import run_with_client, write_if_changed


@click.group(name="updates")
@click.pass_context
def updates_group(ctx: click.Context) -> None:
    """Manage updates.

    \b
    Commands:
      show  - Show update status
      check - Check for updates
      apply - Apply a pending update
      hour  - Preferred update hour
    """
    pass


@updates_group.command(name="show")
@click.pass_context
def updates_show(ctx: click.Context) -> None:
    """Show update status."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_updates(client: EeroClient) -> None:
            with cli_ctx.status("Getting update status..."):
                raw_updates = await client.get_updates(cli_ctx.network_id)

            updates = extract_data(raw_updates) if isinstance(raw_updates, dict) else {}

            if cli_ctx.is_json_output():
                renderer.render_json(updates, "eero.eero.updates.show/v1")
            elif cli_ctx.is_list_output():
                renderer.render_text(updates, "eero.eero.updates.show/v1")
            else:
                has_update = updates.get("has_update", False)
                target = updates.get("target_firmware", "N/A")

                content = (
                    f"[bold]Update Available:[/bold] "
                    f"{'[green]Yes[/green]' if has_update else '[dim]No[/dim]'}\n"
                    f"[bold]Target Firmware:[/bold] {target}"
                )
                hour = updates.get("preferred_update_hour")
                if hour is not None:
                    content += f"\n[bold]Preferred Update Hour:[/bold] {hour}"
                console.print(Panel(content, title="Update Status", border_style="blue"))

        await run_with_client(get_updates)

    asyncio.run(run_cmd())


@updates_group.command(name="check")
@click.pass_context
def updates_check(ctx: click.Context) -> None:
    """Check for available updates."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def check_updates(client: EeroClient) -> None:
            with cli_ctx.status("Checking for updates..."):
                raw_updates = await client.get_updates(cli_ctx.network_id)

            updates = extract_data(raw_updates) if isinstance(raw_updates, dict) else {}

            has_update = updates.get("has_update", False)
            if has_update:
                target = updates.get("target_firmware", "N/A")
                console.print(f"[bold green]Update available: {target}[/bold green]")
            else:
                console.print("[dim]No updates available[/dim]")

        await run_with_client(check_updates)

    asyncio.run(run_cmd())


@updates_group.command(name="apply")
@force_option
@network_option
@click.pass_context
def updates_apply(ctx: click.Context, force: Optional[bool], network_id: Optional[str]) -> None:
    """Apply a pending update.

    Reboots every node on the network.
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.err_console

    spec = get_write_spec("eero updates apply")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target="network",
            ctx=SafetyContext(
                force=cli_ctx.force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
            console=cli_ctx.err_console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def apply_update(client: EeroClient) -> None:
            # No read-first: applying an update has no idempotent "already
            # applied" state to compare against before issuing the write.
            with cli_ctx.status("Applying update..."):
                result = await client.apply_update(cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print("[bold green]Update applied.[/bold green]")
            else:
                console.print("[red]Failed to apply update[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(apply_update)

    asyncio.run(run_cmd())


@updates_group.group(name="hour")
@click.pass_context
def hour_group(ctx: click.Context) -> None:
    """Manage the preferred update hour.

    \b
    Commands:
      set - Set the hour of day updates are applied
    """
    pass


@hour_group.command(name="set")
@click.argument("hour", type=click.IntRange(0, 23))
@force_option
@network_option
@click.pass_context
def hour_set(
    ctx: click.Context, hour: int, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Set the hour of day the network applies updates.

    \b
    Arguments:
      HOUR  0 (midnight to 1am) through 23 (11pm to midnight), in the
            network's timezone
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)

    spec = get_write_spec("eero updates hour set")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target=f"{hour}:00",
            ctx=SafetyContext(
                force=cli_ctx.force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
            console=cli_ctx.err_console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_hour(client: EeroClient) -> None:
            async def read() -> Optional[int]:
                with cli_ctx.status("Reading current update hour..."):
                    raw_network = await client.get_network(cli_ctx.network_id)
                net_data = extract_data(raw_network) if isinstance(raw_network, dict) else {}
                updates = net_data.get("updates")
                return updates.get("preferred_update_hour") if isinstance(updates, dict) else None

            async def write() -> Any:
                with cli_ctx.status(f"Setting update hour to {hour}..."):
                    return await client.set_preferred_update_hour(hour, cli_ctx.network_id)

            # Typed to match `read`: an unknown current hour (None) never matches.
            desired: Optional[int] = hour
            await write_if_changed(
                read,
                desired,
                write,
                force=cli_ctx.force,
                console=cli_ctx.err_console,
                read_command=spec.read_command,
            )

        await run_with_client(set_hour)

    asyncio.run(run_cmd())
