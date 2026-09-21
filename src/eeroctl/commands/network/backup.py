"""Backup internet commands for the Eero CLI (Eero Plus feature).

Commands:
- eero network backup show: Show backup internet configuration
- eero network backup enable: Enable backup internet
- eero network backup disable: Disable backup internet
- eero network backup status: Show cellular backup usage and events

Note: eero-api 8.0.1 removed `get_backup_network`, `get_backup_status`,
`set_backup_network` and `is_using_backup`; this module is rewired to the new
`get_backup_internet` / `set_backup_internet` / `get_cellular_backup_usage` /
`get_cellular_backup_events` family (client.py:1950-1976).
"""

import asyncio
import json
import sys
from typing import Any, Optional

import click
from eero import EeroClient
from eero.exceptions import EeroException, EeroPremiumRequiredException
from rich.panel import Panel

from ...context import EeroCliContext, get_cli_context
from ...exit_codes import ExitCode
from ...formatting.backup_access_points import (
    print_backup_access_points,
    print_backup_ssid_discovery,
)
from ...options import apply_options, common_options
from ...safety import SafetyContext, SafetyError, get_write_spec, require_write_confirmation
from ...transformers import extract_data
from ...transformers.backup_access_points import (
    extract_backup_access_points,
    extract_backup_ssid_discovery,
)
from ...utils import run_with_client, write_if_changed


@click.group(name="backup")
@click.pass_context
def backup_group(ctx: click.Context) -> None:
    """Manage backup internet (Eero Plus feature).

    \b
    Commands:
      show    - Show backup internet configuration
      enable  - Enable backup internet
      disable - Disable backup internet
      status  - Show cellular backup usage and events
    """
    pass


@backup_group.command(name="show")
@click.pass_context
def backup_show(ctx: click.Context) -> None:
    """Show backup internet configuration."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_backup(client: EeroClient) -> None:
            with cli_ctx.status("Getting backup internet settings..."):
                try:
                    raw_backup = await client.get_backup_internet(cli_ctx.network_id)
                except Exception as e:
                    if isinstance(e, EeroPremiumRequiredException):
                        console.print("[yellow]Backup internet requires Eero Plus[/yellow]")
                        sys.exit(ExitCode.PREMIUM_REQUIRED)
                    raise

            backup_data = extract_data(raw_backup) if isinstance(raw_backup, dict) else {}

            if cli_ctx.is_json_output():
                renderer.render_json(backup_data, "eero.network.backup.show/v1")
            elif cli_ctx.is_list_output():
                renderer.render_text(backup_data, "eero.network.backup.show/v1")
            else:
                enabled = backup_data.get("backup_internet_enabled", backup_data.get("enabled"))
                content = (
                    f"[bold]Enabled:[/bold] {'[green]Yes[/green]' if enabled else '[dim]No[/dim]'}"
                )
                console.print(Panel(content, title="Backup Internet", border_style="blue"))

        await run_with_client(get_backup)

    asyncio.run(run_cmd())


@backup_group.command(name="enable")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def backup_enable(ctx: click.Context, force: bool) -> None:
    """Enable backup internet."""
    cli_ctx = get_cli_context(ctx)
    _set_backup(cli_ctx, True, force)


@backup_group.command(name="disable")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def backup_disable(ctx: click.Context, force: bool) -> None:
    """Disable backup internet."""
    cli_ctx = get_cli_context(ctx)
    _set_backup(cli_ctx, False, force)


def _set_backup(cli_ctx: EeroCliContext, enable: bool, force: bool) -> None:
    """Set backup internet state."""
    console = cli_ctx.console
    action = "enable" if enable else "disable"
    effective_force = force or cli_ctx.force
    spec = get_write_spec(f"network backup {action}")
    cli_ctx.active_write_spec = spec

    try:
        require_write_confirmation(
            spec,
            target="network",
            ctx=SafetyContext(
                force=effective_force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_backup(client: EeroClient) -> None:
            async def read() -> bool:
                with cli_ctx.status("Reading current backup internet settings..."):
                    try:
                        raw_backup = await client.get_backup_internet(cli_ctx.network_id)
                    except EeroException as e:
                        if isinstance(e, EeroPremiumRequiredException):
                            console.print("[yellow]Backup internet requires Eero Plus[/yellow]")
                            sys.exit(ExitCode.PREMIUM_REQUIRED)
                        raise
                backup_data = extract_data(raw_backup) if isinstance(raw_backup, dict) else {}
                return bool(
                    backup_data.get(
                        "backup_internet_enabled", backup_data.get("enabled", not enable)
                    )
                )

            async def write() -> Any:
                with cli_ctx.status(f"{action.capitalize()}ing backup internet..."):
                    try:
                        return await client.set_backup_internet(enable, cli_ctx.network_id)
                    except EeroException as e:
                        if isinstance(e, EeroPremiumRequiredException):
                            console.print("[yellow]Backup internet requires Eero Plus[/yellow]")
                            sys.exit(ExitCode.PREMIUM_REQUIRED)
                        raise

            await write_if_changed(
                read,
                enable,
                write,
                force=effective_force,
                console=cli_ctx.err_console,
                read_command=spec.read_command,
            )

        await run_with_client(set_backup)

    asyncio.run(run_cmd())


@backup_group.command(name="status")
@click.pass_context
def backup_status(ctx: click.Context) -> None:
    """Show cellular backup usage and events."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_status(client: EeroClient) -> None:
            with cli_ctx.status("Getting cellular backup status..."):
                try:
                    raw_usage = await client.get_cellular_backup_usage(cli_ctx.network_id)
                    raw_events = await client.get_cellular_backup_events(cli_ctx.network_id)
                except Exception as e:
                    if isinstance(e, EeroPremiumRequiredException):
                        console.print("[yellow]Backup internet requires Eero Plus[/yellow]")
                        sys.exit(ExitCode.PREMIUM_REQUIRED)
                    raise

            usage_data = extract_data(raw_usage) if isinstance(raw_usage, dict) else {}
            events_data = extract_data(raw_events) if isinstance(raw_events, dict) else {}
            status_output = {"usage": usage_data, "events": events_data}

            if cli_ctx.is_json_output():
                renderer.render_json(status_output, "eero.network.backup.status/v1")
            elif cli_ctx.is_list_output():
                renderer.render_text(status_output, "eero.network.backup.status/v1")
            else:
                # Shapes are undocumented (eero-api 8.0.1); render with the
                # same generic key/value dump used elsewhere for undocumented
                # data instead of f-string `repr()`-ing the raw dicts.
                console.print(
                    Panel(
                        json.dumps(status_output, indent=2, default=str),
                        title="Backup Status",
                        border_style="blue",
                    )
                )

        await run_with_client(get_status)

    asyncio.run(run_cmd())


