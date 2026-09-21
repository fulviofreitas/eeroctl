"""SQM (Smart Queue Management) commands for the Eero CLI.

Commands:
- eero network sqm show: Show SQM settings
- eero network sqm enable: Enable SQM
- eero network sqm disable: Disable SQM

Note: `network sqm set` (bandwidth limits) was removed in eero-api 8.0.1 --
`configure_sqm`/`set_sqm_bandwidth`/`set_sqm_auto` have no v8 replacement, the
API exposes no bandwidth fields on SQM.
"""

import asyncio
import sys

import click
from eero import EeroClient
from rich.panel import Panel

from ...context import EeroCliContext, get_cli_context
from ...exit_codes import ExitCode
from ...safety import OperationRisk, SafetyError, confirm_or_fail
from ...transformers import extract_data
from ...utils import run_with_client


@click.group(name="sqm")
@click.pass_context
def sqm_group(ctx: click.Context) -> None:
    """Manage Smart Queue Management (SQM) / QoS settings.

    \b
    Commands:
      show    - Show SQM settings
      enable  - Enable SQM
      disable - Disable SQM

    \b
    Examples:
      eero network sqm show
      eero network sqm enable
    """
    pass


@sqm_group.command(name="show")
@click.pass_context
def sqm_show(ctx: click.Context) -> None:
    """Show SQM settings."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_sqm(client: EeroClient) -> None:
            with cli_ctx.status("Getting SQM settings..."):
                raw_sqm = await client.get_sqm_settings(cli_ctx.network_id)

            sqm_data = extract_data(raw_sqm) if isinstance(raw_sqm, dict) else {}

            if cli_ctx.is_json_output():
                renderer.render_json(sqm_data, "eero.network.sqm.show/v1")
            elif cli_ctx.is_list_output():
                renderer.render_text(sqm_data, "eero.network.sqm.show/v1")
            else:
                enabled = sqm_data.get("enabled", False)
                upload_bw = sqm_data.get("upload_bandwidth")
                download_bw = sqm_data.get("download_bandwidth")

                content = (
                    f"[bold]Enabled:[/bold] {'[green]Yes[/green]' if enabled else '[dim]No[/dim]'}"
                )
                if upload_bw:
                    content += f"\n[bold]Upload:[/bold] {upload_bw} Mbps"
                if download_bw:
                    content += f"\n[bold]Download:[/bold] {download_bw} Mbps"

                console.print(Panel(content, title="SQM Settings", border_style="blue"))

        await run_with_client(get_sqm)

    asyncio.run(run_cmd())


@sqm_group.command(name="enable")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def sqm_enable(ctx: click.Context, force: bool) -> None:
    """Enable SQM."""
    cli_ctx = get_cli_context(ctx)
    _set_sqm_enabled(cli_ctx, True, force)


@sqm_group.command(name="disable")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def sqm_disable(ctx: click.Context, force: bool) -> None:
    """Disable SQM."""
    cli_ctx = get_cli_context(ctx)
    _set_sqm_enabled(cli_ctx, False, force)


def _set_sqm_enabled(cli_ctx: EeroCliContext, enable: bool, force: bool) -> None:
    """Enable or disable SQM."""
    console = cli_ctx.console
    action = "enable" if enable else "disable"

    try:
        confirm_or_fail(
            action=f"{action} SQM",
            target="network",
            risk=OperationRisk.MEDIUM,
            force=force or cli_ctx.force,
            non_interactive=cli_ctx.non_interactive,
            dry_run=cli_ctx.dry_run,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_sqm(client: EeroClient) -> None:
            with cli_ctx.status(f"{action.capitalize()}ing SQM..."):
                result = await client.set_sqm(enable, cli_ctx.network_id)

            if result:
                console.print(f"[bold green]SQM {action}d[/bold green]")
            else:
                console.print(f"[red]Failed to {action} SQM[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_sqm)

    asyncio.run(run_cmd())
