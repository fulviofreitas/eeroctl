"""Data-usage reads for the Eero CLI (closes #46).

Commands:
- eero network usage summary            -- get_data_usage (client.py:1578,
  cadence required)
- eero network usage breakdown          -- get_data_usage_breakdown
  (client.py:1605, cadence optional)
- eero network usage devices [--profile] -- get_devices_data_usage
  (client.py:1624, cadence optional)
- eero network usage device <mac>       -- get_device_data_usage
  (client.py:1649, cadence required)
- eero network usage eeros              -- get_eeros_data_usage_summary
  (client.py:1669, cadence required)
- eero network usage eero <id>          -- get_eero_data_usage
  (client.py:1688, cadence required)
- eero network usage profile <id>       -- get_profile_data_usage
  (client.py:1708, cadence required)
- eero network usage unprofiled [--summary] -- get_unprofiled_devices_data_usage
  / get_unprofiled_data_usage_summary (client.py:1728/1747; the CLI requires
  --cadence for both, even though the devices variant's cadence is optional
  at the SDK layer, to keep one flag contract across the flag)
- eero network usage report show        -- get_data_usage_report_settings
  (client.py:1766, no time window)

All time-windowed commands use `time_window_options(include_timezone=True)`;
`--timezone` maps straight to the facade's `timezone` kwarg.
"""

import asyncio
from typing import Optional

import click
from eero import EeroClient

from ...formatting.data_usage import (
    print_data_usage_breakdown,
    print_data_usage_report_settings,
    print_data_usage_summary,
    print_device_data_usage,
    print_devices_data_usage,
    print_eero_data_usage,
    print_eeros_data_usage_summary,
    print_profile_data_usage,
    print_unprofiled_data_usage_summary,
    print_unprofiled_devices_data_usage,
)
from ...options import apply_options, common_options, resolve_time_window, time_window_options
from ...transformers.data_usage import extract_data_usage
from ...utils import run_with_client


@click.group(name="usage")
@click.pass_context
def usage_group(ctx: click.Context) -> None:
    """View network data usage (closes #46).

    \b
    Commands:
      summary     - Network-wide data usage
      breakdown   - Data usage breakdown
      devices     - Per-device data usage
      device      - One device's data usage (by MAC)
      eeros       - Per-eero data usage summary
      eero        - One eero's data usage
      profile     - One profile's data usage
      unprofiled  - Unprofiled-device data usage
      report      - Data usage report settings
    """
    pass