# ==================== Backup Access Points (read-only, phase A) ====================
#
# list_backup_access_points/discover_backup_ssids (client.py:2910/2974) are
# GETs; commit 5 already rewired `backup show`/`backup status` above onto the
# get_backup_internet/get_cellular_backup_* family and left this family
# alone. add/update/delete/rearrange/discover-start/connectivity-check are
# phase C.


@backup_group.group(name="access-points")
@click.pass_context
def backup_access_points_group(ctx: click.Context) -> None:
    """View backup access points (Eero Plus feature).

    \b
    Commands:
      list     - List configured backup access points
      discover - Discover nearby backup SSIDs
    """
    pass


@backup_access_points_group.command(name="list")
@common_options
@click.pass_context
def backup_access_points_list(
    ctx: click.Context, output: Optional[str], network_id: Optional[str]
) -> None:
    """List configured backup access points."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_access_points(client: EeroClient) -> None:
            with cli_ctx.status("Getting backup access points..."):
                raw = await client.list_backup_access_points(cli_ctx.network_id)
            print_backup_access_points(cli_ctx, extract_backup_access_points(raw))

        await run_with_client(get_access_points)

    asyncio.run(run_cmd())


@backup_access_points_group.command(name="discover")
@common_options
@click.pass_context
def backup_access_points_discover(
    ctx: click.Context, output: Optional[str], network_id: Optional[str]
) -> None:
    """Discover nearby backup SSIDs."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def discover(client: EeroClient) -> None:
            with cli_ctx.status("Discovering backup SSIDs..."):
                raw = await client.discover_backup_ssids(cli_ctx.network_id)
            print_backup_ssid_discovery(cli_ctx, extract_backup_ssid_discovery(raw))

        await run_with_client(discover)

    asyncio.run(run_cmd())
