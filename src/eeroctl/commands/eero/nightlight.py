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
import sys

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
                except Exception as e:
                    if isinstance(e, EeroFeatureUnavailableException):
                        console.print(
                            "[yellow]Nightlight is only available on Eero Beacon devices[/yellow]"
                        )
                        sys.exit(ExitCode.FEATURE_UNAVAILABLE)
                    raise

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
                except Exception as e:
                    if isinstance(e, EeroFeatureUnavailableException):
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
                except Exception as e:
                    if isinstance(e, EeroFeatureUnavailableException):
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
@click.argument("eero_identifier")
@click.option("--on-time", required=True, help="Time to turn on (HH:MM)")
@click.option("--off-time", required=True, help="Time to turn off (HH:MM)")
@click.pass_context
def nightlight_schedule(
    ctx: click.Context, eero_identifier: str, on_time: str, off_time: str
) -> None:
    """Set nightlight schedule."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

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
            # `set_nightlight_schedule` forwards `schedule` to the API verbatim,
            # with no interpretation of its shape (eero-api 8.0.1). This is the
            # v7 field shape; unverified -- no Beacon available to confirm
            # (migration plan Q4). `--schedule-json` for a raw override lands in
            # a later phase-C commit.
            schedule = {"enabled": True, "on": on_time, "off": off_time}
            with cli_ctx.status("Setting nightlight schedule..."):
                try:
                    result = await client.set_nightlight_schedule(
                        eero_id_str, schedule, cli_ctx.network_id
                    )
                except Exception as e:
                    if isinstance(e, EeroFeatureUnavailableException):
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
    console = cli_ctx.console

    spec = get_write_spec("eero nightlight override")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target=eero_identifier,
            ctx=SafetyContext(force=cli_ctx.force, non_interactive=cli_ctx.non_interactive),
            console=cli_ctx.console,
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
                except Exception as e:
                    if isinstance(e, EeroFeatureUnavailableException):
                        console.print(
                            "[yellow]Nightlight is only available on Eero Beacon devices[/yellow]"
                        )
                        sys.exit(ExitCode.FEATURE_UNAVAILABLE)
                    raise

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
