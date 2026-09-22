"""Members and invites reads and writes for the Eero CLI.

Reads:
- eero network members list    -- get_members (client.py:2572, verified)
- eero network members invites -- get_invites (client.py:2579, unverified read;
  403 seen live -- migration plan §4, `network members invites` row)

Writes (migration plan §4 phase C, `network members invite create` row):
- eero network members invite create  -- create_invite (client.py:2584)
- eero network members invite update  -- update_invite (client.py:2589)
- eero network members invite delete  -- delete_invite (client.py:2598)
- eero network members invite respond -- respond_to_invite (client.py:2605)
- eero network members promote        -- promote_member (client.py:2624)
- eero network members remove-admin   -- remove_admin (client.py:2631, HIGH)
- eero network members cancel-pending-admin -- cancel_pending_admin (client.py:2619)

DIGEST-vs-brief deviations (DIGEST.md §6 "Members, Invites & Admins"):
- `create_invite(*, role: str, network_id=None)` takes **no email** -- the
  brief's `invite create <email> --role ...` assumed one; the real facade
  only accepts a role, so `invite create` is `--role` only (no positional
  email argument).
- `update_invite(invite_id, *, invite_nickname: str, network_id=None)` takes
  **`invite_nickname`, not `role`** -- the brief's `invite update <id>
  --role ...` assumed the same shape as create; `invite update` is
  `--nickname` instead.
- `cancel_pending_admin(network_id=None)` takes **no id at all** -- it acts
  on the caller's own pending admin request, so `cancel-pending-admin` has
  no arguments.
"""

import asyncio
import sys
from typing import Optional

import click
from eero import EeroClient
from eero.exceptions import EeroAccessDeniedException, EeroAPIException

from ...context import EeroCliContext, ensure_cli_context, get_cli_context
from ...exit_codes import ExitCode
from ...formatting.members import print_invites, print_members
from ...options import apply_options, common_options, force_option, network_option
from ...safety import SafetyContext, SafetyError, get_write_spec, require_write_confirmation
from ...transformers.members import extract_invites, extract_members
from ...utils import run_with_client

INVITE_ROLES = ("owner", "admin")
"""Roles accepted by `create_invite` (`role: str`, undocumented choice set --
no SDK constant exists to cite; DIGEST.md §6 confirms `Literal[...]` is used
nowhere in the SDK, so this mirrors the brief's own `owner|admin` pairing)."""


@click.group(name="members")
@click.pass_context
def members_group(ctx: click.Context) -> None:
    """Manage network members and pending invites.

    \b
    Commands:
      list                 - Network members
      invites              - Pending invites (not permitted for every account)
      invite                - Manage invites (create/update/delete/respond)
      promote              - Promote a member to admin
      remove-admin         - Remove a user's admin role (irreversible)
      cancel-pending-admin - Cancel the caller's own pending admin request
    """
    ensure_cli_context(ctx)


@members_group.command(name="list")
@common_options
@click.pass_context
def members_list(ctx: click.Context, output: Optional[str], network_id: Optional[str]) -> None:
    """List the network's members."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_members(client: EeroClient) -> None:
            with cli_ctx.status("Getting members..."):
                raw = await client.get_members(cli_ctx.network_id)
            print_members(cli_ctx, extract_members(raw))

        await run_with_client(get_members)

    asyncio.run(run_cmd())


@members_group.command(name="invites")
@common_options
@click.pass_context
def members_invites(ctx: click.Context, output: Optional[str], network_id: Optional[str]) -> None:
    """List the network's pending invites.

    This is an unverified read -- some accounts see a 403 here even when
    they can list members. That case is reported as a friendly message
    rather than a generic "Permission denied" error.
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_invites(client: EeroClient) -> None:
            with cli_ctx.status("Getting invites..."):
                try:
                    raw = await client.get_invites(cli_ctx.network_id)
                except EeroAccessDeniedException:
                    _report_not_permitted(cli_ctx)
                except EeroAPIException as e:
                    # commit 6 maps EeroAccessDeniedException directly; until
                    # then a 403 surfaces as the generic EeroAPIException.
                    if e.status_code == 403:
                        _report_not_permitted(cli_ctx)
                    raise
                else:
                    print_invites(cli_ctx, extract_invites(raw))

        await run_with_client(get_invites)

    asyncio.run(run_cmd())


