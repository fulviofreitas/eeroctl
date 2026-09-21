"""Speed test commands for the Eero CLI.

Commands:
- eero network speedtest run: Run a new speed test
- eero network speedtest show: Show last speed test results
"""

import asyncio

import click
from eero import EeroClient
from rich.panel import Panel

from ...context import get_cli_context
from ...transformers import extract_data
from ...utils import run_with_client


@click.group(name="speedtest")
@click.pass_context
def speedtest_group(ctx: click.Context) -> None:
    """Run and view speed tests.

    \b
    Commands:
      run   - Run a new speed test
      show  - Show last speed test results
    """
    pass


@speedtest_group.command(name="run")
@click.pass_context
def speedtest_run(ctx: click.Context) -> None:
    """Run a new speed test."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def run_test(client: EeroClient) -> None:
            with cli_ctx.status("Starting speed test..."):
                raw_result = await client.run_speed_test(cli_ctx.network_id)

            # `run_speed_test` returns 202 with `data: null` (eero-api 8.0.1) --
            # the test runs asynchronously; there is nothing to unwrap here.
            result = extract_data(raw_result) if isinstance(raw_result, dict) else {}

            if cli_ctx.is_json_output():
                renderer.render_json(result or {}, "eero.network.speedtest.run/v1")
            else:
                console.print("[bold green]Speed test started[/bold green]")
                console.print("[dim]Check results with: eero network speedtest show[/dim]")

        await run_with_client(run_test)

    asyncio.run(run_cmd())


@speedtest_group.command(name="show")
@click.pass_context
def speedtest_show(ctx: click.Context) -> None:
    """Show last speed test results."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_results(client: EeroClient) -> None:
            with cli_ctx.status("Getting speed test results..."):
                raw_history = await client.get_speed_tests(cli_ctx.network_id, limit=1)

            history_data = extract_data(raw_history) if isinstance(raw_history, dict) else None
            if isinstance(history_data, list):
                speed_test = history_data[0] if history_data else None
            elif isinstance(history_data, dict):
                speed_test = history_data
            else:
                speed_test = None

            if not speed_test:
                console.print("[yellow]No speed test results available[/yellow]")
                return

            if cli_ctx.is_json_output():
                renderer.render_json(speed_test, "eero.network.speedtest.show/v1")
            elif cli_ctx.is_list_output():
                renderer.render_text(speed_test, "eero.network.speedtest.show/v1")
            else:
                download = speed_test.get("down", {}).get("value", 0)
                upload = speed_test.get("up", {}).get("value", 0)
                latency = speed_test.get("latency", {}).get("value", 0)
                tested = speed_test.get("date", "Unknown")

                content = (
                    f"[bold]Download:[/bold] {download} Mbps\n"
                    f"[bold]Upload:[/bold] {upload} Mbps\n"
                    f"[bold]Latency:[/bold] {latency} ms\n"
                    f"[bold]Tested:[/bold] {tested}"
                )
                console.print(Panel(content, title="Speed Test Results", border_style="blue"))

        await run_with_client(get_results)

    asyncio.run(run_cmd())
