"""Activity commands for the Eero CLI (Eero Plus feature).

Commands:
- eero activity summary: Network activity summary
- eero activity clients: Per-client activity
- eero activity history: Historical activity
- eero activity categories: Activity by category
"""

import sys

import click
from eero import EeroClient
from rich.panel import Panel
from rich.table import Table

from ..context import ensure_cli_context, get_cli_context
from ..errors import is_premium_error
from ..exit_codes import ExitCode
from ..utils import with_client


def _format_bytes(bytes_val: int) -> str:
    """Format bytes into human-readable format."""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB"


@click.group(name="activity")
@click.pass_context
def activity_group(ctx: click.Context) -> None:
    """View network activity data (Eero Plus feature).

    \b
    Commands:
      summary    - Network activity summary
      clients    - Per-client activity
      history    - Historical activity
      categories - Activity by category

    \b
    Note: Requires an active Eero Plus subscription.

    \b
    Examples:
      eero activity summary
      eero activity clients
      eero activity history --period week
    """
    ensure_cli_context(ctx)


@activity_group.command(name="summary")
@click.pass_context
@with_client
async def activity_summary(ctx: click.Context, client: EeroClient) -> None:
    """Show network activity summary."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    with cli_ctx.status("Getting network activity..."):
        try:
            activity_data = await client.get_activity(cli_ctx.network_id)
        except Exception as e:
            if is_premium_error(e):
                console.print("[yellow]This feature requires Eero Plus subscription[/yellow]")
                sys.exit(ExitCode.PREMIUM_REQUIRED)
            raise

    if cli_ctx.is_structured_output():
        cli_ctx.render_structured(activity_data, "eero.activity.summary/v1")
    else:
        upload = activity_data.get("upload_bytes", 0)
        download = activity_data.get("download_bytes", 0)
        total = upload + download

        content = (
            f"[bold cyan]Download:[/bold cyan] {_format_bytes(download)}\n"
            f"[bold cyan]Upload:[/bold cyan] {_format_bytes(upload)}\n"
            f"[bold cyan]Total:[/bold cyan] {_format_bytes(total)}"
        )
        console.print(Panel(content, title="Network Activity Summary", border_style="blue"))


@activity_group.command(name="clients")
@click.pass_context
@with_client
async def activity_clients(ctx: click.Context, client: EeroClient) -> None:
    """Show per-client activity data."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    with cli_ctx.status("Getting client activity..."):
        try:
            clients_data = await client.get_activity_clients(cli_ctx.network_id)
        except Exception as e:
            if is_premium_error(e):
                console.print("[yellow]This feature requires Eero Plus subscription[/yellow]")
                sys.exit(ExitCode.PREMIUM_REQUIRED)
            raise

    if cli_ctx.is_structured_output():
        cli_ctx.render_structured(clients_data, "eero.activity.clients/v1")
    else:
        if not clients_data:
            console.print("[yellow]No client activity data available[/yellow]")
            return

        table = Table(title="Client Activity")
        table.add_column("Device", style="cyan")
        table.add_column("Download", justify="right")
        table.add_column("Upload", justify="right")
        table.add_column("Total", justify="right")

        for client_info in clients_data:
            name = (
                client_info.get("display_name")
                or client_info.get("hostname")
                or client_info.get("mac", "Unknown")
            )
            download = client_info.get("download_bytes", 0)
            upload = client_info.get("upload_bytes", 0)
            total = download + upload

            table.add_row(
                name, _format_bytes(download), _format_bytes(upload), _format_bytes(total)
            )

        console.print(table)


@activity_group.command(name="history")
@click.option(
    "--period",
    type=click.Choice(["hour", "day", "week", "month"]),
    default="day",
    help="Time period (default: day)",
)
@click.pass_context
@with_client
async def activity_history(ctx: click.Context, client: EeroClient, period: str) -> None:
    """Show historical activity data.

    \b
    Options:
      --period  Time period: hour, day, week, month
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    with cli_ctx.status(f"Getting activity history ({period})..."):
        try:
            history_data = await client.get_activity_history(cli_ctx.network_id, period)
        except Exception as e:
            if is_premium_error(e):
                console.print("[yellow]This feature requires Eero Plus subscription[/yellow]")
                sys.exit(ExitCode.PREMIUM_REQUIRED)
            raise

    if cli_ctx.is_structured_output():
        cli_ctx.render_structured(history_data, "eero.activity.history/v1")
    else:
        total_download = history_data.get("total_download_bytes", 0)
        total_upload = history_data.get("total_upload_bytes", 0)
        data_points = history_data.get("data_points", [])

        content = (
            f"[bold]Period:[/bold] {period}\n"
            f"[bold cyan]Total Download:[/bold cyan] {_format_bytes(total_download)}\n"
            f"[bold cyan]Total Upload:[/bold cyan] {_format_bytes(total_upload)}\n"
            f"[bold]Data Points:[/bold] {len(data_points)}"
        )
        console.print(Panel(content, title=f"Activity History ({period})", border_style="blue"))


@activity_group.command(name="categories")
@click.pass_context
@with_client
async def activity_categories(ctx: click.Context, client: EeroClient) -> None:
    """Show activity grouped by category."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    with cli_ctx.status("Getting activity categories..."):
        try:
            categories_data = await client.get_activity_categories(cli_ctx.network_id)
        except Exception as e:
            if is_premium_error(e):
                console.print("[yellow]This feature requires Eero Plus subscription[/yellow]")
                sys.exit(ExitCode.PREMIUM_REQUIRED)
            raise

    if cli_ctx.is_structured_output():
        cli_ctx.render_structured(categories_data, "eero.activity.categories/v1")
    else:
        if not categories_data:
            console.print("[yellow]No category data available[/yellow]")
            return

        table = Table(title="Activity by Category")
        table.add_column("Category", style="cyan")
        table.add_column("Usage", justify="right")

        for category in categories_data:
            name = category.get("name", "Unknown")
            usage = category.get("bytes", 0)
            table.add_row(name, _format_bytes(usage))

        console.print(table)