def _report_not_permitted(cli_ctx: EeroCliContext) -> None:
    """Report a 403 on `members invites` as a friendly message and exit 4."""
    if cli_ctx.is_structured_output():
        cli_ctx.render_structured(
            {"error": "not_permitted", "message": "Not permitted for this account."},
            "eero.network.members.invites/v1",
        )
    else:
        cli_ctx.console.print(
            "[yellow]Not permitted for this account.[/yellow] "
            "[dim]Some accounts cannot view pending invites even though they "
            "can list members.[/dim]"
        )
    raise SystemExit(ExitCode.FORBIDDEN)


# ==================== Invite writes (phase C) ====================


def _confirm_and_run(
    ctx: click.Context,
    command: str,
    target: str,
    force: Optional[bool],
    network_id: Optional[str] = None,
) -> "EeroCliContext":
    """Shared confirm-then-return-context boilerplate for every write below."""
    cli_ctx = apply_options(ctx, force=force, network_id=network_id)
    console = cli_ctx.err_console
    spec = get_write_spec(command)
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target=target,
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
    return cli_ctx


@members_group.group(name="invite")
@click.pass_context
def invite_group(ctx: click.Context) -> None:
    """Manage invites.

    \b
    Commands:
      create  - Create an invite for a role
      update  - Update an invite's nickname
      delete  - Delete an invite
      respond - Accept or decline an invite
    """
    pass


