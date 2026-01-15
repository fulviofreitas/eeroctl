"""Profile commands for the Eero CLI.

Commands:
- eero profile list: List all profiles
- eero profile show: Show profile details
- eero profile pause: Pause a profile
- eero profile unpause: Unpause a profile
- eero profile apps: App blocking management
- eero profile schedule: Schedule management
"""

import asyncio
import sys
from typing import Literal, Optional

import click
from eero import EeroClient
from rich.panel import Panel
from rich.table import Table

from ..context import EeroCliContext, ensure_cli_context, get_cli_context
from ..errors import is_premium_error
from ..exit_codes import ExitCode
from ..output import OutputFormat
from ..safety import OperationRisk, SafetyError, confirm_or_fail
from ..utils import run_with_client


@click.group(name="profile")
@click.pass_context
def profile_group(ctx: click.Context) -> None:
    """Manage profiles and parental controls.

    \b
    Commands:
      list     - List all profiles
      show     - Show profile details
      pause    - Pause internet access
      unpause  - Resume internet access
      apps     - Blocked apps management
      schedule - Schedule management

    \b
    Examples:
      eero profile list
      eero profile show "Kids"
      eero profile pause "Kids" --duration 30m
      eero profile apps block "Kids" tiktok
    """
    ensure_cli_context(ctx)


@profile_group.command(name="list")
@click.pass_context
def profile_list(ctx: click.Context) -> None:
    """List all profiles."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def get_profiles(client: EeroClient) -> None:
            with cli_ctx.status("Getting profiles..."):
                profiles = await client.get_profiles(cli_ctx.network_id)

            if not profiles:
                console.print("[yellow]No profiles found[/yellow]")
                return

            if cli_ctx.is_structured_output():
                data = [p.model_dump(mode="json") for p in profiles]
                cli_ctx.render_structured(data, "eero.profile.list/v1")
            elif cli_ctx.output_format == OutputFormat.LIST:
                for p in profiles:
                    status = "paused" if p.paused else "active"
                    schedule = "enabled" if p.schedule_enabled else "-"
                    default = "yes" if p.default else "-"
                    premium = "yes" if p.premium_enabled else "-"
                    # Use device_count if available, otherwise count devices list
                    device_count = (
                        p.device_count
                        if p.device_count is not None
                        else len(p.devices) if p.devices else 0
                    )
                    # Use print() with fixed-width columns for alignment
                    print(
                        f"{p.id or '':<14}  {p.name:<20}  {status:<8}  "
                        f"{schedule:<10}  {default:<8}  {premium:<8}  {device_count}"
                    )
            else:
                table = Table(title="Profiles")
                table.add_column("ID", style="dim")
                table.add_column("Name", style="cyan")
                table.add_column("Status")
                table.add_column("Schedule")
                table.add_column("Default")
                table.add_column("Premium")
                table.add_column("Devices", justify="right")

                for p in profiles:
                    # Status: Paused or Active
                    if p.paused:
                        status = "[red]Paused[/red]"
                    else:
                        status = "[green]Active[/green]"

                    # Schedule: Enabled or -
                    schedule = "[blue]Enabled[/blue]" if p.schedule_enabled else "[dim]-[/dim]"

                    # Default profile indicator
                    default = "[yellow]★[/yellow]" if p.default else "[dim]-[/dim]"

                    # Premium features indicator
                    premium = "[magenta]✓[/magenta]" if p.premium_enabled else "[dim]-[/dim]"

                    # Device count - use device_count if available, otherwise count devices list
                    device_count = (
                        p.device_count
                        if p.device_count is not None
                        else len(p.devices) if p.devices else 0
                    )

                    table.add_row(p.id or "", p.name, status, schedule, default, premium, str(device_count))

                console.print(table)

        await run_with_client(get_profiles)

    asyncio.run(run_cmd())


@profile_group.command(name="show")
@click.argument("profile_id")
@click.pass_context
def profile_show(ctx: click.Context, profile_id: str) -> None:
    """Show details of a specific profile.

    \b
    Arguments:
      PROFILE_ID  Profile ID or name
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def get_profile(client: EeroClient) -> None:
            with cli_ctx.status("Getting profiles..."):
                profiles = await client.get_profiles(cli_ctx.network_id)

            target = None
            for p in profiles:
                if p.id == profile_id or p.name == profile_id:
                    target = p
                    break

            if not target or not target.id:
                console.print(f"[red]Profile '{profile_id}' not found[/red]")
                sys.exit(ExitCode.NOT_FOUND)

            with cli_ctx.status("Getting profile details..."):
                profile = await client.get_profile(target.id, cli_ctx.network_id)

            if cli_ctx.is_structured_output():
                cli_ctx.render_structured(profile.model_dump(mode="json"), "eero.profile.show/v1")
            else:
                from ..formatting import print_profile_details

                detail: Literal["brief", "full"] = (
                    "full" if cli_ctx.detail_level == "full" else "brief"
                )
                print_profile_details(profile, detail_level=detail)

        await run_with_client(get_profile)

    asyncio.run(run_cmd())


