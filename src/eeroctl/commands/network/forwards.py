"""Port forwarding commands for the Eero CLI.

Commands:
- eero network forwards list: List all port forwards
- eero network forwards show: Show details of a port forward
"""

import asyncio
import sys

import click
from eero import EeroClient
from rich.panel import Panel
from rich.table import Table

from ...context import get_cli_context
from ...exit_codes import ExitCode
from ...transformers import extract_list
from ...utils import run_with_client


@click.group(name="forwards")
@click.pass_context
def forwards_group(ctx: click.Context) -> None:
    """Manage port forwarding rules.

    \b
    Commands:
      list   - List all port forwards
      show   - Show details of a port forward
      add    - Add a new port forward (stub)
      delete - Delete a port forward (stub)
    """
    pass


@forwards_group.command(name="list")
@click.pass_context
def forwards_list(ctx: click.Context) -> None:
    """List all port forwarding rules."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_forwards(client: EeroClient) -> None:
            with cli_ctx.status("Getting port forwards..."):
                raw_response = await client.get_forwards(cli_ctx.network_id)

            # Extract forwards list from raw response
            forwards = extract_list(raw_response, "forwards")

            if cli_ctx.is_json_output():
                renderer.render_json(raw_response, "eero.network.forwards.list/v1")
            else:
                if not forwards:
                    console.print("[yellow]No port forwards configured[/yellow]")
                    return

                table = Table(title="Port Forwards")
                table.add_column("ID", style="dim")
                table.add_column("Name", style="cyan")
                table.add_column("External Port")
                table.add_column("Internal IP")
                table.add_column("Internal Port")
                table.add_column("Protocol")

                for fwd in forwards:
                    table.add_row(
                        str(fwd.get("id", "")),
                        fwd.get("name", ""),
                        str(fwd.get("external_port", "")),
                        fwd.get("internal_ip", ""),
                        str(fwd.get("internal_port", "")),
                        fwd.get("protocol", "tcp"),
                    )

                console.print(table)

        await run_with_client(get_forwards)

    asyncio.run(run_cmd())


@forwards_group.command(name="show")
@click.argument("forward_id")
@click.pass_context
def forwards_show(ctx: click.Context, forward_id: str) -> None:
    """Show details of a port forward."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_forward(client: EeroClient) -> None:
            with cli_ctx.status("Getting port forward..."):
                raw_response = await client.get_forwards(cli_ctx.network_id)

            # Extract forwards list from raw response
            forwards = extract_list(raw_response, "forwards")

            target = None
            for fwd in forwards:
                if str(fwd.get("id")) == forward_id:
                    target = fwd
                    break

            if not target:
                console.print(f"[red]Port forward '{forward_id}' not found[/red]")
                sys.exit(ExitCode.NOT_FOUND)

            if cli_ctx.is_json_output():
                renderer.render_json(target, "eero.network.forwards.show/v1")
            else:
                content = "\n".join(f"[bold]{k}:[/bold] {v}" for k, v in target.items())
                console.print(
                    Panel(content, title=f"Port Forward: {forward_id}", border_style="blue")
                )

        await run_with_client(get_forward)

    asyncio.run(run_cmd())
