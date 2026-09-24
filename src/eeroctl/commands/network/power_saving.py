"""Power-saving settings and schedule commands for the Eero CLI.

Commands:
- eero network power-saving schedules list -- get_power_saving_schedules
  (client.py:2830, verified)
- eero network power-saving enable/disable [--schedule-enabled/
  --no-schedule-enabled] -- set_power_saving (client.py:2812); HIGH mesh
  (migration plan §3.1's mesh-reboot list); reads current state from the
  `get_network` envelope's `power_saving` field (no dedicated GET for the
  toggle itself -- `api/power_saving.py:54` documents this as the read
  source).
- eero network power-saving schedules create -- create_power_saving_schedule
  (client.py:2837); MEDIUM + unverified
- eero network power-saving schedules update <id> -- update_power_saving_schedule
  (client.py:2858); MEDIUM + unverified; >=1 field required
- eero network power-saving schedules delete <id> -- delete_power_saving_schedule
  (client.py:2881); MEDIUM + unverified

`days` is typed `Any` on the facade and forwarded to the API unchanged, with
no documented shape (`api/power_saving.py:132-134`); the CLI collects it as
repeatable `--day` values rather than guessing a single-string format.
"""

import asyncio
import sys
from typing import Any, Optional, Tuple

import click
from eero import EeroClient

from ...exit_codes import ExitCode
from ...formatting.power_saving import print_power_saving_schedules
from ...options import apply_options, common_options, force_option, network_option
from ...safety import SafetyContext, SafetyError, get_write_spec, require_write_confirmation
from ...transformers import extract_data
from ...transformers.power_saving import extract_power_saving_schedules
from ...utils import run_with_client, write_if_changed


@click.group(name="power-saving")
@click.pass_context
def power_saving_group(ctx: click.Context) -> None:
    """Manage power-saving settings.

    \b
    Commands:
      enable    - Enable power saving
      disable   - Disable power saving
      schedules - Power-saving schedules
    """
    pass


@power_saving_group.command(name="enable")
@click.option(
    "--schedule-enabled/--no-schedule-enabled",
    "schedule_enabled",
    default=None,
    help="Whether the power-saving schedule is enabled. Omitted, left unchanged.",
)
@force_option
@network_option
@click.pass_context
def power_saving_enable(
    ctx: click.Context,
    schedule_enabled: Optional[bool],
    force: Optional[bool],
    network_id: Optional[str],
) -> None:
    """Enable power saving.

    Applying this change reboots every eero on the network.
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    _set_power_saving(cli_ctx, True, schedule_enabled)


@power_saving_group.command(name="disable")
@click.option(
    "--schedule-enabled/--no-schedule-enabled",
    "schedule_enabled",
    default=None,
    help="Whether the power-saving schedule is enabled. Omitted, left unchanged.",
)
@force_option
@network_option
@click.pass_context
def power_saving_disable(
    ctx: click.Context,
    schedule_enabled: Optional[bool],
    force: Optional[bool],
    network_id: Optional[str],
) -> None:
    """Disable power saving.

    Applying this change reboots every eero on the network.
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    _set_power_saving(cli_ctx, False, schedule_enabled)


