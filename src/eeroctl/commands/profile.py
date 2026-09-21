"""Profile commands for the Eero CLI.

Commands:
- eero profile list: List all profiles
- eero profile show: Show profile details
- eero profile create: Create a new profile
- eero profile rename: Rename a profile
- eero profile delete: Delete a profile
- eero profile pause: Pause a profile
- eero profile unpause: Unpause a profile
- eero profile apps: App blocking management
- eero profile schedule: Schedule management
"""

import asyncio
import sys
from typing import Any, Dict, List, Literal, Optional, Set, Union

import click
from eero import EeroClient
from eero.exceptions import EeroException, EeroNotFoundException, EeroPremiumRequiredException
from rich.panel import Panel
from rich.table import Table

from ..context import EeroCliContext, ensure_cli_context
from ..exit_codes import ExitCode
from ..options import apply_options, force_option, network_option, output_option
from ..output import OutputFormat
from ..safety import SafetyContext, SafetyError, get_write_spec, require_write_confirmation
from ..transformers import extract_data, extract_id_from_url, extract_profiles, normalize_profile
from ..utils import looks_like_sdk_reference, run_with_client, write_if_changed


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


# eero.api.schedule.ALL_DAYS (schedule.py:34-42) -- default days scope
# `enable_bedtime` uses server-side when `days` is omitted. Mirrored here so
# `schedule set`'s read-first comparison can tell "no --days given" from "an
# existing Bedtime schedule that already covers every day" apart.
_SCHEDULE_ALL_DAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


_UNRECOGNISED_APPLICATIONS_SHAPE = (
    "Unrecognised application list shape from the API; refusing to rewrite the blocked list"
)


def _extract_dns_policy_applications(raw: Any) -> List[Union[str, Dict[str, Any]]]:
    """Extract the ``applications`` list from a `get_dns_policy_applications` envelope.

    Shape (`eero-api` 8.0.1, `DnsPoliciesAPI.get_profile_applications`):
    ``{"meta": {...}, "data": {"applications": [...], "categories_list": [...]}}``.

    Fails closed: `set_profile_blocked_applications` REPLACES the full blocked
    list, so guessing wrong here can silently unblock (or re-block) every
    other application. Raises `EeroException` -- rather than defaulting to an
    empty list -- when `data.applications` is missing or not a list, so a
    caller never proceeds to a write with a guessed-empty starting point.
    """
    data = extract_data(raw) if isinstance(raw, dict) else raw
    if not isinstance(data, dict) or "applications" not in data:
        raise EeroException(_UNRECOGNISED_APPLICATIONS_SHAPE)
    applications = data["applications"]
    if not isinstance(applications, list):
        raise EeroException(_UNRECOGNISED_APPLICATIONS_SHAPE)
    return applications


def _blocked_app_ids(applications: List[Union[str, Dict[str, Any]]]) -> Set[str]:
    """Return the set of currently-blocked application identifiers.

    Each entry is either a bare app id/name (string, treated as already
    blocked -- mirrors the v7 `blocked_apps` list shape) or a dict carrying
    an `"id"`/`"name"` and a boolean `"blocked"` flag.

    Fails closed: raises `EeroException` if any entry matches neither shape,
    or if the list contains dict entries but none of them carry a `"blocked"`
    key at all -- an all-dict, no-`blocked`-key list would otherwise silently
    look like "nothing is blocked" and a block/unblock write would replace
    the real list with a wrong guess.
    """
    blocked: Set[str] = set()
    dict_entries = 0
    entries_with_blocked_key = 0
    for entry in applications:
        if isinstance(entry, str):
            blocked.add(entry)
        elif isinstance(entry, dict) and (
            entry.get("id") is not None or entry.get("name") is not None
        ):
            dict_entries += 1
            if isinstance(entry.get("blocked"), bool):
                entries_with_blocked_key += 1
                if entry["blocked"]:
                    app_id = entry.get("id") or entry.get("name")
                    blocked.add(str(app_id))
        else:
            raise EeroException(_UNRECOGNISED_APPLICATIONS_SHAPE)

    if dict_entries and not entries_with_blocked_key:
        raise EeroException(_UNRECOGNISED_APPLICATIONS_SHAPE)

    return blocked


