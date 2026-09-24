"""Notification reads and writes for the Eero CLI.

Commands:
- eero network notifications show      -- get_notification_settings (client.py:2378)
- eero network notifications unread    -- has_unread_notifications (client.py:2399)
- eero network notifications history   -- get_notification_history (client.py:2413)
- eero network notifications set       -- set_notification_settings (client.py:2385)
- eero network notifications mark-read -- mark_notifications_read (client.py:2406)

`show`/`unread`/`history` are plain, live-verified GETs -- no confirmation, no
writes. `set`/`mark-read` are unverified writes (migration plan §4 phase C,
`network notifications set` row).
"""

import asyncio
import sys
from typing import Any, Dict, Optional, Tuple

import click
from eero import EeroClient

from ...context import ensure_cli_context, get_cli_context
from ...exit_codes import ExitCode
from ...formatting.notifications import (
    print_notification_history,
    print_notification_settings,
    print_unread,
)
from ...options import apply_options, common_options, force_option, network_option
from ...safety import SafetyContext, SafetyError, get_write_spec, require_write_confirmation
from ...transformers import extract_data
from ...transformers.notifications import (
    extract_history_next_cursor,
    extract_notification_history,
    extract_notification_settings,
    extract_unread,
)
from ...utils import parse_bool_key_value_pairs, run_with_client, write_if_changed


@click.group(name="notifications")
@click.pass_context
def notifications_group(ctx: click.Context) -> None:
    """Manage notification settings and history.

    \b
    Commands:
      show      - Per-event notification settings
      unread    - Whether there are unread notifications
      history   - Notification history
      set       - Update per-event notification settings
      mark-read - Mark all notifications as read

    \b
    Examples:
      eero network notifications show
      eero network notifications history --cursor <value>
      eero network notifications set --set weekly_digest=false
    """
    ensure_cli_context(ctx)


@notifications_group.command(name="show")
@common_options
@click.pass_context
def notifications_show(
    ctx: click.Context, output: Optional[str], network_id: Optional[str]
) -> None:
    """Show per-event notification settings."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_settings(client: EeroClient) -> None:
            with cli_ctx.status("Getting notification settings..."):
                raw = await client.get_notification_settings(cli_ctx.network_id)
            print_notification_settings(cli_ctx, extract_notification_settings(raw))

        await run_with_client(get_settings)

    asyncio.run(run_cmd())


@notifications_group.command(name="unread")
@common_options
@click.pass_context
def notifications_unread(
    ctx: click.Context, output: Optional[str], network_id: Optional[str]
) -> None:
    """Show whether the network has unread notifications."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_unread(client: EeroClient) -> None:
            with cli_ctx.status("Checking unread notifications..."):
                raw = await client.has_unread_notifications(cli_ctx.network_id)
            print_unread(cli_ctx, extract_unread(raw))

        await run_with_client(get_unread)

    asyncio.run(run_cmd())


@notifications_group.command(name="history")
@click.option(
    "--cursor",
    default=None,
    help="Pagination cursor from a previous page's response (sent as `timestamp`).",
)
@common_options
@click.pass_context
def notifications_history(
    ctx: click.Context,
    cursor: Optional[str],
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Show notification history."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_history(client: EeroClient) -> None:
            with cli_ctx.status("Getting notification history..."):
                raw = await client.get_notification_history(cli_ctx.network_id, timestamp=cursor)
            data = extract_notification_history(raw)
            print_notification_history(cli_ctx, data, extract_history_next_cursor(data))

        await run_with_client(get_history)

    asyncio.run(run_cmd())


# ==================== Notification writes (phase C) ====================


@notifications_group.command(name="set")
@click.option(
    "--set",
    "set_pairs",
    multiple=True,
    metavar="KEY=VALUE",
    help="Setting to change, as KEY=VALUE (true/false/1/0). Repeatable.",
)
@force_option
@network_option
@click.pass_context
def notifications_set(
    ctx: click.Context,
    set_pairs: Tuple[str, ...],
    force: Optional[bool],
    network_id: Optional[str],
) -> None:
    """Update per-event notification settings.

    Every KEY must already exist in `network notifications show`'s current
    settings -- an unknown key exits with a usage error rather than being
    silently added.

    \b
    Examples:
      eero network notifications set --set weekly_digest=false
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.err_console
    updates = parse_bool_key_value_pairs(console, set_pairs)

    spec = get_write_spec("network notifications set")
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
            console=console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_settings(client: EeroClient) -> None:
            with cli_ctx.status("Reading current notification settings..."):
                raw = await client.get_notification_settings(cli_ctx.network_id)
            data = extract_data(raw) if isinstance(raw, dict) else {}
            current: Dict[str, Any] = data if isinstance(data, dict) else {}

            unknown = sorted(key for key in updates if key not in current)
            if unknown:
                console.print(f"[red]Unknown notification setting(s): {', '.join(unknown)}[/red]")
                sys.exit(ExitCode.USAGE_ERROR)

            async def read() -> Dict[str, Any]:
                return {key: current.get(key) for key in updates}

            async def write() -> Any:
                merged = {**current, **updates}
                with cli_ctx.status("Updating notification settings..."):
                    return await client.set_notification_settings(merged, cli_ctx.network_id)

            await write_if_changed(
                read,
                updates,
                write,
                force=cli_ctx.force,
                console=console,
                read_command=spec.read_command,
            )

        await run_with_client(set_settings)

    asyncio.run(run_cmd())


@notifications_group.command(name="mark-read")
@force_option
@network_option
@click.pass_context
def notifications_mark_read(
    ctx: click.Context, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Mark all notifications as read."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.err_console
    effective_force = force or cli_ctx.force

    spec = get_write_spec("network notifications mark-read")
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
            console=console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def mark_read(client: EeroClient) -> None:
            with cli_ctx.status("Marking notifications as read..."):
                result = await client.mark_notifications_read(cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print("[bold green]Notifications marked as read.[/bold green]")
            else:
                console.print("[red]Failed to mark notifications as read[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(mark_read)

    asyncio.run(run_cmd())
