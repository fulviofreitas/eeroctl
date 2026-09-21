"""Notification reads for the Eero CLI.

Commands:
- eero network notifications show    -- get_notification_settings (client.py:2378)
- eero network notifications unread  -- has_unread_notifications (client.py:2399)
- eero network notifications history -- get_notification_history (client.py:2413)

All three are plain, live-verified GETs -- no confirmation, no writes.
"""

import asyncio
from typing import Optional

import click
from eero import EeroClient

from ...context import ensure_cli_context
from ...formatting.notifications import (
    print_notification_history,
    print_notification_settings,
    print_unread,
)
from ...options import apply_options, common_options
from ...transformers.notifications import (
    extract_history_next_cursor,
    extract_notification_history,
    extract_notification_settings,
    extract_unread,
)
from ...utils import run_with_client


@click.group(name="notifications")
@click.pass_context
def notifications_group(ctx: click.Context) -> None:
    """View notification settings and history.

    \b
    Commands:
      show    - Per-event notification settings
      unread  - Whether there are unread notifications
      history - Notification history

    \b
    Examples:
      eero network notifications show
      eero network notifications history --cursor <value>
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
