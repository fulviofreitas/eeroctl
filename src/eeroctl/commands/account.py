"""Account-scoped commands for the Eero CLI.

Commands:
- eero account premium        -- get_premium_customer (client.py:2310)
- eero account name set       -- set_account_name (client.py:2642)
- eero account email set      -- set_account_email (client.py:2648)
- eero account email verify   -- verify_account_email (client.py:2652)
- eero account phone set      -- set_account_phone (client.py:2658)
- eero account phone verify   -- verify_account_phone (client.py:2662)
- eero account consents       -- set_account_consents (client.py:2668)
- eero account push set       -- set_push_settings (client.py:2422)

`get_premium_customer` is the only phase-A facade method that takes no
`network_id` at all (eero-api 8.0.1 migration plan §4, `account premium` row:
"account-scoped"), so this command has no `--network-id` option. Every write
in this module is account-scoped the same way -- none of the `AccountAPI`/
`set_push_settings` facade methods take a `network_id` either (migration
plan §4 phase C, `account name set` / ... row).
"""

import asyncio
import sys
from typing import Any, Optional, Tuple

import click
from eero import EeroClient

from ..context import ensure_cli_context, get_cli_context
from ..exit_codes import ExitCode
from ..formatting.account import print_account_premium
from ..options import apply_options, force_option, output_option
from ..safety import SafetyContext, SafetyError, get_write_spec, require_write_confirmation
from ..transformers import extract_data
from ..transformers.account import extract_premium_customer
from ..utils import parse_bool_key_value_pairs, run_with_client, write_if_changed


@click.group(name="account")
@click.pass_context
def account_group(ctx: click.Context) -> None:
    """Account-scoped commands (not tied to a specific network).

    \b
    Commands:
      premium  - Account-wide premium/subscription status
      name     - Manage the account holder's name
      email    - Manage the account's email (set, then verify)
      phone    - Manage the account's phone number (set, then verify)
      consents - Manage marketing-email consent
      push     - Manage push-notification settings

    \b
    Examples:
      eero account premium
      eero account name set "Jane Doe"
      eero account email set jane@example.com
      eero account email verify 123456
    """
    ensure_cli_context(ctx)


@account_group.command(name="premium")
@output_option
@click.pass_context
def account_premium(ctx: click.Context, output: Optional[str]) -> None:
    """Show account-wide premium/subscription status."""
    cli_ctx = apply_options(ctx, output=output)

    async def run_cmd() -> None:
        async def get_premium(client: EeroClient) -> None:
            with cli_ctx.status("Getting account premium status..."):
                raw = await client.get_premium_customer()
            print_account_premium(cli_ctx, extract_premium_customer(raw))

        await run_with_client(get_premium)

    asyncio.run(run_cmd())


# ==================== Account name (read-first) ====================


@account_group.group(name="name")
@click.pass_context
def account_name_group(ctx: click.Context) -> None:
    """Manage the account holder's name.

    \b
    Commands:
      set - Set the account holder's name
    """
    pass


@account_name_group.command(name="set")
@click.argument("name")
@force_option
@click.pass_context
def account_name_set(ctx: click.Context, name: str, force: Optional[bool]) -> None:
    """Set the account holder's name.

    \b
    Arguments:
      NAME  New account holder name
    """
    cli_ctx = apply_options(ctx, force=force)
    console = cli_ctx.err_console

    spec = get_write_spec("account name set")
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
        async def set_name(client: EeroClient) -> None:
            async def read() -> Any:
                with cli_ctx.status("Reading current account name..."):
                    raw = await client.get_account()
                data = extract_data(raw) if isinstance(raw, dict) else {}
                return data.get("name")

            async def write() -> Any:
                with cli_ctx.status(f"Setting account name to '{name}'..."):
                    return await client.set_account_name(name)

            await write_if_changed(
                read,
                name,
                write,
                force=cli_ctx.force,
                console=console,
                read_command=spec.read_command,
            )

        await run_with_client(set_name)

    asyncio.run(run_cmd())


# ==================== Account email (two-step) ====================


@account_group.group(name="email")
@click.pass_context
def account_email_group(ctx: click.Context) -> None:
    """Manage the account's email address.

    \b
    Commands:
      set    - Start an email change (sends a verification code)
      verify - Confirm an email change with the code
    """
    pass


