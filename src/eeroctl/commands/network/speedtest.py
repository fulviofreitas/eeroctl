"""Speed test commands for the Eero CLI.

Commands:
- eero network speedtest run: Run a new speed test
- eero network speedtest show: Show last speed test results
- eero network speedtest history: Show speed test history

`show` and `history` both call `get_speed_tests` (client.py:1206) and share
`transformers.speedtest`'s history/latest-entry accessors, so `show` is
exactly `history --limit 1`, taking the newest entry from the same list.
"""

import asyncio
import sys
from typing import Optional

import click
from eero import EeroClient
from rich.panel import Panel

from ...context import get_cli_context
from ...formatting.speedtest import print_speedtest_history
from ...options import ISO8601_TIMESTAMP, apply_options, common_options
from ...safety import SafetyContext, SafetyError, get_write_spec, require_write_confirmation
from ...transformers import extract_data
from ...transformers.speedtest import extract_latest_speed_test, extract_speed_test_history
from ...utils import run_with_client


@click.group(name="speedtest")
@click.pass_context
def speedtest_group(ctx: click.Context) -> None:
    """Run and view speed tests.

    \b
    Commands:
      run     - Run a new speed test
      show    - Show last speed test results
      history - Show speed test history
    """
    pass


@speedtest_group.command(name="run")
@click.pass_context
def speedtest_run(ctx: click.Context) -> None:
    """Run a new speed test."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer
    spec = get_write_spec("network speedtest run")
    cli_ctx.active_write_spec = spec

    try:
        require_write_confirmation(
            spec,
            target="network",
            ctx=SafetyContext(force=cli_ctx.force, non_interactive=cli_ctx.non_interactive),
            console=cli_ctx.err_console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

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

            speed_test = extract_latest_speed_test(raw_history)

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


@speedtest_group.command(name="history")
@click.option(
    "--limit", type=click.IntRange(min=1), default=None, help="Maximum entries to return."
)
@click.option(
    "--start",
    type=ISO8601_TIMESTAMP,
    default=None,
    help="Window start, ISO-8601 UTC (e.g. 2026-09-21T00:00:00Z).",
)
@click.option(
    "--end",
    type=ISO8601_TIMESTAMP,
    default=None,
    help="Window end, ISO-8601 UTC (e.g. 2026-09-21T00:00:00Z).",
)
@common_options
@click.pass_context
def speedtest_history(
    ctx: click.Context,
    limit: Optional[int],
    start: Optional[str],
    end: Optional[str],
    output: Optional[str],
    network_id: Optional[str],
) -> None:
    """Show speed test history."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_history(client: EeroClient) -> None:
            with cli_ctx.status("Getting speed test history..."):
                raw = await client.get_speed_tests(
                    cli_ctx.network_id, limit=limit, start_time=start, end_time=end
                )
            print_speedtest_history(cli_ctx, extract_speed_test_history(raw))

        await run_with_client(get_history)

    asyncio.run(run_cmd())
