"""Advanced network commands for the Eero CLI.

Commands:
- eero network routing: Show routing information
- eero network thread: Thread protocol settings
- eero network support: Support and diagnostics
"""

import asyncio
import json
import sys

import click
from eero import EeroClient
from rich.panel import Panel

from ...context import get_cli_context
from ...safety import OperationRisk, SafetyError, confirm_or_fail
from ...utils import run_with_client

# ==================== Routing Subcommand ====================


@click.command(name="routing")
@click.pass_context
def routing_show(ctx: click.Context) -> None:
    """Show routing information."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_routing(client: EeroClient) -> None:
            with cli_ctx.status("Getting routing information..."):
                routing = await client.get_routing(cli_ctx.network_id)

            if cli_ctx.is_json_output():
                renderer.render_json(routing, "eero.network.routing.show/v1")
            elif cli_ctx.is_list_output():
                renderer.render_text(routing, "eero.network.routing.show/v1")
            else:
                console.print(
                    Panel(
                        json.dumps(routing, indent=2),
                        title="Routing Information",
                        border_style="blue",
                    )
                )

        await run_with_client(get_routing)

    asyncio.run(run_cmd())


# ==================== Thread Subcommand Group ====================


@click.group(name="thread")
@click.pass_context
def thread_cmd_group(ctx: click.Context) -> None:
    """Manage Thread protocol settings.

    Thread is used for smart home devices. Enable/disable
    is under security settings.
    """
    pass


@thread_cmd_group.command(name="show")
@click.pass_context
def thread_show(ctx: click.Context) -> None:
    """Show Thread protocol information."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_thread(client: EeroClient) -> None:
            with cli_ctx.status("Getting Thread information..."):
                thread_data = await client.get_thread(cli_ctx.network_id)

            if cli_ctx.is_json_output():
                renderer.render_json(thread_data, "eero.network.thread.show/v1")
            elif cli_ctx.is_list_output():
                renderer.render_text(thread_data, "eero.network.thread.show/v1")
            else:
                console.print(
                    Panel(
                        json.dumps(thread_data, indent=2),
                        title="Thread Protocol",
                        border_style="blue",
                    )
                )

        await run_with_client(get_thread)

    asyncio.run(run_cmd())


# ==================== Support Subcommand Group ====================


@click.group(name="support")
@click.pass_context
def support_group(ctx: click.Context) -> None:
    """Support and diagnostics.

    \b
    Commands:
      show   - Show support information
      bundle - Export support bundle
    """
    pass


@support_group.command(name="show")
@click.pass_context
def support_show(ctx: click.Context) -> None:
    """Show support information."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_support(client: EeroClient) -> None:
            with cli_ctx.status("Getting support information..."):
                support_data = await client.get_support(cli_ctx.network_id)

            if cli_ctx.is_json_output():
                renderer.render_json(support_data, "eero.network.support.show/v1")
            elif cli_ctx.is_list_output():
                renderer.render_text(support_data, "eero.network.support.show/v1")
            else:
                console.print(
                    Panel(
                        json.dumps(support_data, indent=2),
                        title="Support Information",
                        border_style="blue",
                    )
                )

        await run_with_client(get_support)

    asyncio.run(run_cmd())


@support_group.group(name="bundle")
@click.pass_context
def bundle_group(ctx: click.Context) -> None:
    """Manage support bundles."""
    pass


@bundle_group.command(name="export")
@click.option("--out", "-o", required=True, help="Output file path")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def bundle_export(ctx: click.Context, out: str, force: bool) -> None:
    """Export support bundle to file.

    Creates a diagnostic bundle for Eero support.
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    try:
        confirm_or_fail(
            action="export support bundle",
            target=f"to {out}",
            risk=OperationRisk.MEDIUM,
            force=force or cli_ctx.force,
            non_interactive=cli_ctx.non_interactive,
            dry_run=cli_ctx.dry_run,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def export_bundle(client: EeroClient) -> None:
            with cli_ctx.status("Generating support bundle..."):
                support_data = await client.get_support(cli_ctx.network_id)
                diagnostics = await client.get_diagnostics(cli_ctx.network_id)

            bundle = {
                "support": support_data,
                "diagnostics": diagnostics,
            }

            with open(out, "w") as f:
                json.dump(bundle, f, indent=2, default=str)

            console.print(f"[bold green]Support bundle exported to {out}[/bold green]")

        await run_with_client(export_bundle)

    asyncio.run(run_cmd())
