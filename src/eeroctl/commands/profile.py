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
from typing import Any, Dict, Literal, Optional

import click
from eero import EeroClient
from rich.panel import Panel
from rich.table import Table

from ..context import EeroCliContext, ensure_cli_context
from ..errors import is_premium_error
from ..exit_codes import ExitCode
from ..options import apply_options, force_option, network_option, output_option
from ..output import OutputFormat
from ..safety import OperationRisk, SafetyError, confirm_or_fail
from ..transformers import extract_data, extract_profiles, normalize_profile
from ..utils import run_with_client


def _find_profile(profiles: list, identifier: str) -> Optional[Dict[str, Any]]:
    """Find a profile by ID or name (case-insensitive for names)."""
    identifier_lower = identifier.lower()

    for p in profiles:
        prof = normalize_profile(p)

        # Exact match for ID
        if prof.get("id") == identifier:
            return prof

        # Case-insensitive match for name
        name = prof.get("name") or ""
        if name.lower() == identifier_lower:
            return prof

    return None


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
@output_option
@network_option
@click.pass_context
def profile_list(ctx: click.Context, output: Optional[str], network_id: Optional[str]) -> None:
    """List all profiles."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def get_profiles(client: EeroClient) -> None:
            with cli_ctx.status("Getting profiles..."):
                raw_response = await client.get_profiles(cli_ctx.network_id)

            profiles = extract_profiles(raw_response)
            normalized = [normalize_profile(p) for p in profiles]

            if not normalized:
                console.print("[yellow]No profiles found[/yellow]")
                return

            if cli_ctx.is_structured_output():
                cli_ctx.render_structured(normalized, "eero.profile.list/v1")
            elif cli_ctx.output_format == OutputFormat.LIST:
                for p in normalized:
                    status = "paused" if p.get("paused") else "active"
                    schedule = "enabled" if p.get("schedule_enabled") else "-"
                    default = "yes" if p.get("default") else "-"
                    premium = "yes" if p.get("premium_enabled") else "-"
                    device_count = p.get("device_count", 0)
                    print(
                        f"{p.get('id') or '':<14}  {p.get('name') or '':<20}  {status:<8}  "
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

                for p in normalized:
                    if p.get("paused"):
                        status = "[red]Paused[/red]"
                    else:
                        status = "[green]Active[/green]"
                    schedule = (
                        "[blue]Enabled[/blue]" if p.get("schedule_enabled") else "[dim]-[/dim]"
                    )
                    default = "[yellow]★[/yellow]" if p.get("default") else "[dim]-[/dim]"
                    premium = "[magenta]✓[/magenta]" if p.get("premium_enabled") else "[dim]-[/dim]"
                    device_count = p.get("device_count", 0)

                    table.add_row(
                        p.get("id") or "",
                        p.get("name") or "",
                        status,
                        schedule,
                        default,
                        premium,
                        str(device_count),
                    )

                console.print(table)

        await run_with_client(get_profiles)

    asyncio.run(run_cmd())


@profile_group.command(name="show")
@click.argument("profile_identifier")
@output_option
@network_option
@click.pass_context
def profile_show(
    ctx: click.Context, profile_identifier: str, output: Optional[str], network_id: Optional[str]
) -> None:
    """Show details of a specific profile.

    \b
    Arguments:
      PROFILE_IDENTIFIER  Profile ID or name
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def get_profile(client: EeroClient) -> None:
            with cli_ctx.status("Finding profile..."):
                raw_response = await client.get_profiles(cli_ctx.network_id)

            profiles = extract_profiles(raw_response)
            target = _find_profile(profiles, profile_identifier)

            if not target or not target.get("id"):
                console.print(f"[red]Profile '{profile_identifier}' not found[/red]")
                console.print("[dim]Try: eero profile list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            with cli_ctx.status("Getting profile details..."):
                raw_detail = await client.get_profile(target["id"], cli_ctx.network_id)

            profile = normalize_profile(extract_data(raw_detail))

            if cli_ctx.is_structured_output():
                cli_ctx.render_structured(profile, "eero.profile.show/v1")
            elif cli_ctx.is_list_output():
                # Simple key-value output for list format
                cli_ctx.renderer.render_text(profile, "eero.profile.show/v1")
            else:
                from ..formatting import print_profile_details

                detail: Literal["brief", "full"] = (
                    "full" if cli_ctx.detail_level == "full" else "brief"
                )
                print_profile_details(profile, detail_level=detail)

        await run_with_client(get_profile)

    asyncio.run(run_cmd())


@profile_group.command(name="pause")
@click.argument("profile_identifier")
@click.option("--duration", "-d", help="Duration (e.g., 30m, 1h)")
@force_option
@network_option
@click.pass_context
def profile_pause(
    ctx: click.Context,
    profile_identifier: str,
    duration: Optional[str],
    force: Optional[bool],
    network_id: Optional[str],
) -> None:
    """Pause internet access for a profile.

    \b
    Arguments:
      PROFILE_IDENTIFIER  Profile ID or name

    \b
    Options:
      --duration, -d  Duration (e.g., 30m, 1h)
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    _set_profile_paused(cli_ctx, profile_identifier, True)


@profile_group.command(name="unpause")
@click.argument("profile_identifier")
@force_option
@network_option
@click.pass_context
def profile_unpause(
    ctx: click.Context, profile_identifier: str, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Resume internet access for a profile.

    \b
    Arguments:
      PROFILE_IDENTIFIER  Profile ID or name
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    _set_profile_paused(cli_ctx, profile_identifier, False)


def _set_profile_paused(cli_ctx: EeroCliContext, profile_identifier: str, paused: bool) -> None:
    """Pause or unpause a profile."""
    console = cli_ctx.console
    action = "pause" if paused else "unpause"

    async def run_cmd() -> None:
        async def toggle_pause(client: EeroClient) -> None:
            # Find profile first
            with cli_ctx.status("Finding profile..."):
                raw_response = await client.get_profiles(cli_ctx.network_id)

            profiles = extract_profiles(raw_response)
            target = _find_profile(profiles, profile_identifier)

            if not target or not target.get("id"):
                console.print(f"[red]Profile '{profile_identifier}' not found[/red]")
                console.print("[dim]Try: eero profile list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            try:
                confirm_or_fail(
                    action=action,
                    target=target.get("name") or profile_identifier,
                    risk=OperationRisk.MEDIUM,
                    force=cli_ctx.force,
                    non_interactive=cli_ctx.non_interactive,
                    dry_run=cli_ctx.dry_run,
                    console=cli_ctx.console,
                )
            except SafetyError as e:
                cli_ctx.renderer.render_error(e.message)
                sys.exit(e.exit_code)

            with cli_ctx.status(f"{action.capitalize()}ing profile..."):
                result = await client.pause_profile(target["id"], paused, cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
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
@click.argument("profile_identifier")
@output_option
@network_option
@click.pass_context
def apps_list(
    ctx: click.Context, profile_identifier: str, output: Optional[str], network_id: Optional[str]
) -> None:
    """List blocked applications for a profile."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_apps(client: EeroClient) -> None:
            # Find profile first
            with cli_ctx.status("Finding profile..."):
                raw_response = await client.get_profiles(cli_ctx.network_id)

            profiles = extract_profiles(raw_response)
            target = _find_profile(profiles, profile_identifier)

            if not target or not target.get("id"):
                console.print(f"[red]Profile '{profile_identifier}' not found[/red]")
                console.print("[dim]Try: eero profile list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            with cli_ctx.status("Getting blocked apps..."):
                try:
                    raw_apps = await client.get_blocked_applications(
                        target["id"], cli_ctx.network_id
                    )
                except Exception as e:
                    if is_premium_error(e):
                        console.print("[yellow]This feature requires Eero Plus[/yellow]")
                        sys.exit(ExitCode.PREMIUM_REQUIRED)
                    raise

            apps = extract_data(raw_apps) if isinstance(raw_apps, dict) else raw_apps
            if isinstance(apps, dict):
                apps = apps.get("applications", [])

            apps_data = {"profile": target.get("name"), "blocked_apps": apps}

            if cli_ctx.is_json_output():
                renderer.render_json(apps_data, "eero.profile.apps.list/v1")
            elif cli_ctx.is_list_output():
                renderer.render_text(apps_data, "eero.profile.apps.list/v1")
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
@click.argument("profile_identifier")
@click.argument("apps", nargs=-1, required=True)
@network_option
@click.pass_context
def apps_block(
    ctx: click.Context, profile_identifier: str, apps: tuple, network_id: Optional[str]
) -> None:
    """Block application(s) for a profile.

    \b
    Arguments:
      PROFILE_IDENTIFIER  Profile ID or name
      APPS                App identifier(s) to block

    \b
    Examples:
      eero profile apps block "Kids" tiktok facebook
    """
    cli_ctx = apply_options(ctx, network_id=network_id)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def block_apps(client: EeroClient) -> None:
            # Find profile first
            with cli_ctx.status("Finding profile..."):
                raw_response = await client.get_profiles(cli_ctx.network_id)

            profiles = extract_profiles(raw_response)
            target = _find_profile(profiles, profile_identifier)

            if not target or not target.get("id"):
                console.print(f"[red]Profile '{profile_identifier}' not found[/red]")
                console.print("[dim]Try: eero profile list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            for app in apps:
                with cli_ctx.status(f"Blocking {app}..."):
                    try:
                        # TODO: add_blocked_application method not yet implemented in eero-api
                        result = await client.add_blocked_application(  # type: ignore[attr-defined]
                            target["id"], app, cli_ctx.network_id
                        )
                        meta = result.get("meta", {}) if isinstance(result, dict) else {}
                        if meta.get("code") == 200 or result:
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
@click.argument("profile_identifier")
@click.argument("apps", nargs=-1, required=True)
@network_option
@click.pass_context
def apps_unblock(
    ctx: click.Context, profile_identifier: str, apps: tuple, network_id: Optional[str]
) -> None:
    """Unblock application(s) for a profile.

    \b
    Arguments:
      PROFILE_IDENTIFIER  Profile ID or name
      APPS                App identifier(s) to unblock
    """
    cli_ctx = apply_options(ctx, network_id=network_id)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def unblock_apps(client: EeroClient) -> None:
            # Find profile first
            with cli_ctx.status("Finding profile..."):
                raw_response = await client.get_profiles(cli_ctx.network_id)

            profiles = extract_profiles(raw_response)
            target = _find_profile(profiles, profile_identifier)

            if not target or not target.get("id"):
                console.print(f"[red]Profile '{profile_identifier}' not found[/red]")
                console.print("[dim]Try: eero profile list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            for app in apps:
                with cli_ctx.status(f"Unblocking {app}..."):
                    try:
                        # TODO: remove_blocked_application method not yet implemented in eero-api
                        result = await client.remove_blocked_application(  # type: ignore[attr-defined]
                            target["id"], app, cli_ctx.network_id
                        )
                        meta = result.get("meta", {}) if isinstance(result, dict) else {}
                        if meta.get("code") == 200 or result:
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
@click.argument("profile_identifier")
@output_option
@network_option
@click.pass_context
def schedule_show(
    ctx: click.Context, profile_identifier: str, output: Optional[str], network_id: Optional[str]
) -> None:
    """Show schedule for a profile."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_schedule(client: EeroClient) -> None:
            # Find profile first
            with cli_ctx.status("Finding profile..."):
                raw_response = await client.get_profiles(cli_ctx.network_id)

            profiles = extract_profiles(raw_response)
            target = _find_profile(profiles, profile_identifier)

            if not target or not target.get("id"):
                console.print(f"[red]Profile '{profile_identifier}' not found[/red]")
                console.print("[dim]Try: eero profile list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            with cli_ctx.status("Getting schedule..."):
                raw_schedule = await client.get_profile_schedule(target["id"], cli_ctx.network_id)

            schedule_data = extract_data(raw_schedule) if isinstance(raw_schedule, dict) else {}

            if cli_ctx.is_json_output():
                renderer.render_json(schedule_data, "eero.profile.schedule.show/v1")
            elif cli_ctx.is_list_output():
                renderer.render_text(schedule_data, "eero.profile.schedule.show/v1")
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
@click.argument("profile_identifier")
@click.option("--start", required=True, help="Start time (HH:MM)")
@click.option("--end", required=True, help="End time (HH:MM)")
@click.option("--days", help="Days (comma-separated, e.g., mon,tue,wed)")
@force_option
@network_option
@click.pass_context
def schedule_set(
    ctx: click.Context,
    profile_identifier: str,
    start: str,
    end: str,
    days: Optional[str],
    force: Optional[bool],
    network_id: Optional[str],
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
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.console

    days_list = days.split(",") if days else None

    async def run_cmd() -> None:
        async def set_schedule(client: EeroClient) -> None:
            # Find profile first
            with cli_ctx.status("Finding profile..."):
                raw_response = await client.get_profiles(cli_ctx.network_id)

            profiles = extract_profiles(raw_response)
            target = _find_profile(profiles, profile_identifier)

            if not target or not target.get("id"):
                console.print(f"[red]Profile '{profile_identifier}' not found[/red]")
                console.print("[dim]Try: eero profile list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            try:
                confirm_or_fail(
                    action="set bedtime schedule",
                    target=f"{target.get('name') or profile_identifier} ({start} - {end})",
                    risk=OperationRisk.MEDIUM,
                    force=cli_ctx.force,
                    non_interactive=cli_ctx.non_interactive,
                    dry_run=cli_ctx.dry_run,
                    console=cli_ctx.console,
                )
            except SafetyError as e:
                cli_ctx.renderer.render_error(e.message)
                sys.exit(e.exit_code)

            with cli_ctx.status("Setting schedule..."):
                result = await client.enable_bedtime(
                    target["id"], start, end, days_list, cli_ctx.network_id
                )

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print(f"[bold green]Schedule set: {start} - {end}[/bold green]")
            else:
                console.print("[red]Failed to set schedule[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_schedule)

    asyncio.run(run_cmd())


@schedule_group.command(name="clear")
@click.argument("profile_identifier")
@force_option
@network_option
@click.pass_context
def schedule_clear(
    ctx: click.Context, profile_identifier: str, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Clear all schedules for a profile."""
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def clear_schedule(client: EeroClient) -> None:
            # Find profile first
            with cli_ctx.status("Finding profile..."):
                raw_response = await client.get_profiles(cli_ctx.network_id)

            profiles = extract_profiles(raw_response)
            target = _find_profile(profiles, profile_identifier)

            if not target or not target.get("id"):
                console.print(f"[red]Profile '{profile_identifier}' not found[/red]")
                console.print("[dim]Try: eero profile list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            try:
                confirm_or_fail(
                    action="clear schedule",
                    target=target.get("name") or profile_identifier,
                    risk=OperationRisk.MEDIUM,
                    force=cli_ctx.force,
                    non_interactive=cli_ctx.non_interactive,
                    dry_run=cli_ctx.dry_run,
                    console=cli_ctx.console,
                )
            except SafetyError as e:
                cli_ctx.renderer.render_error(e.message)
                sys.exit(e.exit_code)

            with cli_ctx.status("Clearing schedule..."):
                result = await client.clear_profile_schedule(target["id"], cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print("[bold green]Schedule cleared[/bold green]")
            else:
                console.print("[red]Failed to clear schedule[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(clear_schedule)

    asyncio.run(run_cmd())
