"""Nightlight commands for the Eero CLI (Beacon only).

Commands:
- eero eero nightlight show: Show nightlight settings
- eero eero nightlight on: Turn nightlight on
- eero eero nightlight off: Turn nightlight off
- eero eero nightlight brightness: Set brightness
- eero eero nightlight schedule: Set schedule
- eero eero nightlight override: One-shot brightness override
"""

import asyncio
import json
import sys
from typing import Optional

import click
from eero import EeroClient
from eero.exceptions import EeroFeatureUnavailableException
from rich.panel import Panel

from ...context import EeroCliContext, get_cli_context
from ...exit_codes import ExitCode
from ...safety import SafetyContext, SafetyError, get_write_spec, require_write_confirmation
from ...transformers import extract_data
from ...utils import run_with_client
from .base import resolve_eero_identifier


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
      override   - One-shot brightness override
    """
    pass


@nightlight_group.command(name="show")
@click.argument("eero_identifier")
@click.pass_context
def nightlight_show(ctx: click.Context, eero_identifier: str) -> None:
    """Show nightlight settings."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_nightlight(client: EeroClient) -> None:
            # Resolve eero by ID, serial, or name
            with cli_ctx.status(f"Finding Eero '{eero_identifier}'..."):
                resolved_id, eero = await resolve_eero_identifier(
                    client, eero_identifier, cli_ctx.network_id
                )

            if not resolved_id or not eero:
                console.print(f"[red]Eero '{eero_identifier}' not found[/red]")
                console.print("[dim]Try: eero eero list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            eero_id_str = str(resolved_id)
            with cli_ctx.status("Getting nightlight settings..."):
                try:
                    raw_nl = await client.get_nightlight(eero_id_str, cli_ctx.network_id)
                except EeroFeatureUnavailableException:
                    console.print(
                        "[yellow]Nightlight is only available on Eero Beacon devices[/yellow]"
                    )
                    sys.exit(ExitCode.FEATURE_UNAVAILABLE)

            # `get_nightlight` now GETs the `data.nightlight.url` sub-resource and
            # returns the nightlight object itself, so the settings usually live at
            # `data.*`; tolerate the old `data.nightlight.*` shape too (eero-api
            # 8.0.1, unverified — no Beacon available to confirm).
            _data = extract_data(raw_nl) if isinstance(raw_nl, dict) else {}
            nl_data = _data.get("nightlight", _data) if isinstance(_data, dict) else {}
            if not isinstance(nl_data, dict):
                nl_data = {}

            if cli_ctx.is_json_output():
                renderer.render_json(nl_data, "eero.eero.nightlight.show/v1")
            elif cli_ctx.is_list_output():
                renderer.render_text(nl_data, "eero.eero.nightlight.show/v1")
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
@click.argument("eero_identifier")
@click.pass_context
def nightlight_on(ctx: click.Context, eero_identifier: str) -> None:
    """Turn nightlight on."""
    cli_ctx = get_cli_context(ctx)
    _set_nightlight(cli_ctx, eero_identifier, True)


@nightlight_group.command(name="off")
@click.argument("eero_identifier")
@click.pass_context
def nightlight_off(ctx: click.Context, eero_identifier: str) -> None:
    """Turn nightlight off."""
    cli_ctx = get_cli_context(ctx)
    _set_nightlight(cli_ctx, eero_identifier, False)


def _set_nightlight(cli_ctx: EeroCliContext, eero_identifier: str, enabled: bool) -> None:
    """Set nightlight state."""
    console = cli_ctx.console
    action = "on" if enabled else "off"

    spec = get_write_spec(f"eero nightlight {action}")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target=eero_identifier,
            ctx=SafetyContext(force=cli_ctx.force, non_interactive=cli_ctx.non_interactive),
            console=cli_ctx.err_console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_nl(client: EeroClient) -> None:
            # Resolve eero by ID, serial, or name
            with cli_ctx.status(f"Finding Eero '{eero_identifier}'..."):
                resolved_id, eero = await resolve_eero_identifier(
                    client, eero_identifier, cli_ctx.network_id
                )

            if not resolved_id or not eero:
                console.print(f"[red]Eero '{eero_identifier}' not found[/red]")
                console.print("[dim]Try: eero eero list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            eero_id_str = str(resolved_id)
            with cli_ctx.status(f"Turning nightlight {action}..."):
                try:
                    result = await client.set_nightlight(
                        eero_id_str, enabled=enabled, network_id=cli_ctx.network_id
                    )
                except EeroFeatureUnavailableException:
                    console.print(
                        "[yellow]Nightlight is only available on Eero Beacon devices[/yellow]"
                    )
                    sys.exit(ExitCode.FEATURE_UNAVAILABLE)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print(f"[bold green]Nightlight turned {action}[/bold green]")
            else:
                console.print(f"[red]Failed to turn nightlight {action}[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_nl)

    asyncio.run(run_cmd())


@nightlight_group.command(name="brightness")
@click.argument("eero_identifier")
@click.argument("value", type=click.IntRange(0, 100))
@click.pass_context
def nightlight_brightness(ctx: click.Context, eero_identifier: str, value: int) -> None:
    """Set nightlight brightness (0-100)."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    spec = get_write_spec("eero nightlight brightness")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target=eero_identifier,
            ctx=SafetyContext(force=cli_ctx.force, non_interactive=cli_ctx.non_interactive),
            console=cli_ctx.err_console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_brightness(client: EeroClient) -> None:
            # Resolve eero by ID, serial, or name
            with cli_ctx.status(f"Finding Eero '{eero_identifier}'..."):
                resolved_id, eero = await resolve_eero_identifier(
                    client, eero_identifier, cli_ctx.network_id
                )

            if not resolved_id or not eero:
                console.print(f"[red]Eero '{eero_identifier}' not found[/red]")
                console.print("[dim]Try: eero eero list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            eero_id_str = str(resolved_id)
            with cli_ctx.status(f"Setting nightlight brightness to {value}%..."):
                try:
                    result = await client.set_nightlight_brightness(
                        eero_id_str, value, cli_ctx.network_id
                    )
                except EeroFeatureUnavailableException:
                    console.print(
                        "[yellow]Nightlight is only available on Eero Beacon devices[/yellow]"
                    )
                    sys.exit(ExitCode.FEATURE_UNAVAILABLE)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print(f"[bold green]Nightlight brightness set to {value}%[/bold green]")
            else:
                console.print("[red]Failed to set nightlight brightness[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_brightness)

    asyncio.run(run_cmd())


@nightlight_group.command(name="schedule")
@click.argument("eero_identifier")
@click.option("--on", "on_time", help="Time to turn on (HH:MM)")
@click.option("--off", "off_time", help="Time to turn off (HH:MM)")
@click.option("--disable", is_flag=True, help="Disable the schedule")
@click.option(
    "--schedule-json",
    help="Raw schedule object as JSON, forwarded to the API unchanged",
)
@click.pass_context
def nightlight_schedule(
    ctx: click.Context,
    eero_identifier: str,
    on_time: Optional[str],
    off_time: Optional[str],
    disable: bool,
    schedule_json: Optional[str],
) -> None:
    """Set (or disable) an eero's nightlight schedule.

    The schedule shape is unverified -- no Beacon was available to confirm
    it (migration plan Q4). Exactly one of --on/--off together,
    --disable, or --schedule-json is required.

    \b
    Options:
      --on TEXT             Time to turn on (HH:MM); requires --off
      --off TEXT            Time to turn off (HH:MM); requires --on
      --disable              Disable the schedule
      --schedule-json TEXT   Raw schedule object as JSON, forwarded to the
                              API unchanged -- for shapes --on/--off/
                              --disable do not cover
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.err_console

    on_off_given = on_time is not None or off_time is not None
    modes_given = sum([on_off_given, disable, schedule_json is not None])

    if modes_given == 0:
        console.print("[red]One of --on/--off, --disable, or --schedule-json is required[/red]")
        sys.exit(ExitCode.USAGE_ERROR)
    if modes_given > 1:
        console.print(
            "[red]--on/--off, --disable, and --schedule-json are mutually exclusive[/red]"
        )
        sys.exit(ExitCode.USAGE_ERROR)

    if schedule_json is not None:
        try:
            schedule = json.loads(schedule_json)
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid --schedule-json: {e}[/red]")
            sys.exit(ExitCode.USAGE_ERROR)
        if not isinstance(schedule, dict) or not schedule:
            console.print("[red]--schedule-json must be a non-empty JSON object[/red]")
            sys.exit(ExitCode.USAGE_ERROR)
    elif disable:
        schedule = {"enabled": False}
    else:
        if on_time is None or off_time is None:
            console.print("[red]--on and --off are required together[/red]")
            sys.exit(ExitCode.USAGE_ERROR)
        # v7 field shape; the SDK forwards `schedule` verbatim, with no
        # interpretation of its shape (eero-api 8.0.1, DIGEST §10).
        schedule = {"enabled": True, "on": on_time, "off": off_time}

    spec = get_write_spec("eero nightlight schedule")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target=eero_identifier,
            ctx=SafetyContext(force=cli_ctx.force, non_interactive=cli_ctx.non_interactive),
            console=cli_ctx.err_console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_schedule(client: EeroClient) -> None:
            # Resolve eero by ID, serial, or name
            with cli_ctx.status(f"Finding Eero '{eero_identifier}'..."):
                resolved_id, eero = await resolve_eero_identifier(
                    client, eero_identifier, cli_ctx.network_id
                )

            if not resolved_id or not eero:
                console.print(f"[red]Eero '{eero_identifier}' not found[/red]")
                console.print("[dim]Try: eero eero list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            eero_id_str = str(resolved_id)
            with cli_ctx.status("Setting nightlight schedule..."):
                try:
                    result = await client.set_nightlight_schedule(
                        eero_id_str, schedule, cli_ctx.network_id
                    )
                except EeroFeatureUnavailableException:
                    console.print(
                        "[yellow]Nightlight is only available on Eero Beacon devices[/yellow]"
                    )
                    sys.exit(ExitCode.FEATURE_UNAVAILABLE)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print("[bold green]Nightlight schedule updated.[/bold green]")
            else:
                console.print("[red]Failed to set schedule[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_schedule)

    asyncio.run(run_cmd())


@nightlight_group.command(name="override")
@click.argument("eero_identifier")
@click.option(
    "--brightness", required=True, type=click.IntRange(0, 100), help="Brightness percentage"
)
@click.pass_context
def nightlight_override(ctx: click.Context, eero_identifier: str, brightness: int) -> None:
    """Apply a one-shot nightlight brightness override.

    Distinct from `nightlight brightness`: this calls the SDK's dedicated
    `nightlight_override` action rather than `set_nightlight`.
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.err_console

    spec = get_write_spec("eero nightlight override")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target=eero_identifier,
            ctx=SafetyContext(force=cli_ctx.force, non_interactive=cli_ctx.non_interactive),
            console=cli_ctx.err_console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_override(client: EeroClient) -> None:
            with cli_ctx.status(f"Finding Eero '{eero_identifier}'..."):
                resolved_id, eero = await resolve_eero_identifier(
                    client, eero_identifier, cli_ctx.network_id
                )

            if not resolved_id or not eero:
                console.print(f"[red]Eero '{eero_identifier}' not found[/red]")
                console.print("[dim]Try: eero eero list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            eero_id_str = str(resolved_id)
            with cli_ctx.status(f"Applying nightlight override ({brightness}%)..."):
                try:
                    result = await client.nightlight_override(
                        eero_id_str,
                        brightness_percentage=brightness,
                        network_id=cli_ctx.network_id,
                    )
                except EeroFeatureUnavailableException:
                    console.print(
                        "[yellow]Nightlight is only available on Eero Beacon devices[/yellow]"
                    )
                    sys.exit(ExitCode.FEATURE_UNAVAILABLE)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print(
                    f"[bold green]Nightlight override applied ({brightness}%)[/bold green]"
                )
            else:
                console.print("[red]Failed to apply nightlight override[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_override)

    asyncio.run(run_cmd())