@profile_group.command(name="pause")
@click.argument("profile_id")
@click.option("--duration", "-d", help="Duration (e.g., 30m, 1h)")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def profile_pause(
    ctx: click.Context, profile_id: str, duration: Optional[str], force: bool
) -> None:
    """Pause internet access for a profile.

    \b
    Arguments:
      PROFILE_ID  Profile ID or name

    \b
    Options:
      --duration, -d  Duration (e.g., 30m, 1h)
    """
    cli_ctx = get_cli_context(ctx)
    _set_profile_paused(cli_ctx, profile_id, True, force)


@profile_group.command(name="unpause")
@click.argument("profile_id")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def profile_unpause(ctx: click.Context, profile_id: str, force: bool) -> None:
    """Resume internet access for a profile.

    \b
    Arguments:
      PROFILE_ID  Profile ID or name
    """
    cli_ctx = get_cli_context(ctx)
    _set_profile_paused(cli_ctx, profile_id, False, force)


def _set_profile_paused(
    cli_ctx: EeroCliContext, profile_id: str, paused: bool, force: bool
) -> None:
    """Pause or unpause a profile."""
    console = cli_ctx.console
    action = "pause" if paused else "unpause"

    async def run_cmd() -> None:
        async def toggle_pause(client: EeroClient) -> None:
            # Find profile first
            with cli_ctx.status("Finding profile..."):
                profiles = await client.get_profiles(cli_ctx.network_id)

            target = None
            for p in profiles:
                if p.id == profile_id or p.name == profile_id:
                    target = p
                    break

            if not target or not target.id:
                console.print(f"[red]Profile '{profile_id}' not found[/red]")
                sys.exit(ExitCode.NOT_FOUND)

            try:
                confirm_or_fail(
                    action=action,
                    target=target.name,
                    risk=OperationRisk.MEDIUM,
                    force=force or cli_ctx.force,
                    non_interactive=cli_ctx.non_interactive,
                    dry_run=cli_ctx.dry_run,
                    console=cli_ctx.console,
                )
            except SafetyError as e:
                cli_ctx.renderer.render_error(e.message)
                sys.exit(e.exit_code)

            with cli_ctx.status(f"{action.capitalize()}ing profile..."):
                result = await client.pause_profile(target.id, paused, cli_ctx.network_id)

            if result:
                console.print(f"[bold green]Profile {action}d[/bold green]")
            else:
                console.print(f"[red]Failed to {action} profile[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(toggle_pause)

    asyncio.run(run_cmd())


# ==================== Apps Subcommand Group ====================


@profile_group.group(name="apps")
@click.pass_context
def apps_group(ctx: click.Context) -> None:
    """Manage blocked applications (Eero Plus).

    \b
    Commands:
      list    - List blocked apps
      block   - Block app(s)
      unblock - Unblock app(s)
    """
    pass


@apps_group.command(name="list")
@click.argument("profile_id")
@click.pass_context
def apps_list(ctx: click.Context, profile_id: str) -> None:
    """List blocked applications for a profile."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_apps(client: EeroClient) -> None:
            # Find profile first
            with cli_ctx.status("Finding profile..."):
                profiles = await client.get_profiles(cli_ctx.network_id)

            target = None
            for p in profiles:
                if p.id == profile_id or p.name == profile_id:
                    target = p
                    break

            if not target or not target.id:
                console.print(f"[red]Profile '{profile_id}' not found[/red]")
                sys.exit(ExitCode.NOT_FOUND)

            with cli_ctx.status("Getting blocked apps..."):
                try:
                    apps = await client.get_blocked_applications(target.id, cli_ctx.network_id)
                except Exception as e:
                    if is_premium_error(e):
                        console.print("[yellow]This feature requires Eero Plus[/yellow]")
                        sys.exit(ExitCode.PREMIUM_REQUIRED)
                    raise

            if cli_ctx.is_json_output():
                renderer.render_json(
                    {"profile": target.name, "blocked_apps": apps}, "eero.profile.apps.list/v1"
                )
            else:
                if not apps:
                    console.print("[dim]No blocked applications[/dim]")
                else:
                    console.print(f"[bold]Blocked Applications ({len(apps)}):[/bold]")
                    for app in apps:
                        console.print(f"  • {app}")

        await run_with_client(get_apps)

    asyncio.run(run_cmd())


@apps_group.command(name="block")
@click.argument("profile_id")
@click.argument("apps", nargs=-1, required=True)
@click.pass_context
def apps_block(ctx: click.Context, profile_id: str, apps: tuple) -> None:
    """Block application(s) for a profile.

    \b
    Arguments:
      PROFILE_ID  Profile ID or name
      APPS        App identifier(s) to block

    \b
    Examples:
      eero profile apps block "Kids" tiktok facebook
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def block_apps(client: EeroClient) -> None:
            # Find profile first
            with cli_ctx.status("Finding profile..."):
                profiles = await client.get_profiles(cli_ctx.network_id)

            target = None
            for p in profiles:
                if p.id == profile_id or p.name == profile_id:
                    target = p
                    break

            if not target or not target.id:
                console.print(f"[red]Profile '{profile_id}' not found[/red]")
                sys.exit(ExitCode.NOT_FOUND)

            for app in apps:
                with cli_ctx.status(f"Blocking {app}..."):
                    try:
                        result = await client.add_blocked_application(
                            target.id, app, cli_ctx.network_id
                        )
                        if result:
                            console.print(f"[green]✓[/green] {app} blocked")
                        else:
                            console.print(f"[red]✗[/red] Failed to block {app}")
                    except Exception as e:
                        if is_premium_error(e):
                            console.print("[yellow]This feature requires Eero Plus[/yellow]")
                            sys.exit(ExitCode.PREMIUM_REQUIRED)
                        console.print(f"[red]✗[/red] Error blocking {app}: {e}")

        await run_with_client(block_apps)

    asyncio.run(run_cmd())


@apps_group.command(name="unblock")
@click.argument("profile_id")
@click.argument("apps", nargs=-1, required=True)
@click.pass_context
def apps_unblock(ctx: click.Context, profile_id: str, apps: tuple) -> None:
    """Unblock application(s) for a profile.

    \b
    Arguments:
      PROFILE_ID  Profile ID or name
      APPS        App identifier(s) to unblock
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def unblock_apps(client: EeroClient) -> None:
            # Find profile first
            with cli_ctx.status("Finding profile..."):
                profiles = await client.get_profiles(cli_ctx.network_id)

            target = None
            for p in profiles:
                if p.id == profile_id or p.name == profile_id:
                    target = p
                    break

            if not target or not target.id:
                console.print(f"[red]Profile '{profile_id}' not found[/red]")
                sys.exit(ExitCode.NOT_FOUND)

            for app in apps:
                with cli_ctx.status(f"Unblocking {app}..."):
                    try:
                        result = await client.remove_blocked_application(
                            target.id, app, cli_ctx.network_id
                        )
                        if result:
                            console.print(f"[green]✓[/green] {app} unblocked")
                        else:
                            console.print(f"[red]✗[/red] Failed to unblock {app}")
                    except Exception as e:
                        if is_premium_error(e):
                            console.print("[yellow]This feature requires Eero Plus[/yellow]")
                            sys.exit(ExitCode.PREMIUM_REQUIRED)
                        console.print(f"[red]✗[/red] Error unblocking {app}: {e}")

        await run_with_client(unblock_apps)

    asyncio.run(run_cmd())


# ==================== Schedule Subcommand Group ====================


@profile_group.group(name="schedule")
@click.pass_context
def schedule_group(ctx: click.Context) -> None:
    """Manage internet access schedule.

    \b
    Commands:
      show - Show schedule
      set  - Set bedtime schedule
      clear - Clear all schedules
    """
    pass


@schedule_group.command(name="show")
@click.argument("profile_id")
@click.pass_context
def schedule_show(ctx: click.Context, profile_id: str) -> None:
    """Show schedule for a profile."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_schedule(client: EeroClient) -> None:
            # Find profile first
            with cli_ctx.status("Finding profile..."):
                profiles = await client.get_profiles(cli_ctx.network_id)

            target = None
            for p in profiles:
                if p.id == profile_id or p.name == profile_id:
                    target = p
                    break

            if not target or not target.id:
                console.print(f"[red]Profile '{profile_id}' not found[/red]")
                sys.exit(ExitCode.NOT_FOUND)

            with cli_ctx.status("Getting schedule..."):
                schedule_data = await client.get_profile_schedule(target.id, cli_ctx.network_id)

            if cli_ctx.is_json_output():
                renderer.render_json(schedule_data, "eero.profile.schedule.show/v1")
            else:
                enabled = schedule_data.get("enabled", False)
                time_blocks = schedule_data.get("time_blocks", [])

                content = (
                    f"[bold]Enabled:[/bold] {'[green]Yes[/green]' if enabled else '[dim]No[/dim]'}"
                )
                if time_blocks:
                    content += f"\n[bold]Time Blocks:[/bold] {len(time_blocks)}"
                    for i, block in enumerate(time_blocks, 1):
                        days = ", ".join(block.get("days", []))
                        start = block.get("start", "?")
                        end = block.get("end", "?")
                        content += f"\n  {i}. {days}: {start} - {end}"

                console.print(Panel(content, title="Schedule", border_style="blue"))

        await run_with_client(get_schedule)

    asyncio.run(run_cmd())


@schedule_group.command(name="set")
@click.argument("profile_id")
@click.option("--start", required=True, help="Start time (HH:MM)")
@click.option("--end", required=True, help="End time (HH:MM)")
@click.option("--days", help="Days (comma-separated, e.g., mon,tue,wed)")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def schedule_set(
    ctx: click.Context, profile_id: str, start: str, end: str, days: Optional[str], force: bool
) -> None:
    """Set bedtime schedule for a profile.

    \b
    Options:
      --start TEXT  Start time (HH:MM, required)
      --end TEXT    End time (HH:MM, required)
      --days TEXT   Days (comma-separated, defaults to all)

    \b
    Examples:
      eero profile schedule set "Kids" --start 21:00 --end 07:00
      eero profile schedule set "Kids" --start 22:00 --end 06:00 --days mon,tue,wed,thu,fri
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    days_list = days.split(",") if days else None

    async def run_cmd() -> None:
        async def set_schedule(client: EeroClient) -> None:
            # Find profile first
            with cli_ctx.status("Finding profile..."):
                profiles = await client.get_profiles(cli_ctx.network_id)

            target = None
            for p in profiles:
                if p.id == profile_id or p.name == profile_id:
                    target = p
                    break

            if not target or not target.id:
                console.print(f"[red]Profile '{profile_id}' not found[/red]")
                sys.exit(ExitCode.NOT_FOUND)

            try:
                confirm_or_fail(
                    action="set bedtime schedule",
                    target=f"{target.name} ({start} - {end})",
                    risk=OperationRisk.MEDIUM,
                    force=force or cli_ctx.force,
                    non_interactive=cli_ctx.non_interactive,
                    dry_run=cli_ctx.dry_run,
                    console=cli_ctx.console,
                )
            except SafetyError as e:
                cli_ctx.renderer.render_error(e.message)
                sys.exit(e.exit_code)

            with cli_ctx.status("Setting schedule..."):
                result = await client.enable_bedtime(
                    target.id, start, end, days_list, cli_ctx.network_id
                )

            if result:
                console.print(f"[bold green]Schedule set: {start} - {end}[/bold green]")
            else:
                console.print("[red]Failed to set schedule[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_schedule)

    asyncio.run(run_cmd())


@schedule_group.command(name="clear")
@click.argument("profile_id")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def schedule_clear(ctx: click.Context, profile_id: str, force: bool) -> None:
    """Clear all schedules for a profile."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def clear_schedule(client: EeroClient) -> None:
            # Find profile first
            with cli_ctx.status("Finding profile..."):
                profiles = await client.get_profiles(cli_ctx.network_id)

            target = None
            for p in profiles:
                if p.id == profile_id or p.name == profile_id:
                    target = p
                    break

            if not target or not target.id:
                console.print(f"[red]Profile '{profile_id}' not found[/red]")
                sys.exit(ExitCode.NOT_FOUND)

            try:
                confirm_or_fail(
                    action="clear schedule",
                    target=target.name,
                    risk=OperationRisk.MEDIUM,
                    force=force or cli_ctx.force,
                    non_interactive=cli_ctx.non_interactive,
                    dry_run=cli_ctx.dry_run,
                    console=cli_ctx.console,
                )
            except SafetyError as e:
                cli_ctx.renderer.render_error(e.message)
                sys.exit(e.exit_code)

            with cli_ctx.status("Clearing schedule..."):
                result = await client.clear_profile_schedule(target.id, cli_ctx.network_id)

            if result:
                console.print("[bold green]Schedule cleared[/bold green]")
            else:
                console.print("[red]Failed to clear schedule[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(clear_schedule)

    asyncio.run(run_cmd())
