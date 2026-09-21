"""Update commands for the Eero CLI.

Commands:
- eero eero updates show: Show update status
- eero eero updates check: Check for updates
- eero eero updates apply: Apply a pending update
"""

import asyncio
import sys
from typing import Optional

import click
from eero import EeroClient
from rich.panel import Panel

from ...context import get_cli_context
from ...exit_codes import ExitCode
from ...options import apply_options, force_option, network_option
from ...safety import SafetyContext, SafetyError, get_write_spec, require_write_confirmation
from ...transformers import extract_data
from ...utils import run_with_client


@click.group(name="updates")
@click.pass_context
def updates_group(ctx: click.Context) -> None:
    """Manage updates.

    \b
    Commands:
      show  - Show update status
      check - Check for updates
      apply - Apply a pending update
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
    console = cli_ctx.console

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
            console=cli_ctx.console,
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
