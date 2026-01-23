"""LED commands for the Eero CLI.

Commands:
- eero eero led show: Show LED status
- eero eero led on: Turn LED on
- eero eero led off: Turn LED off
- eero eero led brightness: Set LED brightness
"""

import asyncio
import sys

import click
from eero import EeroClient
from rich.panel import Panel

from ...context import EeroCliContext, get_cli_context
from ...exit_codes import ExitCode
from ...transformers import extract_data
from ...utils import run_with_client
from .base import resolve_eero_identifier


@click.group(name="led")
@click.pass_context
def led_group(ctx: click.Context) -> None:
    """Manage LED settings.

    \b
    Commands:
      show       - Show LED status
      on         - Turn LED on
      off        - Turn LED off
      brightness - Set LED brightness
    """
    pass


@led_group.command(name="show")
@click.argument("eero_identifier")
@click.pass_context
def led_show(ctx: click.Context, eero_identifier: str) -> None:
    """Show LED status for an Eero node."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_led(client: EeroClient) -> None:
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

            with cli_ctx.status("Getting LED status..."):
                raw_led = await client.get_led_status(eero_id_str, cli_ctx.network_id)

            led_data = extract_data(raw_led) if isinstance(raw_led, dict) else {}

            if cli_ctx.is_json_output():
                renderer.render_json(led_data, "eero.eero.led.show/v1")
            elif cli_ctx.is_list_output():
                renderer.render_text(led_data, "eero.eero.led.show/v1")
            else:
                led_on = led_data.get("led_on", False)
                brightness = led_data.get("led_brightness", 100)

                content = (
                    f"[bold]Status:[/bold] {'[green]On[/green]' if led_on else '[dim]Off[/dim]'}\n"
                    f"[bold]Brightness:[/bold] {brightness}%"
                )
                console.print(Panel(content, title="LED Settings", border_style="blue"))

        await run_with_client(get_led)

    asyncio.run(run_cmd())


@led_group.command(name="on")
@click.argument("eero_identifier")
@click.pass_context
def led_on(ctx: click.Context, eero_identifier: str) -> None:
    """Turn LED on."""
    cli_ctx = get_cli_context(ctx)
    _set_led(cli_ctx, eero_identifier, True)


@led_group.command(name="off")
@click.argument("eero_identifier")
@click.pass_context
def led_off(ctx: click.Context, eero_identifier: str) -> None:
    """Turn LED off."""
    cli_ctx = get_cli_context(ctx)
    _set_led(cli_ctx, eero_identifier, False)


def _set_led(cli_ctx: EeroCliContext, eero_identifier: str, enabled: bool) -> None:
    """Set LED state."""
    console = cli_ctx.console
    action = "on" if enabled else "off"

    async def run_cmd() -> None:
        async def set_led(client: EeroClient) -> None:
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

            with cli_ctx.status(f"Turning LED {action}..."):
                result = await client.set_led(eero_id_str, enabled, cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print(f"[bold green]LED turned {action}[/bold green]")
            else:
                console.print(f"[red]Failed to turn LED {action}[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_led)

    asyncio.run(run_cmd())


@led_group.command(name="brightness")
@click.argument("eero_identifier")
@click.argument("value", type=click.IntRange(0, 100))
@click.pass_context
def led_brightness(ctx: click.Context, eero_identifier: str, value: int) -> None:
    """Set LED brightness (0-100)."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

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

            with cli_ctx.status(f"Setting LED brightness to {value}%..."):
                result = await client.set_led_brightness(eero_id_str, value, cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print(f"[bold green]LED brightness set to {value}%[/bold green]")
            else:
                console.print("[red]Failed to set LED brightness[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_brightness)

    asyncio.run(run_cmd())
