"""Activity commands for the Eero CLI (Eero Plus feature).

Commands:
- eero activity history: Historical activity data (get_insights)
- eero activity categories: Activity by category (get_insights, blocked)
- eero activity devices: Per-device insights (get_devices_insights)
- eero activity device <id>: One device's insights (get_device_insights)
- eero activity profiles: Per-profile insights (get_profiles_insights)
- eero activity profile <id>[--devices]: One profile's (or its devices')
  insights (get_profile_insights / get_profile_devices_insights)

`history`/`categories` predate the `time_window_options` decorator
(commit 10) and are not rewired onto it here: their `--start`/`--end` are
required flags with no defaulting and their `--cadence` choice set includes
`"weekly"` (accepted by the CLI, rejected by the SDK -- a pre-existing,
untouched quirk), while `time_window_options`'s `--start`/`--end` are always
optional with defaulting and its `cadence_choices` would have to narrow to
`("hourly", "daily")` to match what the SDK actually validates. Either
change is a behavioural change to already-tested, documented flags, not the
"small change" the brief allows for -- so they are left as-is here.

`devices`/`device`/`profiles`/`profile` below are new phase-A commands and
do use `time_window_options(cadence_required=True, cadence_choices=
("hourly", "daily"))`, matching what their five facade methods actually
require (§4 conventions paragraph). They also use `run_with_client`
(the phase-A convention) rather than `history`/`categories`'s `with_client`,
so `EeroAccessDeniedException` gets the standard exit-4 mapping.
"""

import asyncio
import sys
from typing import Optional

import click
from eero import EeroClient
from eero.exceptions import EeroPremiumRequiredException
from rich.table import Table

from ..context import ensure_cli_context
from ..exit_codes import ExitCode
from ..formatting.activity import (
    print_device_insights,
    print_devices_insights,
    print_profile_devices_insights,
    print_profile_insights,
    print_profiles_insights,
)
from ..options import (
    apply_options,
    common_options,
    network_option,
    output_option,
    resolve_time_window,
    time_window_options,
)
from ..transformers import extract_devices, extract_profiles
from ..transformers.activity import extract_insights
from ..utils import run_with_client, with_client
from .device import _find_device
from .profile import _find_profile

_INSIGHT_TYPE_CHOICES = ("adblock", "blocked", "inspected")
"""Valid `insight_type` values (`eero/api/insights.py:110-113`, live-observed)."""


