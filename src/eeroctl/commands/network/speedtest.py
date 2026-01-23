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
from ...transformers import extract_data, normalize_network
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
            with cli_ctx.status("Running speed test (this may take a minute)..."):
                raw_result = await client.run_speed_test(cli_ctx.network_id)

            result = extract_data(raw_result) if isinstance(raw_result, dict) else {}

            if cli_ctx.is_json_output():
                renderer.render_json(result, "eero.network.speedtest.run/v1")
            else:
                download = result.get("down", {}).get("value", 0)
                upload = result.get("up", {}).get("value", 0)
                latency = result.get("latency", {}).get("value", 0)

                content = (
                    f"[bold]Download:[/bold] {download} Mbps\n"
                    f"[bold]Upload:[/bold] {upload} Mbps\n"
                    f"[bold]Latency:[/bold] {latency} ms"
                )
                console.print(Panel(content, title="Speed Test Results", border_style="green"))

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
                raw_network = await client.get_network(cli_ctx.network_id)

            network = normalize_network(extract_data(raw_network))
            speed_test = network.get("speed_test")

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