@account_email_group.command(name="set")
@click.argument("email")
@force_option
@click.pass_context
def account_email_set(ctx: click.Context, email: str, force: Optional[bool]) -> None:
    """Start an email change. Sends a verification code to EMAIL.

    \b
    Arguments:
      EMAIL  New email address
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.err_console
    effective_force = force or cli_ctx.force

    spec = get_write_spec("account email set")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target=email,
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
        async def set_email(client: EeroClient) -> None:
            with cli_ctx.status(f"Requesting email change to '{email}'..."):
                result = await client.set_account_email(email)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print(f"[bold green]Verification code sent to '{email}'.[/bold green]")
                console.print("[dim]Run `eero account email verify <code>` to confirm.[/dim]")
            else:
                console.print(f"[red]Failed to request email change to '{email}'[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_email)

    asyncio.run(run_cmd())


@account_email_group.command(name="verify")
@click.argument("code")
@force_option
@click.pass_context
def account_email_verify(ctx: click.Context, code: str, force: Optional[bool]) -> None:
    """Confirm a pending email change with the verification CODE."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.err_console
    effective_force = force or cli_ctx.force

    spec = get_write_spec("account email verify")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target="account email",
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
        async def verify_email(client: EeroClient) -> None:
            with cli_ctx.status("Verifying email change..."):
                result = await client.verify_account_email(code)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print("[bold green]Email change verified.[/bold green]")
            else:
                console.print("[red]Failed to verify email change[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(verify_email)

    asyncio.run(run_cmd())


# ==================== Account phone (two-step) ====================


@account_group.group(name="phone")
@click.pass_context
def account_phone_group(ctx: click.Context) -> None:
    """Manage the account's phone number.

    \b
    Commands:
      set    - Start a phone number change (sends a verification code)
      verify - Confirm a phone number change with the code
    """
    pass


@account_phone_group.command(name="set")
@click.argument("phone")
@force_option
@click.pass_context
def account_phone_set(ctx: click.Context, phone: str, force: Optional[bool]) -> None:
    """Start a phone number change. Sends a verification code to PHONE.

    \b
    Arguments:
      PHONE  New phone number
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.err_console
    effective_force = force or cli_ctx.force

    spec = get_write_spec("account phone set")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target=phone,
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
        async def set_phone(client: EeroClient) -> None:
            with cli_ctx.status(f"Requesting phone number change to '{phone}'..."):
                result = await client.set_account_phone(phone)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print(f"[bold green]Verification code sent to '{phone}'.[/bold green]")
                console.print("[dim]Run `eero account phone verify <code>` to confirm.[/dim]")
            else:
                console.print(f"[red]Failed to request phone number change to '{phone}'[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_phone)

    asyncio.run(run_cmd())


@account_phone_group.command(name="verify")
@click.argument("code")
@force_option
@click.pass_context
def account_phone_verify(ctx: click.Context, code: str, force: Optional[bool]) -> None:
    """Confirm a pending phone number change with the verification CODE."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.err_console
    effective_force = force or cli_ctx.force

    spec = get_write_spec("account phone verify")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target="account phone",
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
        async def verify_phone(client: EeroClient) -> None:
            with cli_ctx.status("Verifying phone number change..."):
                result = await client.verify_account_phone(code)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print("[bold green]Phone number change verified.[/bold green]")
            else:
                console.print("[red]Failed to verify phone number change[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(verify_phone)

    asyncio.run(run_cmd())


# ==================== Account consents (read-first) ====================


@account_group.command(name="consents")
@click.option(
    "--marketing-emails/--no-marketing-emails",
    "marketing_emails",
    default=None,
    help="Opt in/out of marketing emails.",
)
@force_option
@click.pass_context
def account_consents(
    ctx: click.Context, marketing_emails: Optional[bool], force: Optional[bool]
) -> None:
    """Manage marketing-email consent.

    \b
    Options:
      --marketing-emails / --no-marketing-emails  Required; one must be given
    """
    cli_ctx = apply_options(ctx, force=force)
    console = cli_ctx.err_console

    if marketing_emails is None:
        console.print("[red]One of --marketing-emails/--no-marketing-emails is required[/red]")
        sys.exit(ExitCode.USAGE_ERROR)

    spec = get_write_spec("account consents")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target="account",
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
        async def set_consents(client: EeroClient) -> None:
            async def read() -> bool:
                with cli_ctx.status("Reading current consents..."):
                    raw = await client.get_account()
                data = extract_data(raw) if isinstance(raw, dict) else {}
                consents = data.get("consents") if isinstance(data, dict) else None
                consents = consents if isinstance(consents, dict) else {}
                return bool(consents.get("marketing_emails", not marketing_emails))

            async def write() -> Any:
                with cli_ctx.status("Updating consents..."):
                    return await client.set_account_consents(marketing_emails=marketing_emails)

            await write_if_changed(
                read,
                marketing_emails,
                write,
                force=cli_ctx.force,
                console=console,
                read_command=spec.read_command,
            )

        await run_with_client(set_consents)

    asyncio.run(run_cmd())


# ==================== Account push settings ====================


@account_group.group(name="push")
@click.pass_context
def account_push_group(ctx: click.Context) -> None:
    """Manage push-notification settings.

    \b
    Commands:
      set - Update push-notification settings
    """
    pass


@account_push_group.command(name="set")
@click.option(
    "--set",
    "set_pairs",
    multiple=True,
    metavar="KEY=VALUE",
    help="Setting to change, as KEY=VALUE (true/false/1/0). Repeatable.",
)
@force_option
@click.pass_context
def account_push_set(ctx: click.Context, set_pairs: Tuple[str, ...], force: Optional[bool]) -> None:
    """Update push-notification settings.

    No dedicated read exists for the current values, so this always writes.

    \b
    Examples:
      eero account push set --set device_offline=true --set weekly_digest=false
    """
    cli_ctx = apply_options(ctx, force=force)
    console = cli_ctx.err_console
    settings = parse_bool_key_value_pairs(console, set_pairs)

    spec = get_write_spec("account push set")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target="account",
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
        async def set_push(client: EeroClient) -> None:
            with cli_ctx.status("Updating push-notification settings..."):
                result = await client.set_push_settings(settings)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print("[bold green]Push-notification settings updated.[/bold green]")
            else:
                console.print("[red]Failed to update push-notification settings[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_push)

    asyncio.run(run_cmd())