@click.group(name="activity")
@click.pass_context
def activity_group(ctx: click.Context) -> None:
    """View network activity data (Eero Plus feature).

    \b
    Commands:
      history    - Historical activity (requires --start and --end)
      categories - Blocked-traffic activity by category (requires --start and --end)
      devices    - Per-device insights
      device     - One device's insights
      profiles   - Per-profile insights
      profile    - One profile's (or its devices') insights

    \b
    Note: Requires an active Eero Plus subscription.

    \b
    Examples:
      eero activity history --start 2026-07-01 --end 2026-07-22
      eero activity categories --start 2026-07-01 --end 2026-07-22 --cadence weekly
      eero activity devices --cadence daily --insight-type inspected \\
          --start 2026-09-01T00:00:00Z --end 2026-09-21T00:00:00Z
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
            if isinstance(e, EeroPremiumRequiredException):
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
            if isinstance(e, EeroPremiumRequiredException):
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


# ==================== Devices / Profiles insights (phase A) ====================


@activity_group.command(name="devices")
@time_window_options(cadence_required=True, cadence_choices=("hourly", "daily"))
@click.option(
    "--insight-type",
    type=click.Choice(_INSIGHT_TYPE_CHOICES),
    required=True,
    help="Category to query.",
)
@common_options
@click.pass_context
def activity_devices(
    ctx: click.Context,
    start: Optional[str],
    end: Optional[str],
    cadence: str,
    insight_type: str,
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Show per-device activity insights."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    start_iso, end_iso = resolve_time_window(start, end, cadence)

    async def run_cmd() -> None:
        async def get_devices_insights(client: EeroClient) -> None:
            with cli_ctx.status("Getting per-device insights..."):
                raw = await client.get_devices_insights(
                    cli_ctx.network_id,
                    start=start_iso,
                    end=end_iso,
                    cadence=cadence,
                    insight_type=insight_type,
                )
            print_devices_insights(cli_ctx, extract_insights(raw))

        await run_with_client(get_devices_insights)

    asyncio.run(run_cmd())


@activity_group.command(name="device")
@click.argument("device_identifier")
@time_window_options(cadence_required=True, cadence_choices=("hourly", "daily"))
@click.option(
    "--insight-type",
    type=click.Choice(_INSIGHT_TYPE_CHOICES),
    required=True,
    help="Category to query.",
)
@common_options
@click.pass_context
def activity_device(
    ctx: click.Context,
    device_identifier: str,
    start: Optional[str],
    end: Optional[str],
    cadence: str,
    insight_type: str,
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Show one device's activity insights.

    \b
    Arguments:
      DEVICE_IDENTIFIER  Device ID, MAC address, or name
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console
    start_iso, end_iso = resolve_time_window(start, end, cadence)

    async def run_cmd() -> None:
        async def get_device_insights(client: EeroClient) -> None:
            with cli_ctx.status("Finding device..."):
                raw_devices = await client.get_devices(cli_ctx.network_id)
            target = _find_device(extract_devices(raw_devices), device_identifier)

            if not target or not target.get("id"):
                console.print(f"[red]Device '{device_identifier}' not found[/red]")
                console.print("[dim]Try: eero device list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            with cli_ctx.status("Getting device insights..."):
                raw = await client.get_device_insights(
                    target["id"],
                    cli_ctx.network_id,
                    start=start_iso,
                    end=end_iso,
                    cadence=cadence,
                    insight_type=insight_type,
                )
            print_device_insights(cli_ctx, extract_insights(raw))

        await run_with_client(get_device_insights)

    asyncio.run(run_cmd())


@activity_group.command(name="profiles")
@time_window_options(cadence_required=True, cadence_choices=("hourly", "daily"))
@click.option(
    "--insight-type",
    type=click.Choice(_INSIGHT_TYPE_CHOICES),
    required=True,
    help="Category to query.",
)
@common_options
@click.pass_context
def activity_profiles(
    ctx: click.Context,
    start: Optional[str],
    end: Optional[str],
    cadence: str,
    insight_type: str,
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Show per-profile activity insights."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    start_iso, end_iso = resolve_time_window(start, end, cadence)

    async def run_cmd() -> None:
        async def get_profiles_insights(client: EeroClient) -> None:
            with cli_ctx.status("Getting per-profile insights..."):
                raw = await client.get_profiles_insights(
                    cli_ctx.network_id,
                    start=start_iso,
                    end=end_iso,
                    cadence=cadence,
                    insight_type=insight_type,
                )
            print_profiles_insights(cli_ctx, extract_insights(raw))

        await run_with_client(get_profiles_insights)

    asyncio.run(run_cmd())


@activity_group.command(name="profile")
@click.argument("profile_identifier")
@click.option(
    "--devices",
    "show_devices",
    is_flag=True,
    default=False,
    help="Show the profile's per-device insights instead of the profile's own.",
)
@time_window_options(cadence_required=True, cadence_choices=("hourly", "daily"))
@click.option(
    "--insight-type",
    type=click.Choice(_INSIGHT_TYPE_CHOICES),
    required=True,
    help="Category to query.",
)
@common_options
@click.pass_context
def activity_profile(
    ctx: click.Context,
    profile_identifier: str,
    show_devices: bool,
    start: Optional[str],
    end: Optional[str],
    cadence: str,
    insight_type: str,
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Show one profile's activity insights.

    \b
    Arguments:
      PROFILE_IDENTIFIER  Profile ID or name

    \b
    Options:
      --devices  Show the profile's per-device insights instead
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console
    start_iso, end_iso = resolve_time_window(start, end, cadence)

    async def run_cmd() -> None:
        async def get_profile_insights(client: EeroClient) -> None:
            with cli_ctx.status("Finding profile..."):
                raw_profiles = await client.get_profiles(cli_ctx.network_id)
            target = _find_profile(extract_profiles(raw_profiles), profile_identifier)

            if not target or not target.get("id"):
                console.print(f"[red]Profile '{profile_identifier}' not found[/red]")
                console.print("[dim]Try: eero profile list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            if show_devices:
                with cli_ctx.status("Getting profile device insights..."):
                    raw = await client.get_profile_devices_insights(
                        target["id"],
                        cli_ctx.network_id,
                        start=start_iso,
                        end=end_iso,
                        cadence=cadence,
                        insight_type=insight_type,
                    )
                print_profile_devices_insights(cli_ctx, extract_insights(raw))
            else:
                with cli_ctx.status("Getting profile insights..."):
                    raw = await client.get_profile_insights(
                        target["id"],
                        cli_ctx.network_id,
                        start=start_iso,
                        end=end_iso,
                        cadence=cadence,
                        insight_type=insight_type,
                    )
                print_profile_insights(cli_ctx, extract_insights(raw))

        await run_with_client(get_profile_insights)

    asyncio.run(run_cmd())
