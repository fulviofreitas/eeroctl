"""SQM (Smart Queue Management) commands for the Eero CLI.

Commands:
- eero network sqm show: Show SQM settings
- eero network sqm enable: Enable SQM
- eero network sqm disable: Disable SQM
- eero network sqm set: Configure bandwidth limits
"""

import asyncio
import sys
from typing import Optional

import click
from eero import EeroClient
from rich.panel import Panel

from ...context import EeroCliContext, get_cli_context
from ...exit_codes import ExitCode
from ...safety import OperationRisk, SafetyError, confirm_or_fail
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
      set     - Configure bandwidth limits

    \b
    Examples:
      eero network sqm show
      eero network sqm enable
      eero network sqm set --upload 50 --download 200
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
                sqm_data = await client.get_sqm_settings(cli_ctx.network_id)

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
                result = await client.set_sqm_enabled(enable, cli_ctx.network_id)

            if result:
                console.print(f"[bold green]SQM {action}d[/bold green]")
            else:
                console.print(f"[red]Failed to {action} SQM[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_sqm)

    asyncio.run(run_cmd())


@sqm_group.command(name="set")
@click.option("--upload", "-u", type=int, help="Upload bandwidth limit (Mbps)")
@click.option("--download", "-d", type=int, help="Download bandwidth limit (Mbps)")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def sqm_set(
    ctx: click.Context, upload: Optional[int], download: Optional[int], force: bool
) -> None:
    """Configure SQM bandwidth limits.

    \b
    Options:
      --upload, -u    Upload bandwidth in Mbps
      --download, -d  Download bandwidth in Mbps

    \b
    Examples:
      eero network sqm set --upload 50 --download 200
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    if upload is None and download is None:
        console.print("[yellow]Specify --upload and/or --download[/yellow]")
        sys.exit(ExitCode.USAGE_ERROR)

    try:
        confirm_or_fail(
            action="configure SQM",
            target=f"upload={upload}Mbps download={download}Mbps",
            risk=OperationRisk.MEDIUM,
            force=force or cli_ctx.force,
            non_interactive=cli_ctx.non_interactive,
            dry_run=cli_ctx.dry_run,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def configure_sqm(client: EeroClient) -> None:
            with cli_ctx.status("Configuring SQM..."):
                result = await client.configure_sqm(
                    enabled=True,
                    upload_mbps=upload,
                    download_mbps=download,
                    network_id=cli_ctx.network_id,
                )

            if result:
                msg_parts = []
                if upload:
                    msg_parts.append(f"Upload={upload}Mbps")
                if download:
                    msg_parts.append(f"Download={download}Mbps")
                console.print(f"[bold green]SQM configured: {' '.join(msg_parts)}[/bold green]")
            else:
                console.print("[red]Failed to configure SQM[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(configure_sqm)

    asyncio.run(run_cmd())