@click.group(name="profile")
@click.pass_context
def profile_group(ctx: click.Context) -> None:
    """Manage profiles and parental controls.

    \b
    Commands:
      list     - List all profiles
      show     - Show profile details
      create   - Create a new profile
      rename   - Rename a profile
      delete   - Delete a profile
      pause    - Pause internet access
      unpause  - Resume internet access
      apps     - Blocked apps management
      schedule - Schedule management

    \b
    Examples:
      eero profile list
      eero profile show "Kids"
      eero profile create Kids
      eero profile rename Kids Schoolkids
      eero profile delete Kids --force
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
            # A path/URL/hostile-shaped identifier goes straight to the
            # id-validated SDK method, verbatim -- never pre-validated here
            # (migration plan §2.5 decision 2). `EeroValidationException` is
            # deliberately not caught: it propagates to `run_with_client` and
            # maps to exit 2. Only a well-shaped-but-absent id/path/URL
            # (`EeroNotFoundException`, or an empty envelope) falls through
            # to "not found"; plain names skip straight to the existing
            # list-and-match resolution below.
            profile: Optional[Dict[str, Any]] = None
            if looks_like_sdk_reference(profile_identifier):
                with cli_ctx.status("Getting profile details..."):
                    try:
                        raw_detail = await client.get_profile(
                            profile_identifier, cli_ctx.network_id
                        )
                    except EeroNotFoundException:
                        raw_detail = None

                data = extract_data(raw_detail) if isinstance(raw_detail, dict) else None
                if isinstance(data, dict) and data:
                    profile = normalize_profile(data)

                if profile is None:
                    console.print(f"[red]Profile '{profile_identifier}' not found[/red]")
                    console.print("[dim]Try: eero profile list[/dim]")
                    sys.exit(ExitCode.NOT_FOUND)
            else:
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
                # Curated key-value output matching table fields
                from ..formatting.profile import get_profile_list_data

                list_data = get_profile_list_data(profile)
                for key, value in list_data.items():
                    print(f"{key}: {value if value is not None else '-'}")
            else:
                from ..formatting import print_profile_details

                detail: Literal["brief", "full"] = (
                    "full" if cli_ctx.detail_level == "full" else "brief"
                )
                print_profile_details(profile, detail_level=detail)

        await run_with_client(get_profile)

    asyncio.run(run_cmd())


@profile_group.command(name="create")
@click.argument("name")
@output_option
@network_option
@click.pass_context
def profile_create(
    ctx: click.Context, name: str, output: Optional[str], network_id: Optional[str]
) -> None:
    """Create a new profile.

    \b
    Arguments:
      NAME  Name for the new profile
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    console = cli_ctx.console
    spec = get_write_spec("profile create")
    cli_ctx.active_write_spec = spec

    try:
        require_write_confirmation(
            spec,
            target=name,
            ctx=SafetyContext(
                force=cli_ctx.force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
            console=cli_ctx.err_console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def create_profile(client: EeroClient) -> None:
            with cli_ctx.status("Creating profile..."):
                result = await client.create_profile(name, network_id=cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200:
                profile = normalize_profile(extract_data(result))

                if cli_ctx.is_structured_output():
                    cli_ctx.render_structured(profile, "eero.profile.create/v1")
                elif cli_ctx.is_list_output():
                    from ..formatting.profile import get_profile_list_data

                    list_data = get_profile_list_data(profile)
                    for key, value in list_data.items():
                        print(f"{key}: {value if value is not None else '-'}")
                else:
                    console.print(
                        f"[bold green]Profile created:[/bold green] "
                        f"{profile.get('name') or name} ({profile.get('id') or ''})"
                    )
            else:
                console.print("[red]Failed to create profile[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(create_profile)

    asyncio.run(run_cmd())


@profile_group.command(name="rename")
@click.argument("profile_identifier")
@click.argument("new_name")
@force_option
@network_option
@click.pass_context
def profile_rename(
    ctx: click.Context,
    profile_identifier: str,
    new_name: str,
    force: Optional[bool],
    network_id: Optional[str],
) -> None:
    """Rename a profile.

    \b
    Arguments:
      PROFILE_IDENTIFIER  Profile ID or name
      NEW_NAME            New name for the profile
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def rename_profile(client: EeroClient) -> None:
            with cli_ctx.status("Finding profile..."):
                raw_response = await client.get_profiles(cli_ctx.network_id)

            profiles = extract_profiles(raw_response)
            target = _find_profile(profiles, profile_identifier)

            if not target or not target.get("id"):
                console.print(f"[red]Profile '{profile_identifier}' not found[/red]")
                console.print("[dim]Try: eero profile list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            spec = get_write_spec("profile rename")
            cli_ctx.active_write_spec = spec
            try:
                require_write_confirmation(
                    spec,
                    target=f"{target.get('name') or profile_identifier} → {new_name}",
                    ctx=SafetyContext(
                        force=cli_ctx.force,
                        non_interactive=cli_ctx.non_interactive,
                        dry_run=cli_ctx.dry_run,
                    ),
                    console=cli_ctx.err_console,
                )
            except SafetyError as e:
                cli_ctx.renderer.render_error(e.message)
                sys.exit(e.exit_code)

            with cli_ctx.status("Renaming profile..."):
                result = await client.rename_profile(target["id"], new_name, cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print(f"[bold green]Profile renamed to '{new_name}'[/bold green]")
            else:
                console.print("[red]Failed to rename profile[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(rename_profile)

    asyncio.run(run_cmd())


@profile_group.command(name="delete")
@click.argument("profile_identifier")
@force_option
@network_option
@click.pass_context
def profile_delete(
    ctx: click.Context,
    profile_identifier: str,
    force: Optional[bool],
    network_id: Optional[str],
) -> None:
    """Delete a profile.

    \b
    Arguments:
      PROFILE_IDENTIFIER  Profile ID or name
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def delete_profile(client: EeroClient) -> None:
            with cli_ctx.status("Finding profile..."):
                raw_response = await client.get_profiles(cli_ctx.network_id)

            profiles = extract_profiles(raw_response)
            target = _find_profile(profiles, profile_identifier)

            if not target or not target.get("id"):
                console.print(f"[red]Profile '{profile_identifier}' not found[/red]")
                console.print("[dim]Try: eero profile list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            spec = get_write_spec("profile delete")
            cli_ctx.active_write_spec = spec
            try:
                require_write_confirmation(
                    spec,
                    target=target.get("name") or profile_identifier,
                    ctx=SafetyContext(
                        force=cli_ctx.force,
                        non_interactive=cli_ctx.non_interactive,
                        dry_run=cli_ctx.dry_run,
                    ),
                    console=cli_ctx.err_console,
                )
            except SafetyError as e:
                cli_ctx.renderer.render_error(e.message)
                sys.exit(e.exit_code)

            with cli_ctx.status("Deleting profile..."):
                result = await client.delete_profile(target["id"], cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print("[bold green]Profile deleted[/bold green]")
            else:
                console.print("[red]Failed to delete profile[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(delete_profile)

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
    spec = get_write_spec(f"profile {action}")
    cli_ctx.active_write_spec = spec

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
                require_write_confirmation(
                    spec,
                    target=target.get("name") or profile_identifier,
                    ctx=SafetyContext(
                        force=cli_ctx.force,
                        non_interactive=cli_ctx.non_interactive,
                        dry_run=cli_ctx.dry_run,
                    ),
                    console=cli_ctx.err_console,
                )
            except SafetyError as e:
                cli_ctx.renderer.render_error(e.message)
                sys.exit(e.exit_code)

            # Already fetched above (target["paused"]), so no extra read
            # round-trip is needed for the skip-unchanged check.
            async def read() -> bool:
                return bool(target.get("paused", not paused))

            async def write() -> Any:
                with cli_ctx.status(f"{action.capitalize()}ing profile..."):
                    return await client.pause_profile(target["id"], paused, cli_ctx.network_id)

            await write_if_changed(
                read,
                paused,
                write,
                force=cli_ctx.force,
                console=cli_ctx.err_console,
                read_command=spec.read_command,
            )

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
                    raw_apps = await client.get_dns_policy_applications(
                        target["id"], cli_ctx.network_id
                    )
                except EeroException as e:
                    if isinstance(e, EeroPremiumRequiredException):
                        console.print("[yellow]This feature requires Eero Plus[/yellow]")
                        sys.exit(ExitCode.PREMIUM_REQUIRED)
                    raise

            applications = _extract_dns_policy_applications(raw_apps)
            apps = sorted(_blocked_app_ids(applications))

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
@force_option
@network_option
@click.pass_context
def apps_block(
    ctx: click.Context,
    profile_identifier: str,
    apps: tuple,
    force: Optional[bool],
    network_id: Optional[str],
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
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.console
    spec = get_write_spec("profile apps block")
    cli_ctx.active_write_spec = spec

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

            try:
                require_write_confirmation(
                    spec,
                    target=f"{target.get('name') or profile_identifier}: {', '.join(apps)}",
                    ctx=SafetyContext(
                        force=cli_ctx.force,
                        non_interactive=cli_ctx.non_interactive,
                        dry_run=cli_ctx.dry_run,
                    ),
                    console=cli_ctx.err_console,
                )
            except SafetyError as e:
                cli_ctx.renderer.render_error(e.message)
                sys.exit(e.exit_code)

            with cli_ctx.status("Getting current blocked apps..."):
                try:
                    raw_apps = await client.get_dns_policy_applications(
                        target["id"], cli_ctx.network_id
                    )
                except EeroException as e:
                    if isinstance(e, EeroPremiumRequiredException):
                        console.print("[yellow]This feature requires Eero Plus[/yellow]")
                        sys.exit(ExitCode.PREMIUM_REQUIRED)
                    raise

            applications = _extract_dns_policy_applications(raw_apps)
            new_blocked = _blocked_app_ids(applications) | set(apps)

            # `set_profile_blocked_applications` REPLACES the full list -- show
            # the user exactly what will be sent before issuing the write.
            cli_ctx.err_console.print(
                f"Blocked applications after this change: {sorted(new_blocked)}"
            )

            with cli_ctx.status("Blocking apps..."):
                try:
                    result = await client.set_profile_blocked_applications(
                        target["id"], sorted(new_blocked), cli_ctx.network_id
                    )
                except EeroException as e:
                    if isinstance(e, EeroPremiumRequiredException):
                        console.print("[yellow]This feature requires Eero Plus[/yellow]")
                        sys.exit(ExitCode.PREMIUM_REQUIRED)
                    console.print(f"[red]✗[/red] Error blocking apps: {e}")
                    sys.exit(ExitCode.GENERIC_ERROR)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                for app in apps:
                    console.print(f"[green]✓[/green] {app} blocked")
            else:
                console.print("[red]✗[/red] Failed to block apps")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(block_apps)

    asyncio.run(run_cmd())


@apps_group.command(name="unblock")
@click.argument("profile_identifier")
@click.argument("apps", nargs=-1, required=True)
@force_option
@network_option
@click.pass_context
def apps_unblock(
    ctx: click.Context,
    profile_identifier: str,
    apps: tuple,
    force: Optional[bool],
    network_id: Optional[str],
) -> None:
    """Unblock application(s) for a profile.

    \b
    Arguments:
      PROFILE_IDENTIFIER  Profile ID or name
      APPS                App identifier(s) to unblock
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.console
    spec = get_write_spec("profile apps unblock")
    cli_ctx.active_write_spec = spec

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

            try:
                require_write_confirmation(
                    spec,
                    target=f"{target.get('name') or profile_identifier}: {', '.join(apps)}",
                    ctx=SafetyContext(
                        force=cli_ctx.force,
                        non_interactive=cli_ctx.non_interactive,
                        dry_run=cli_ctx.dry_run,
                    ),
                    console=cli_ctx.err_console,
                )
            except SafetyError as e:
                cli_ctx.renderer.render_error(e.message)
                sys.exit(e.exit_code)

            with cli_ctx.status("Getting current blocked apps..."):
                try:
                    raw_apps = await client.get_dns_policy_applications(
                        target["id"], cli_ctx.network_id
                    )
                except EeroException as e:
                    if isinstance(e, EeroPremiumRequiredException):
                        console.print("[yellow]This feature requires Eero Plus[/yellow]")
                        sys.exit(ExitCode.PREMIUM_REQUIRED)
                    raise

            applications = _extract_dns_policy_applications(raw_apps)
            new_blocked = _blocked_app_ids(applications) - set(apps)

            # `set_profile_blocked_applications` REPLACES the full list -- show
            # the user exactly what will be sent before issuing the write.
            cli_ctx.err_console.print(
                f"Blocked applications after this change: {sorted(new_blocked)}"
            )

            with cli_ctx.status("Unblocking apps..."):
                try:
                    result = await client.set_profile_blocked_applications(
                        target["id"], sorted(new_blocked), cli_ctx.network_id
                    )
                except EeroException as e:
                    if isinstance(e, EeroPremiumRequiredException):
                        console.print("[yellow]This feature requires Eero Plus[/yellow]")
                        sys.exit(ExitCode.PREMIUM_REQUIRED)
                    console.print(f"[red]✗[/red] Error unblocking apps: {e}")
                    sys.exit(ExitCode.GENERIC_ERROR)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                for app in apps:
                    console.print(f"[green]✓[/green] {app} unblocked")
            else:
                console.print("[red]✗[/red] Failed to unblock apps")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(unblock_apps)

    asyncio.run(run_cmd())


# ==================== Schedule Subcommand Group ====================


@profile_group.group(name="schedule")
@click.pass_context
def schedule_group(ctx: click.Context) -> None:
    """Manage internet access schedule.

    \b
    Commands:
      show   - Show schedule
      set    - Set bedtime schedule
      clear  - Clear all schedules
      delete - Delete one schedule entry
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
                raw_schedule = await client.get_schedules(target["id"], cli_ctx.network_id)

            # `get_schedules` returns `data` as a *list* of pause sub-resources
            # (eero-api 8.0.1), not the old `{"enabled": ..., "time_blocks": [...]}`
            # object.
            data = extract_data(raw_schedule) if isinstance(raw_schedule, dict) else raw_schedule
            schedules = data if isinstance(data, list) else []

            if cli_ctx.is_json_output():
                renderer.render_json({"schedules": schedules}, "eero.profile.schedule.show/v1")
            elif cli_ctx.is_list_output():
                renderer.render_text({"schedules": schedules}, "eero.profile.schedule.show/v1")
            else:
                if not schedules:
                    content = "[dim]No schedules set[/dim]"
                else:
                    lines = []
                    for i, pause in enumerate(schedules, 1):
                        name = pause.get("name", "?")
                        days = ", ".join(pause.get("days", []))
                        start = pause.get("start", "?")
                        end = pause.get("end", "?")
                        enabled = pause.get("enabled", False)
                        status = "[green]enabled[/green]" if enabled else "[dim]disabled[/dim]"
                        lines.append(f"{i}. {name} ({status}) {days}: {start} - {end}")
                    content = "\n".join(lines)

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

            spec = get_write_spec("profile schedule set")
            cli_ctx.active_write_spec = spec
            try:
                require_write_confirmation(
                    spec,
                    target=f"{target.get('name') or profile_identifier} ({start} - {end})",
                    ctx=SafetyContext(
                        force=cli_ctx.force,
                        non_interactive=cli_ctx.non_interactive,
                        dry_run=cli_ctx.dry_run,
                    ),
                    console=cli_ctx.err_console,
                )
            except SafetyError as e:
                cli_ctx.renderer.render_error(e.message)
                sys.exit(e.exit_code)

            desired_days = tuple(sorted(d.lower() for d in (days_list or _SCHEDULE_ALL_DAYS)))
            desired = (start, end, desired_days)

            async def read() -> Any:
                with cli_ctx.status("Reading current schedule..."):
                    raw_schedule = await client.get_schedules(target["id"], cli_ctx.network_id)
                data = (
                    extract_data(raw_schedule) if isinstance(raw_schedule, dict) else raw_schedule
                )
                schedules = data if isinstance(data, list) else []
                for entry in schedules:
                    if isinstance(entry, dict) and entry.get("name") == "Bedtime":
                        return (
                            entry.get("start"),
                            entry.get("end"),
                            tuple(sorted(entry.get("days") or [])),
                        )
                # Sentinel: no existing "Bedtime" schedule to compare against.
                return ("", "", ())

            async def write() -> Any:
                with cli_ctx.status("Setting schedule..."):
                    return await client.enable_bedtime(
                        target["id"], start, end, days_list, cli_ctx.network_id
                    )

            await write_if_changed(
                read,
                desired,
                write,
                force=cli_ctx.force,
                console=console,
                read_command=spec.read_command,
            )

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

            spec = get_write_spec("profile schedule clear")
            cli_ctx.active_write_spec = spec
            try:
                require_write_confirmation(
                    spec,
                    target=target.get("name") or profile_identifier,
                    ctx=SafetyContext(
                        force=cli_ctx.force,
                        non_interactive=cli_ctx.non_interactive,
                        dry_run=cli_ctx.dry_run,
                    ),
                    console=cli_ctx.err_console,
                )
            except SafetyError as e:
                cli_ctx.renderer.render_error(e.message)
                sys.exit(e.exit_code)

            with cli_ctx.status("Clearing schedule..."):
                results = await client.clear_profile_schedule(target["id"], cli_ctx.network_id)

            # `clear_profile_schedule` returns a list of raw responses, one per
            # deleted pause (eero-api 8.0.1); success = every element's
            # `meta.code` is 2xx (an empty list means there was nothing to clear).
            results_list = results if isinstance(results, list) else []
            all_succeeded = all(
                200 <= r.get("meta", {}).get("code", 0) < 300
                for r in results_list
                if isinstance(r, dict)
            )
            if all_succeeded:
                console.print(
                    f"[bold green]Schedule cleared ({len(results_list)} entry(ies))[/bold green]"
                )
            else:
                console.print("[red]Failed to clear schedule[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(clear_schedule)

    asyncio.run(run_cmd())


@schedule_group.command(name="delete")
@click.argument("profile_identifier")
@click.argument("schedule_id")
@force_option
@network_option
@click.pass_context
def schedule_delete(
    ctx: click.Context,
    profile_identifier: str,
    schedule_id: str,
    force: Optional[bool],
    network_id: Optional[str],
) -> None:
    """Delete one schedule entry for a profile.

    \b
    Arguments:
      PROFILE_IDENTIFIER  Profile ID or name
      SCHEDULE_ID          Schedule id, or the tail of its `url`
                            (see `eero profile schedule show`)
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.console

    async def run_cmd() -> None:
        async def delete_one(client: EeroClient) -> None:
            with cli_ctx.status("Finding profile..."):
                raw_response = await client.get_profiles(cli_ctx.network_id)

            profiles = extract_profiles(raw_response)
            target = _find_profile(profiles, profile_identifier)

            if not target or not target.get("id"):
                console.print(f"[red]Profile '{profile_identifier}' not found[/red]")
                console.print("[dim]Try: eero profile list[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            with cli_ctx.status("Finding schedule..."):
                raw_schedule = await client.get_schedules(target["id"], cli_ctx.network_id)

            data = extract_data(raw_schedule) if isinstance(raw_schedule, dict) else raw_schedule
            schedules = data if isinstance(data, list) else []

            # `update_schedule`/`delete_schedule` reject a bare id (migration
            # plan §2.5 decision 4); the caller must pass the envelope. Match
            # on the schedule's own `id` field when present, else the tail of
            # its `url`, and hand the whole entry to `delete_schedule`.
            match = None
            for entry in schedules:
                if not isinstance(entry, dict):
                    continue
                if entry.get("id") == schedule_id or (
                    extract_id_from_url(entry.get("url")) == schedule_id
                ):
                    match = entry
                    break

            if match is None:
                console.print(f"[red]Schedule '{schedule_id}' not found[/red]")
                console.print(f"[dim]Try: eero profile schedule show {profile_identifier}[/dim]")
                sys.exit(ExitCode.NOT_FOUND)

            spec = get_write_spec("profile schedule delete")
            cli_ctx.active_write_spec = spec
            try:
                require_write_confirmation(
                    spec,
                    target=match.get("name") or schedule_id,
                    ctx=SafetyContext(
                        force=cli_ctx.force,
                        non_interactive=cli_ctx.non_interactive,
                        dry_run=cli_ctx.dry_run,
                    ),
                    console=cli_ctx.console,
                )
            except SafetyError as e:
                cli_ctx.renderer.render_error(e.message)
                sys.exit(e.exit_code)

            with cli_ctx.status("Deleting schedule..."):
                result = await client.delete_schedule(match)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print("[bold green]Schedule deleted[/bold green]")
            else:
                console.print("[red]Failed to delete schedule[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(delete_one)

    asyncio.run(run_cmd())
