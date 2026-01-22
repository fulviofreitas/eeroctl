"""Nightlight commands for the Eero CLI (Beacon only).

Commands:
- eero eero nightlight show: Show nightlight settings
- eero eero nightlight on: Turn nightlight on
- eero eero nightlight off: Turn nightlight off
- eero eero nightlight brightness: Set brightness
- eero eero nightlight schedule: Set schedule
"""

import asyncio
import sys

import click
from eero import EeroClient
from eero.exceptions import EeroNotFoundException
from rich.panel import Panel

from ...context import EeroCliContext, get_cli_context
from ...errors import is_feature_unavailable_error
from ...exit_codes import ExitCode
from ...transformers import extract_data, normalize_eero
from ...utils import run_with_client


@click.group(name="nightlight")
@click.pass_context
def nightlight_group(ctx: click.Context) -> None:
    """Manage nightlight (Eero Beacon only).

    \b
    Commands:
      show       - Show nightlight settings
      on         - Turn nightlight on
      off        - Turn nightlight off
      brightness - Set brightness
      schedule   - Set schedule
    """
    pass


@nightlight_group.command(name="show")
@click.argument("eero_id")
@click.pass_context
def nightlight_show(ctx: click.Context, eero_id: str) -> None:
    """Show nightlight settings."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_nightlight(client: EeroClient) -> None:
            # Resolve eero first (by ID, serial, location, or MAC)
            with cli_ctx.status(f"Finding Eero '{eero_id}'..."):
                try:
                    raw_eero = await client.get_eero(eero_id, cli_ctx.network_id)
                except EeroNotFoundException:
                    console.print(f"[red]Eero '{eero_id}' not found[/red]")
                    sys.exit(ExitCode.NOT_FOUND)

            eero = normalize_eero(extract_data(raw_eero))

            eero_id_str = str(eero.get("id") or "")
            with cli_ctx.status("Getting nightlight settings..."):
                try:
                    raw_nl = await client.get_nightlight(eero_id_str, cli_ctx.network_id)
                except Exception as e:
                    if is_feature_unavailable_error(e, "beacon"):
                        console.print(
                            "[yellow]Nightlight is only available on Eero Beacon devices[/yellow]"
                        )
                        sys.exit(ExitCode.FEATURE_UNAVAILABLE)
                    raise

            nl_data = extract_data(raw_nl) if isinstance(raw_nl, dict) else {}

            if cli_ctx.is_json_output():
                renderer.render_json(nl_data, "eero.eero.nightlight.show/v1")
            else:
                enabled = nl_data.get("enabled", False)
                brightness = nl_data.get("brightness", 100)
                schedule_enabled = nl_data.get("schedule_enabled", False)

                content = (
                    f"[bold]Enabled:[/bold] {'[green]Yes[/green]' if enabled else '[dim]No[/dim]'}\n"
                    f"[bold]Brightness:[/bold] {brightness}%"
                )
                if schedule_enabled:
                    on_time = nl_data.get("on_time", "N/A")
                    off_time = nl_data.get("off_time", "N/A")
                    content += f"\n[bold]Schedule:[/bold] {on_time} - {off_time}"

                console.print(Panel(content, title="Nightlight Settings", border_style="blue"))

        await run_with_client(get_nightlight)

    asyncio.run(run_cmd())


@nightlight_group.command(name="on")
@click.argument("eero_id")
@click.pass_context
def nightlight_on(ctx: click.Context, eero_id: str) -> None:
    """Turn nightlight on."""
    cli_ctx = get_cli_context(ctx)
    _set_nightlight(cli_ctx, eero_id, True)


@nightlight_group.command(name="off")
@click.argument("eero_id")
@click.pass_context
def nightlight_off(ctx: click.Context, eero_id: str) -> None:
    """Turn nightlight off."""
    cli_ctx = get_cli_context(ctx)
    _set_nightlight(cli_ctx, eero_id, False)


def _set_nightlight(cli_ctx: EeroCliContext, eero_id: str, enabled: bool) -> None:
    """Set nightlight state."""
    console = cli_ctx.console
    action = "on" if enabled else "off"

    async def run_cmd() -> None:
        async def set_nl(client: EeroClient) -> None:
            # Resolve eero first (by ID, serial, location, or MAC)
            with cli_ctx.status(f"Finding Eero '{eero_id}'..."):
                try:
                    raw_eero = await client.get_eero(eero_id, cli_ctx.network_id)
                except EeroNotFoundException:
                    console.print(f"[red]Eero '{eero_id}' not found[/red]")
                    sys.exit(ExitCode.NOT_FOUND)

            eero = normalize_eero(extract_data(raw_eero))

            eero_id_str = str(eero.get("id") or "")
            with cli_ctx.status(f"Turning nightlight {action}..."):
                try:
                    result = await client.set_nightlight(
                        eero_id_str, enabled=enabled, network_id=cli_ctx.network_id
                    )
                except Exception as e:
                    if is_feature_unavailable_error(e, "beacon"):
                        console.print(
                            "[yellow]Nightlight is only available on Eero Beacon devices[/yellow]"
                        )
                        sys.exit(ExitCode.FEATURE_UNAVAILABLE)
                    raise

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print(f"[bold green]Nightlight turned {action}[/bold green]")
            else:
                console.print(f"[red]Failed to turn nightlight {action}[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_nl)

    asyncio.run(run_cmd())


@nightlight_group.command(name="brightness")
@click.argument("eero_id")
@click.argument("value", type=click.IntRange(0, 100))
@click.pass_context
def nightlight_brightness(ctx: click.Context, eero_id: str, value: int) -> None:
    """Set nightlight brightness (0-100)."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def set_brightness(client: EeroClient) -> None:
            # Resolve eero first (by ID, serial, location, or MAC)
            with cli_ctx.status(f"Finding Eero '{eero_id}'..."):
                try:
                    raw_eero = await client.get_eero(eero_id, cli_ctx.network_id)
                except EeroNotFoundException:
                    console.print(f"[red]Eero '{eero_id}' not found[/red]")
                    sys.exit(ExitCode.NOT_FOUND)

            eero = normalize_eero(extract_data(raw_eero))

            eero_id_str = str(eero.get("id") or "")
            with cli_ctx.status(f"Setting nightlight brightness to {value}%..."):
                try:
                    # TODO: set_nightlight_brightness method not yet implemented in eero-api
                    result = await client.set_nightlight_brightness(  # type: ignore[attr-defined]
                        eero_id_str, value, cli_ctx.network_id
                    )
                except Exception as e:
                    if is_feature_unavailable_error(e, "beacon"):
                        console.print(
                            "[yellow]Nightlight is only available on Eero Beacon devices[/yellow]"
                        )
                        sys.exit(ExitCode.FEATURE_UNAVAILABLE)
                    raise

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print(f"[bold green]Nightlight brightness set to {value}%[/bold green]")
            else:
                console.print("[red]Failed to set nightlight brightness[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_brightness)

    asyncio.run(run_cmd())


@nightlight_group.command(name="schedule")
@click.argument("eero_id")
@click.option("--on-time", required=True, help="Time to turn on (HH:MM)")
@click.option("--off-time", required=True, help="Time to turn off (HH:MM)")
@click.pass_context
def nightlight_schedule(ctx: click.Context, eero_id: str, on_time: str, off_time: str) -> None:
    """Set nightlight schedule."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def set_schedule(client: EeroClient) -> None:
            # Resolve eero first (by ID, serial, location, or MAC)
            with cli_ctx.status(f"Finding Eero '{eero_id}'..."):
                try:
                    raw_eero = await client.get_eero(eero_id, cli_ctx.network_id)
                except EeroNotFoundException:
                    console.print(f"[red]Eero '{eero_id}' not found[/red]")
                    sys.exit(ExitCode.NOT_FOUND)

            eero = normalize_eero(extract_data(raw_eero))

            eero_id_str = str(eero.get("id") or "")
            with cli_ctx.status("Setting nightlight schedule..."):
                try:
                    # TODO: set_nightlight_schedule method not yet implemented in eero-api
                    result = await client.set_nightlight_schedule(  # type: ignore[attr-defined]
                        eero_id_str, True, on_time, off_time, cli_ctx.network_id
                    )
                except Exception as e:
                    if is_feature_unavailable_error(e, "beacon"):
                        console.print(
                            "[yellow]Nightlight is only available on Eero Beacon devices[/yellow]"
                        )
                        sys.exit(ExitCode.FEATURE_UNAVAILABLE)
                    raise

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print(f"[bold green]Schedule set: {on_time} - {off_time}[/bold green]")
            else:
                console.print("[red]Failed to set schedule[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_schedule)

    asyncio.run(run_cmd())