def _set_power_saving(cli_ctx: Any, enable: bool, schedule_enabled: Optional[bool]) -> None:
    """Set the network's power-saving toggle."""
    console = cli_ctx.err_console
    action = "enable" if enable else "disable"
    spec = get_write_spec(f"network power-saving {action}")
    cli_ctx.active_write_spec = spec

    try:
        require_write_confirmation(
            spec,
            target="network",
            ctx=SafetyContext(
                force=cli_ctx.force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
            console=console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    desired: dict = {"enable": enable}
    if schedule_enabled is not None:
        desired["power_saving_schedule_enabled"] = schedule_enabled

    async def run_cmd() -> None:
        async def set_power_saving(client: EeroClient) -> None:
            async def read() -> dict:
                with cli_ctx.status("Reading current power-saving settings..."):
                    raw = await client.get_network(cli_ctx.network_id)
                net_data = extract_data(raw) if isinstance(raw, dict) else {}
                current = net_data.get("power_saving") if isinstance(net_data, dict) else {}
                return current if isinstance(current, dict) else {}

            def compare(current: dict, wanted: dict) -> bool:
                return all(current.get(k) == v for k, v in wanted.items())

            async def write() -> Any:
                with cli_ctx.status(f"{action.capitalize()}ing power saving..."):
                    return await client.set_power_saving(
                        cli_ctx.network_id,
                        enable=enable,
                        power_saving_schedule_enabled=schedule_enabled,
                    )

            await write_if_changed(
                read,
                desired,
                write,
                compare=compare,
                force=cli_ctx.force,
                console=console,
                read_command=spec.read_command,
            )

        await run_with_client(set_power_saving)

    asyncio.run(run_cmd())


@power_saving_group.group(name="schedules")
@click.pass_context
def power_saving_schedules_group(ctx: click.Context) -> None:
    """Manage power-saving schedules.

    \b
    Commands:
      list   - List power-saving schedules
      create - Create a power-saving schedule
      update - Update a power-saving schedule
      delete - Delete a power-saving schedule
    """
    pass


@power_saving_schedules_group.command(name="list")
@common_options
@click.pass_context
def power_saving_schedules_list(
    ctx: click.Context, output: Optional[str], network_id: Optional[str]
) -> None:
    """List power-saving schedules."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_schedules(client: EeroClient) -> None:
            with cli_ctx.status("Getting power-saving schedules..."):
                raw = await client.get_power_saving_schedules(cli_ctx.network_id)
            print_power_saving_schedules(cli_ctx, extract_power_saving_schedules(raw))

        await run_with_client(get_schedules)

    asyncio.run(run_cmd())


@power_saving_schedules_group.command(name="create")
@click.option("--name", required=True, help="The schedule's name.")
@click.option(
    "--day",
    "days",
    multiple=True,
    required=True,
    help="A day the schedule applies to. Repeat for multiple days.",
)
@click.option("--start-time", "start_time", required=True, help="The schedule's start time.")
@click.option("--end-time", "end_time", required=True, help="The schedule's end time.")
@click.option(
    "--enabled/--no-enabled", "enabled", default=True, help="Whether the schedule is enabled."
)
@force_option
@network_option
@click.pass_context
def power_saving_schedules_create(
    ctx: click.Context,
    name: str,
    days: Tuple[str, ...],
    start_time: str,
    end_time: str,
    enabled: bool,
    force: Optional[bool],
    network_id: Optional[str],
) -> None:
    """Create a power-saving schedule."""
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.err_console

    spec = get_write_spec("network power-saving schedules create")
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
            console=console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def create(client: EeroClient) -> None:
            with cli_ctx.status(f"Creating power-saving schedule '{name}'..."):
                result = await client.create_power_saving_schedule(
                    cli_ctx.network_id,
                    name=name,
                    days=list(days),
                    start_time=start_time,
                    end_time=end_time,
                    enabled=enabled,
                )

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") in (200, 201) or result:
                console.print("[bold green]Power-saving schedule created.[/bold green]")
                console.print(f"[dim]Verify with `{spec.read_command}`.[/dim]")
            else:
                console.print("[red]Failed to create power-saving schedule[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(create)

    asyncio.run(run_cmd())


@power_saving_schedules_group.command(name="update")
@click.argument("schedule_id")
@click.option("--name", default=None, help="The schedule's new name.")
@click.option(
    "--day",
    "days",
    multiple=True,
    help="A day the schedule applies to. Repeat for multiple days.",
)
@click.option("--start-time", "start_time", default=None, help="The schedule's new start time.")
@click.option("--end-time", "end_time", default=None, help="The schedule's new end time.")
@click.option(
    "--enabled/--no-enabled",
    "enabled",
    default=None,
    help="Whether the schedule is enabled. Omitted, left unchanged.",
)
@force_option
@network_option
@click.pass_context
def power_saving_schedules_update(
    ctx: click.Context,
    schedule_id: str,
    name: Optional[str],
    days: Tuple[str, ...],
    start_time: Optional[str],
    end_time: Optional[str],
    enabled: Optional[bool],
    force: Optional[bool],
    network_id: Optional[str],
) -> None:
    """Update a power-saving schedule.

    \b
    Arguments:
      SCHEDULE_ID  The schedule's id, as returned by 'network power-saving schedules list'
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.err_console

    if name is None and not days and start_time is None and end_time is None and enabled is None:
        console.print("[red]At least one field must be supplied to update[/red]")
        sys.exit(ExitCode.USAGE_ERROR)

    spec = get_write_spec("network power-saving schedules update")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target=schedule_id,
            ctx=SafetyContext(
                force=cli_ctx.force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
            console=console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def update(client: EeroClient) -> None:
            with cli_ctx.status(f"Updating power-saving schedule {schedule_id}..."):
                result = await client.update_power_saving_schedule(
                    schedule_id,
                    cli_ctx.network_id,
                    name=name,
                    days=list(days) if days else None,
                    start_time=start_time,
                    end_time=end_time,
                    enabled=enabled,
                )

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print("[bold green]Power-saving schedule updated.[/bold green]")
                console.print(f"[dim]Verify with `{spec.read_command}`.[/dim]")
            else:
                console.print("[red]Failed to update power-saving schedule[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(update)

    asyncio.run(run_cmd())


@power_saving_schedules_group.command(name="delete")
@click.argument("schedule_id")
@force_option
@network_option
@click.pass_context
def power_saving_schedules_delete(
    ctx: click.Context, schedule_id: str, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Delete a power-saving schedule.

    \b
    Arguments:
      SCHEDULE_ID  The schedule's id, as returned by 'network power-saving schedules list'
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.err_console

    spec = get_write_spec("network power-saving schedules delete")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target=schedule_id,
            ctx=SafetyContext(
                force=cli_ctx.force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
            console=console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def delete(client: EeroClient) -> None:
            with cli_ctx.status(f"Deleting power-saving schedule {schedule_id}..."):
                result = await client.delete_power_saving_schedule(schedule_id, cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print("[bold green]Power-saving schedule deleted.[/bold green]")
            else:
                console.print("[red]Failed to delete power-saving schedule[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(delete)

    asyncio.run(run_cmd())
