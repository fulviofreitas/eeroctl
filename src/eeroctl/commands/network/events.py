"""Events, network-scan, and channel-utilization reads for the Eero CLI.

Commands:
- eero network events    -- get_app_events (client.py:2316)
- eero network scan      -- get_network_scan (client.py:2332)
- eero network channels  -- get_channel_utilization (client.py:2339)

All three are plain, live-verified GETs -- no confirmation, no writes.
`network channels` uses bare `--start`/`--end` (both required, matching the
SDK's keyword-only `start`/`end`) rather than the shared `time_window_options`
group: `get_channel_utilization` has no `cadence` parameter at all, unlike the
insights/data-usage families `time_window_options` was built for (migration
plan §4 conventions paragraph).
"""

import asyncio
from typing import Optional

import click
from eero import EeroClient
from eero.api.events import CHANNEL_UTILIZATION_BANDS

from ...formatting.events import print_channels, print_events, print_scan
from ...options import ISO8601_TIMESTAMP, apply_options, common_options, resolve_time_window
from ...transformers.events import (
    extract_channel_utilization,
    extract_events,
    extract_next_cursor,
    extract_scan,
)
from ...utils import run_with_client


@click.command(name="events")
@click.option(
    "--page-size",
    type=click.IntRange(min=1),
    default=None,
    help="Page size, sent as the `page_size` query parameter.",
)
@click.option(
    "--cursor",
    default=None,
    help="Pagination cursor from a previous page's response (sent as `timestamp`).",
)
@common_options
@click.pass_context
def network_events(
    ctx: click.Context,
    page_size: Optional[int],
    cursor: Optional[str],
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Show recent app events for the network."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_events(client: EeroClient) -> None:
            with cli_ctx.status("Getting network events..."):
                raw = await client.get_app_events(
                    cli_ctx.network_id, page_size=page_size, timestamp=cursor
                )
            data = extract_events(raw)
            print_events(cli_ctx, data, extract_next_cursor(data))

        await run_with_client(get_events)

    asyncio.run(run_cmd())


@click.command(name="scan")
@common_options
@click.pass_context
def network_scan(ctx: click.Context, output: Optional[str], network_id: Optional[str]) -> None:
    """Show the latest channel/neighbour scan."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_scan(client: EeroClient) -> None:
            with cli_ctx.status("Getting network scan..."):
                raw = await client.get_network_scan(cli_ctx.network_id)
            print_scan(cli_ctx, extract_scan(raw))

        await run_with_client(get_scan)

    asyncio.run(run_cmd())


@click.command(name="channels")
@click.option(
    "--start",
    type=ISO8601_TIMESTAMP,
    required=True,
    help="Window start, ISO-8601 UTC (e.g. 2026-09-21T00:00:00Z). Required.",
)
@click.option(
    "--end",
    type=ISO8601_TIMESTAMP,
    required=True,
    help="Window end, ISO-8601 UTC (e.g. 2026-09-21T00:00:00Z). Required.",
)
@click.option(
    "--band",
    type=click.Choice(CHANNEL_UTILIZATION_BANDS),
    default=None,
    help="Restrict to one Wi-Fi band.",
)
@click.option(
    "--eero",
    "eero_id",
    type=int,
    default=None,
    help="Restrict to one eero node (integer eero id).",
)
@click.option(
    "--granularity",
    type=click.IntRange(min=1),
    default=None,
    help="Minutes per sample.",
)
@click.option(
    "--busy-threshold",
    type=click.IntRange(min=1),
    default=None,
    help="Busy-channel percentage threshold.",
)
@common_options
@click.pass_context
def network_channels(
    ctx: click.Context,
    start: str,
    end: str,
    band: Optional[str],
    eero_id: Optional[int],
    granularity: Optional[int],
    busy_threshold: Optional[int],
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Show Wi-Fi channel utilization for a time window."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    start_iso, end_iso = resolve_time_window(start, end, None)

    async def run_cmd() -> None:
        async def get_channels(client: EeroClient) -> None:
            with cli_ctx.status("Getting channel utilization..."):
                raw = await client.get_channel_utilization(
                    cli_ctx.network_id,
                    start=start_iso,
                    end=end_iso,
                    busy_threshold=busy_threshold,
                    eero_id=eero_id,
                    band=band,
                    granularity=granularity,
                )
            print_channels(cli_ctx, extract_channel_utilization(raw))

        await run_with_client(get_channels)

    asyncio.run(run_cmd())
