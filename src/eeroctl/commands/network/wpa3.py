"""WPA3-per-band read/write for the Eero CLI.

Commands:
- eero network wpa3 show -- get_wpa3_per_band (client.py:2736)
- eero network wpa3 set  -- set_wpa3_per_band (client.py:2743)

Distinct from the existing `network security wpa3 enable/disable` whole-network
toggle (`set_wpa3`, client.py:2210): this is the newer per-band read/write
family. `set_wpa3_per_band` is a mesh-reboot write (migration plan §3.1, §4
phase C row 30) and requires at least one of `band_2_4_ghz`/`band_5_ghz`
(SDK: `EeroValidationException("wpa3_per_band", "at least one of
band_2_4_ghz, band_5_ghz must be supplied")`, `wpa3.py:149` -- eeroctl
enforces the same rule client-side, before any prompt, per v8.0.1's
no-empty-update convention, migration plan §1.5).
"""

import asyncio
import sys
from typing import Any, Optional, Tuple

import click
from eero import EeroClient

from ...const import WPA3_MODES
from ...exit_codes import ExitCode
from ...formatting.wpa3 import print_wpa3_per_band
from ...options import apply_options, common_options, force_option, network_option
from ...safety import SafetyContext, SafetyError, get_write_spec, require_write_confirmation
from ...transformers import extract_data
from ...transformers.wpa3 import extract_wpa3_per_band
from ...utils import run_with_client, write_if_changed


@click.group(name="wpa3")
@click.pass_context
def wpa3_per_band_group(ctx: click.Context) -> None:
    """Manage WPA3 per-band settings.

    \b
    Commands:
      show - Current per-band WPA3 mode
      set  - Set the per-band WPA3 mode (reboots the mesh)
    """
    pass


@wpa3_per_band_group.command(name="show")
@common_options
@click.pass_context
def wpa3_per_band_show(
    ctx: click.Context, output: Optional[str], network_id: Optional[str]
) -> None:
    """Show the current per-band WPA3 mode."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_wpa3(client: EeroClient) -> None:
            with cli_ctx.status("Getting WPA3 per-band settings..."):
                raw = await client.get_wpa3_per_band(cli_ctx.network_id)
            print_wpa3_per_band(cli_ctx, extract_wpa3_per_band(raw))

        await run_with_client(get_wpa3)

    asyncio.run(run_cmd())


@wpa3_per_band_group.command(name="set")
@click.option(
    "--band-2-4",
    "band_2_4",
    type=click.Choice(WPA3_MODES),
    default=None,
    help="New WPA3 mode for the 2.4 GHz band.",
)
@click.option(
    "--band-5",
    "band_5",
    type=click.Choice(WPA3_MODES),
    default=None,
    help="New WPA3 mode for the 5 GHz band.",
)
@force_option
@network_option
@click.pass_context
def wpa3_per_band_set(
    ctx: click.Context,
    band_2_4: Optional[str],
    band_5: Optional[str],
    force: Optional[bool],
    network_id: Optional[str],
) -> None:
    """Set the per-band WPA3 mode.

    Reboots every eero on the network. At least one of --band-2-4/--band-5
    is required.

    \b
    Options:
      --band-2-4 [WPA2|WPA2_WPA3|WPA3]  New mode for the 2.4 GHz band
      --band-5   [WPA2|WPA2_WPA3|WPA3]  New mode for the 5 GHz band
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.err_console

    if band_2_4 is None and band_5 is None:
        console.print("[red]At least one of --band-2-4/--band-5 is required[/red]")
        sys.exit(ExitCode.USAGE_ERROR)

    spec = get_write_spec("network wpa3 set")
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
        async def set_wpa3(client: EeroClient) -> None:
            async def read() -> Tuple[Any, Any]:
                with cli_ctx.status("Reading current WPA3 per-band settings..."):
                    raw = await client.get_wpa3_per_band(cli_ctx.network_id)
                data = extract_data(raw) if isinstance(raw, dict) else {}
                return (data.get("band_2_4_ghz"), data.get("band_5_ghz"))

            def compare(current: Tuple[Any, Any], desired: Tuple[Any, Any]) -> bool:
                c24, c5 = current
                d24, d5 = desired
                return (d24 is None or d24 == c24) and (d5 is None or d5 == c5)

            async def write() -> Any:
                with cli_ctx.status("Setting WPA3 per-band mode..."):
                    return await client.set_wpa3_per_band(
                        cli_ctx.network_id,
                        band_2_4_ghz=band_2_4,
                        band_5_ghz=band_5,
                    )

            await write_if_changed(
                read,
                (band_2_4, band_5),
                write,
                compare=compare,
                force=cli_ctx.force,
                console=console,
                read_command=spec.read_command,
            )

        await run_with_client(set_wpa3)

    asyncio.run(run_cmd())