@usage_group.command(name="summary")
@time_window_options(cadence_required=True, include_timezone=True)
@common_options
@click.pass_context
def usage_summary(
    ctx: click.Context,
    start: Optional[str],
    end: Optional[str],
    cadence: str,
    timezone: Optional[str],
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Show network-wide data usage."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    start_iso, end_iso = resolve_time_window(start, end, cadence)

    async def run_cmd() -> None:
        async def get_usage(client: EeroClient) -> None:
            with cli_ctx.status("Getting data usage..."):
                raw = await client.get_data_usage(
                    cli_ctx.network_id,
                    start=start_iso,
                    end=end_iso,
                    cadence=cadence,
                    timezone=timezone,
                )
            print_data_usage_summary(cli_ctx, extract_data_usage(raw))

        await run_with_client(get_usage)

    asyncio.run(run_cmd())


@usage_group.command(name="breakdown")
@time_window_options(include_timezone=True)
@common_options
@click.pass_context
def usage_breakdown(
    ctx: click.Context,
    start: Optional[str],
    end: Optional[str],
    cadence: Optional[str],
    timezone: Optional[str],
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Show data usage breakdown."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    start_iso, end_iso = resolve_time_window(start, end, cadence)

    async def run_cmd() -> None:
        async def get_breakdown(client: EeroClient) -> None:
            with cli_ctx.status("Getting data usage breakdown..."):
                raw = await client.get_data_usage_breakdown(
                    cli_ctx.network_id,
                    start=start_iso,
                    end=end_iso,
                    cadence=cadence,
                    timezone=timezone,
                )
            print_data_usage_breakdown(cli_ctx, extract_data_usage(raw))

        await run_with_client(get_breakdown)

    asyncio.run(run_cmd())


@usage_group.command(name="devices")
@click.option("--profile", "profile_id", default=None, help="Restrict to one profile's devices.")
@time_window_options(include_timezone=True)
@common_options
@click.pass_context
def usage_devices(
    ctx: click.Context,
    profile_id: Optional[str],
    start: Optional[str],
    end: Optional[str],
    cadence: Optional[str],
    timezone: Optional[str],
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Show per-device data usage."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    start_iso, end_iso = resolve_time_window(start, end, cadence)

    async def run_cmd() -> None:
        async def get_devices_usage(client: EeroClient) -> None:
            with cli_ctx.status("Getting per-device data usage..."):
                raw = await client.get_devices_data_usage(
                    cli_ctx.network_id,
                    start=start_iso,
                    end=end_iso,
                    cadence=cadence,
                    timezone=timezone,
                    profile_id=profile_id,
                )
            print_devices_data_usage(cli_ctx, extract_data_usage(raw))

        await run_with_client(get_devices_usage)

    asyncio.run(run_cmd())


@usage_group.command(name="device")
@click.argument("device_mac")
@time_window_options(cadence_required=True, include_timezone=True)
@common_options
@click.pass_context
def usage_device(
    ctx: click.Context,
    device_mac: str,
    start: Optional[str],
    end: Optional[str],
    cadence: str,
    timezone: Optional[str],
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Show one device's data usage.

    \b
    Arguments:
      DEVICE_MAC  The device's MAC address
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    start_iso, end_iso = resolve_time_window(start, end, cadence)

    async def run_cmd() -> None:
        async def get_device_usage(client: EeroClient) -> None:
            with cli_ctx.status(f"Getting data usage for {device_mac}..."):
                raw = await client.get_device_data_usage(
                    device_mac,
                    cli_ctx.network_id,
                    start=start_iso,
                    end=end_iso,
                    cadence=cadence,
                    timezone=timezone,
                )
            print_device_data_usage(cli_ctx, extract_data_usage(raw))

        await run_with_client(get_device_usage)

    asyncio.run(run_cmd())


@usage_group.command(name="eeros")
@time_window_options(cadence_required=True, include_timezone=True)
@common_options
@click.pass_context
def usage_eeros(
    ctx: click.Context,
    start: Optional[str],
    end: Optional[str],
    cadence: str,
    timezone: Optional[str],
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Show per-eero data usage summary."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    start_iso, end_iso = resolve_time_window(start, end, cadence)

    async def run_cmd() -> None:
        async def get_eeros_usage(client: EeroClient) -> None:
            with cli_ctx.status("Getting per-eero data usage summary..."):
                raw = await client.get_eeros_data_usage_summary(
                    cli_ctx.network_id,
                    start=start_iso,
                    end=end_iso,
                    cadence=cadence,
                    timezone=timezone,
                )
            print_eeros_data_usage_summary(cli_ctx, extract_data_usage(raw))

        await run_with_client(get_eeros_usage)

    asyncio.run(run_cmd())


@usage_group.command(name="eero")
@click.argument("eero_id")
@time_window_options(cadence_required=True, include_timezone=True)
@common_options
@click.pass_context
def usage_eero(
    ctx: click.Context,
    eero_id: str,
    start: Optional[str],
    end: Optional[str],
    cadence: str,
    timezone: Optional[str],
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Show one eero's data usage.

    \b
    Arguments:
      EERO_ID  Bare eero id (see 'eero eero list')
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    start_iso, end_iso = resolve_time_window(start, end, cadence)

    async def run_cmd() -> None:
        async def get_eero_usage(client: EeroClient) -> None:
            with cli_ctx.status(f"Getting data usage for eero {eero_id}..."):
                raw = await client.get_eero_data_usage(
                    eero_id,
                    cli_ctx.network_id,
                    start=start_iso,
                    end=end_iso,
                    cadence=cadence,
                    timezone=timezone,
                )
            print_eero_data_usage(cli_ctx, extract_data_usage(raw))

        await run_with_client(get_eero_usage)

    asyncio.run(run_cmd())


@usage_group.command(name="profile")
@click.argument("profile_id")
@time_window_options(cadence_required=True, include_timezone=True)
@common_options
@click.pass_context
def usage_profile(
    ctx: click.Context,
    profile_id: str,
    start: Optional[str],
    end: Optional[str],
    cadence: str,
    timezone: Optional[str],
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Show one profile's data usage.

    \b
    Arguments:
      PROFILE_ID  Bare profile id (see 'eero profile list')
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    start_iso, end_iso = resolve_time_window(start, end, cadence)

    async def run_cmd() -> None:
        async def get_profile_usage(client: EeroClient) -> None:
            with cli_ctx.status(f"Getting data usage for profile {profile_id}..."):
                raw = await client.get_profile_data_usage(
                    profile_id,
                    cli_ctx.network_id,
                    start=start_iso,
                    end=end_iso,
                    cadence=cadence,
                    timezone=timezone,
                )
            print_profile_data_usage(cli_ctx, extract_data_usage(raw))

        await run_with_client(get_profile_usage)

    asyncio.run(run_cmd())


@usage_group.command(name="unprofiled")
@click.option(
    "--summary",
    "show_summary",
    is_flag=True,
    default=False,
    help="Show the unprofiled-devices summary instead of the per-device list.",
)
@time_window_options(cadence_required=True, include_timezone=True)
@common_options
@click.pass_context
def usage_unprofiled(
    ctx: click.Context,
    show_summary: bool,
    start: Optional[str],
    end: Optional[str],
    cadence: str,
    timezone: Optional[str],
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Show unprofiled-device data usage.

    \b
    Options:
      --summary  Show the summary instead of the per-device list
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    start_iso, end_iso = resolve_time_window(start, end, cadence)

    async def run_cmd() -> None:
        async def get_unprofiled_usage(client: EeroClient) -> None:
            if show_summary:
                with cli_ctx.status("Getting unprofiled data usage summary..."):
                    raw = await client.get_unprofiled_data_usage_summary(
                        cli_ctx.network_id,
                        start=start_iso,
                        end=end_iso,
                        cadence=cadence,
                        timezone=timezone,
                    )
                print_unprofiled_data_usage_summary(cli_ctx, extract_data_usage(raw))
            else:
                with cli_ctx.status("Getting unprofiled device data usage..."):
                    raw = await client.get_unprofiled_devices_data_usage(
                        cli_ctx.network_id,
                        start=start_iso,
                        end=end_iso,
                        cadence=cadence,
                        timezone=timezone,
                    )
                print_unprofiled_devices_data_usage(cli_ctx, extract_data_usage(raw))

        await run_with_client(get_unprofiled_usage)

    asyncio.run(run_cmd())


@usage_group.group(name="report")
@click.pass_context
def usage_report_group(ctx: click.Context) -> None:
    """View data usage report settings.

    \b
    Commands:
      show - Current report settings
    """
    pass


@usage_report_group.command(name="show")
@common_options
@click.pass_context
def usage_report_show(ctx: click.Context, output: Optional[str], network_id: Optional[str]) -> None:
    """Show data usage report settings."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_report_settings(client: EeroClient) -> None:
            with cli_ctx.status("Getting data usage report settings..."):
                raw = await client.get_data_usage_report_settings(cli_ctx.network_id)
            print_data_usage_report_settings(cli_ctx, extract_data_usage(raw))

        await run_with_client(get_report_settings)

    asyncio.run(run_cmd())