@invite_group.command(name="create")
@click.option("--role", required=True, type=click.Choice(INVITE_ROLES), help="Invite role.")
@force_option
@network_option
@click.pass_context
def invite_create(
    ctx: click.Context, role: str, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Create an invite for a role. No email is taken -- `create_invite`
    generates an invite code/link, not an email-addressed invite."""
    cli_ctx = _confirm_and_run(ctx, "network members invite create", role, force, network_id)
    console = cli_ctx.err_console

    async def run_cmd() -> None:
        async def create(client: EeroClient) -> None:
            with cli_ctx.status(f"Creating '{role}' invite..."):
                result = await client.create_invite(role=role, network_id=cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") in (200, 201) or result:
                console.print(f"[bold green]Invite created for role '{role}'.[/bold green]")
                console.print("[dim]Verify with `eero network members invites`.[/dim]")
            else:
                console.print("[red]Failed to create invite[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(create)

    asyncio.run(run_cmd())


@invite_group.command(name="update")
@click.argument("invite_id")
@click.option("--nickname", required=True, help="New nickname for the invite.")
@force_option
@network_option
@click.pass_context
def invite_update(
    ctx: click.Context,
    invite_id: str,
    nickname: str,
    force: Optional[bool],
    network_id: Optional[str],
) -> None:
    """Update an invite's nickname.

    \b
    Arguments:
      INVITE_ID  The invite's id
    """
    cli_ctx = _confirm_and_run(ctx, "network members invite update", invite_id, force, network_id)
    console = cli_ctx.err_console

    async def run_cmd() -> None:
        async def update(client: EeroClient) -> None:
            with cli_ctx.status(f"Updating invite '{invite_id}'..."):
                result = await client.update_invite(
                    invite_id, invite_nickname=nickname, network_id=cli_ctx.network_id
                )

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print(f"[bold green]Invite '{invite_id}' updated.[/bold green]")
                console.print("[dim]Verify with `eero network members invites`.[/dim]")
            else:
                console.print(f"[red]Failed to update invite '{invite_id}'[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(update)

    asyncio.run(run_cmd())


@invite_group.command(name="delete")
@click.argument("invite_id")
@force_option
@network_option
@click.pass_context
def invite_delete(
    ctx: click.Context, invite_id: str, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Delete an invite.

    \b
    Arguments:
      INVITE_ID  The invite's id
    """
    cli_ctx = _confirm_and_run(ctx, "network members invite delete", invite_id, force, network_id)
    console = cli_ctx.err_console

    async def run_cmd() -> None:
        async def delete(client: EeroClient) -> None:
            with cli_ctx.status(f"Deleting invite '{invite_id}'..."):
                result = await client.delete_invite(invite_id, network_id=cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print(f"[bold green]Invite '{invite_id}' deleted.[/bold green]")
            else:
                console.print(f"[red]Failed to delete invite '{invite_id}'[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(delete)

    asyncio.run(run_cmd())


@invite_group.command(name="respond")
@click.argument("invite_id")
@click.option("--accept", "accept", flag_value=True, default=None, help="Accept the invite.")
@click.option("--decline", "accept", flag_value=False, default=None, help="Decline the invite.")
@force_option
@network_option
@click.pass_context
def invite_respond(
    ctx: click.Context,
    invite_id: str,
    accept: Optional[bool],
    force: Optional[bool],
    network_id: Optional[str],
) -> None:
    """Accept or decline an invite. Exactly one of --accept/--decline is required.

    \b
    Arguments:
      INVITE_ID  The invite's id
    """
    cli_ctx = apply_options(ctx, force=force, network_id=network_id)
    console = cli_ctx.err_console

    if accept is None:
        console.print("[red]One of --accept/--decline is required[/red]")
        sys.exit(ExitCode.USAGE_ERROR)

    action = "Accepting" if accept else "Declining"
    cli_ctx = _confirm_and_run(ctx, "network members invite respond", invite_id, force, network_id)
    console = cli_ctx.err_console

    async def run_cmd() -> None:
        async def respond(client: EeroClient) -> None:
            with cli_ctx.status(f"{action} invite '{invite_id}'..."):
                result = await client.respond_to_invite(
                    accept=accept, invite_id=invite_id, network_id=cli_ctx.network_id
                )

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                verb = "accepted" if accept else "declined"
                console.print(f"[bold green]Invite '{invite_id}' {verb}.[/bold green]")
            else:
                console.print(f"[red]Failed to respond to invite '{invite_id}'[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(respond)

    asyncio.run(run_cmd())


# ==================== Promotion / admin writes (phase C) ====================


@members_group.command(name="promote")
@click.argument("member")
@force_option
@network_option
@click.pass_context
def members_promote(
    ctx: click.Context, member: str, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Promote a member to admin.

    \b
    Arguments:
      MEMBER  The member's id
    """
    cli_ctx = _confirm_and_run(ctx, "network members promote", member, force, network_id)
    console = cli_ctx.err_console

    async def run_cmd() -> None:
        async def promote(client: EeroClient) -> None:
            with cli_ctx.status(f"Promoting '{member}' to admin..."):
                result = await client.promote_member(member, network_id=cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print(f"[bold green]'{member}' promoted to admin.[/bold green]")
                console.print("[dim]Verify with `eero network members list`.[/dim]")
            else:
                console.print(f"[red]Failed to promote '{member}'[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(promote)

    asyncio.run(run_cmd())


@members_group.command(name="remove-admin")
@click.argument("user")
@force_option
@network_option
@click.pass_context
def members_remove_admin(
    ctx: click.Context, user: str, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Remove a user's admin role. Irreversible from this command alone.

    \b
    Arguments:
      USER  The user's id
    """
    cli_ctx = _confirm_and_run(ctx, "network members remove-admin", user, force, network_id)
    console = cli_ctx.err_console

    async def run_cmd() -> None:
        async def remove_admin(client: EeroClient) -> None:
            with cli_ctx.status(f"Removing admin role from '{user}'..."):
                result = await client.remove_admin(user, network_id=cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print(f"[bold green]Admin role removed from '{user}'.[/bold green]")
                console.print("[dim]Verify with `eero network members list`.[/dim]")
            else:
                console.print(f"[red]Failed to remove admin role from '{user}'[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(remove_admin)

    asyncio.run(run_cmd())


@members_group.command(name="cancel-pending-admin")
@force_option
@network_option
@click.pass_context
def members_cancel_pending_admin(
    ctx: click.Context, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Cancel the caller's own pending admin request. Takes no arguments --
    `cancel_pending_admin` acts on the caller, not a named id."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.err_console
    effective_force = force or cli_ctx.force

    spec = get_write_spec("network members cancel-pending-admin")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target="account",
            ctx=SafetyContext(
                force=effective_force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
            console=console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def cancel(client: EeroClient) -> None:
            with cli_ctx.status("Cancelling pending admin request..."):
                result = await client.cancel_pending_admin(cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print("[bold green]Pending admin request cancelled.[/bold green]")
            else:
                console.print("[red]Failed to cancel pending admin request[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(cancel)

    asyncio.run(run_cmd())
