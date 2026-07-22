"""Activity commands for the Eero CLI (Eero Plus feature).

Commands:
- eero activity history: Historical activity data (get_insights)
- eero activity categories: Activity by category (get_insights, blocked)
"""

import sys
from typing import Optional

import click
from eero import EeroClient
from rich.table import Table

from ..context import ensure_cli_context
from ..errors import is_premium_error
from ..exit_codes import ExitCode
from ..options import apply_options, network_option, output_option
from ..utils import with_client


@click.group(name="activity")
@click.pass_context
def activity_group(ctx: click.Context) -> None:
    """View network activity data (Eero Plus feature).

    \b
    Commands:
      history    - Historical activity (requires --start and --end)
      categories - Blocked-traffic activity by category (requires --start and --end)

    \b
    Note: Requires an active Eero Plus subscription.

    \b
    Examples:
      eero activity history --start 2026-07-01 --end 2026-07-22
      eero activity categories --start 2026-07-01 --end 2026-07-22 --cadence weekly
    """
    ensure_cli_context(ctx)


@activity_group.command(name="history")
@click.option("--start", required=True, help="Start of window (ISO 8601, e.g. 2026-07-01)")
@click.option("--end", required=True, help="End of window (ISO 8601, e.g. 2026-07-22)")
@click.option(
    "--insight-type",
    type=click.Choice(["adblock", "blocked", "inspected"]),
    default="inspected",
    show_default=True,
    help="Insight type to retrieve.",
)
@click.option(
    "--cadence",
    type=click.Choice(["hourly", "daily", "weekly"]),
    default="daily",
    show_default=True,
    help="Data cadence.",
)
@output_option
@network_option
@click.pass_context
@with_client
async def activity_history(
    ctx: click.Context,
    client: EeroClient,
    start: str,
    end: str,
    insight_type: str,
    cadence: str,
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Show historical activity data.

    \b
    Required:
      --start ISO  Start of the time window (e.g. 2026-07-01)
      --end ISO    End of the time window (e.g. 2026-07-22)

    \b
    Optional:
      --insight-type  adblock | blocked | inspected (default: inspected)
      --cadence       hourly | daily | weekly (default: daily)
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console

    with cli_ctx.status("Getting activity history..."):
        try:
            raw_response = await client.get_insights(
                cli_ctx.network_id,
                start=start,
                end=end,
                insight_type=insight_type,
                cadence=cadence,
            )
        except Exception as e:
            if is_premium_error(e):
                console.print("[yellow]This feature requires Eero Plus subscription[/yellow]")
                sys.exit(ExitCode.PREMIUM_REQUIRED)
            raise

    if cli_ctx.is_structured_output():
        cli_ctx.render_structured(raw_response, "eero.activity.history/v1")
        return

    series = raw_response.get("data", {}).get("series", [])
    if not series:
        console.print("[yellow]No activity data available for the given window[/yellow]")
        return

    table = Table(title=f"Activity History ({insight_type}, {cadence})")
    table.add_column("Insight Type", style="cyan")
    table.add_column("Sum", justify="right", style="green")
    table.add_column("Data Points", justify="right")

    for entry in series:
        table.add_row(
            str(entry.get("insight_type", "")),
            str(entry.get("sum", 0)),
            str(len(entry.get("values", []))),
        )

    console.print(table)


@activity_group.command(name="categories")
@click.option("--start", required=True, help="Start of window (ISO 8601, e.g. 2026-07-01)")
@click.option("--end", required=True, help="End of window (ISO 8601, e.g. 2026-07-22)")
@click.option(
    "--cadence",
    type=click.Choice(["hourly", "daily", "weekly"]),
    default="daily",
    show_default=True,
    help="Data cadence.",
)
@output_option
@network_option
@click.pass_context
@with_client
async def activity_categories(
    ctx: click.Context,
    client: EeroClient,
    start: str,
    end: str,
    cadence: str,
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Show blocked-traffic activity by category.

    \b
    Required:
      --start ISO  Start of the time window (e.g. 2026-07-01)
      --end ISO    End of the time window (e.g. 2026-07-22)

    \b
    Optional:
      --cadence  hourly | daily | weekly (default: daily)
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console

    with cli_ctx.status("Getting activity categories..."):
        try:
            raw_response = await client.get_insights(
                cli_ctx.network_id,
                start=start,
                end=end,
                insight_type="blocked",
                cadence=cadence,
            )
        except Exception as e:
            if is_premium_error(e):
                console.print("[yellow]This feature requires Eero Plus subscription[/yellow]")
                sys.exit(ExitCode.PREMIUM_REQUIRED)
            raise

    if cli_ctx.is_structured_output():
        cli_ctx.render_structured(raw_response, "eero.activity.categories/v1")
        return

    series = raw_response.get("data", {}).get("series", [])
    if not series:
        console.print("[yellow]No category data available for the given window[/yellow]")
        return

    table = Table(title=f"Activity Categories (blocked, {cadence})")
    table.add_column("Insight Type", style="cyan")
    table.add_column("Sum", justify="right", style="green")
    table.add_column("Data Points", justify="right")

    for entry in series:
        table.add_row(
            str(entry.get("insight_type", "")),
            str(entry.get("sum", 0)),
            str(len(entry.get("values", []))),
        )

    console.print(table)
