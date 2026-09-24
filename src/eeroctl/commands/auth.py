"""Authentication commands for the Eero CLI.

Commands:
- eero auth login: Start authentication flow
- eero auth logout: End current session
- eero auth clear: Clear all stored credentials
- eero auth status: Show authentication status
"""

import asyncio
import json
import logging
import sys
from dataclasses import dataclass
from typing import Any, Optional, TypedDict

import click
from eero import EeroClient
from eero.exceptions import EeroAuthenticationException, EeroException, EeroValidationException
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from ..const import KEYRING_ACCOUNT_NAME, KEYRING_SERVICE_NAME
from ..context import EeroCliContext, ensure_cli_context, get_cli_context
from ..exit_codes import ExitCode
from ..output import OutputFormat
from ..sdk_private import clear_all_credentials, resend_verification_code
from ..utils import (
    build_client,
    get_auth_method,
    get_config_file,
    get_cookie_file,
    get_legacy_backup_path,
    get_session_token_override,
    prepare_client,
    set_auth_method,
    set_preferred_network,
)

logger = logging.getLogger(__name__)

# EEROCTL_SESSION_TOKEN fully owns the session for the process; there is
# nothing on disk or in the keyring to log in/out of or clear.
_SESSION_FROM_ENV_REFUSAL = (
    "session comes from EEROCTL_SESSION_TOKEN; unset it to manage stored credentials"
)


def _refuse_if_session_token_managed(cli_ctx: EeroCliContext) -> bool:
    """Refuse auth login/logout/clear when EEROCTL_SESSION_TOKEN is set.

    Returns:
        True if the command must stop here (caller should ``sys.exit(2)``).
    """
    if get_session_token_override() is None:
        return False
    cli_ctx.renderer.render_error(_SESSION_FROM_ENV_REFUSAL)
    return True


def _remove_legacy_backup_if_present(cli_ctx: EeroCliContext) -> None:
    """Delete the plaintext pre-v8 credential backup, if one exists.

    ``backup_legacy_cookie_file`` (utils.py) writes this file so a
    rollback to a 7.x release does not lose the session. Once credentials
    are explicitly logged out of or cleared, that plaintext copy must not
    linger indefinitely (v8 migration plan §8.2; security review).
    """
    backup_path = get_legacy_backup_path(get_cookie_file())
    try:
        if backup_path.exists():
            backup_path.unlink()
            cli_ctx.err_console.print("removed pre-v8 credential backup")
    except OSError as ex:
        logger.debug("Could not remove the pre-v8 backup file: %s", ex)


class _UserData(TypedDict):
    """Type definition for user data in account info."""

    id: str | None
    name: str | None
    email: str | None
    phone: str | None
    role: str | None
    created_at: str | None


class _AccountData(TypedDict):
    """Type definition for account data."""

    id: str | None
    name: str | None
    premium_status: str | None
    premium_expiry: str | None
    created_at: str | None
    users: list[_UserData]


class _SessionInfo(TypedDict):
    """An informational-only probe of the cookie file.

    Never used to determine session validity: schema 2 (eero-api v8) drops
    ``session_expiry``/``refresh_token`` entirely, and a valid session can
    live in the keyring alone with no cookie file on disk at all. Validity is
    always a live ``client.is_authenticated`` / ``get_account()`` probe (see
    the v8 migration plan, §2.1).
    """

    path: str
    present: bool
    schema_version: int | None
    legacy_backup_present: bool


@click.group(name="auth")
@click.pass_context
def auth_group(ctx: click.Context) -> None:
    """Manage authentication.

    \b
    Commands:
      login   - Authenticate with your Eero account
      logout  - End current session
      clear   - Clear all stored credentials
      status  - Show authentication status

    \b
    Examples:
      eero auth login          # Start login flow
      eero auth status         # Check if authenticated
      eero auth logout         # End session
    """
    ensure_cli_context(ctx)


@auth_group.command(name="login")
@click.option("--force", is_flag=True, help="Force new login even if already authenticated")
@click.option("--no-keyring", is_flag=True, help="Don't use keyring for secure token storage")
@click.pass_context
def auth_login(ctx: click.Context, force: bool, no_keyring: bool) -> None:
    """Login to your Eero account.

    Starts an interactive authentication flow. A verification code
    will be sent to your email or phone number.

    \b
    Examples:
      eero auth login           # Start login flow
      eero auth login --force   # Force new login
      eero auth login --no-keyring  # Use file storage only
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    if _refuse_if_session_token_managed(cli_ctx):
        sys.exit(ExitCode.USAGE_ERROR)

    # Determine use_keyring setting:
    # - If --no-keyring is specified, use cookie_file method
    # - Otherwise, use the saved preference (defaults to keyring)
    use_keyring = not no_keyring if no_keyring else get_auth_method() == "keyring"

    async def run() -> None:
        async with build_client(use_keyring=use_keyring) as client:
            if client.is_authenticated and not force:
                # Validate session is actually working, not just locally present
                try:
                    await client.get_networks()
                    console.print(
                        "[bold yellow]Already authenticated.[/bold yellow] "
                        "Use --force to login again."
                    )
                    return
                except EeroAuthenticationException:
                    # Session expired, continue with login flow
                    console.print("[yellow]Session expired. Starting new login...[/yellow]")

            await _interactive_login(client, force, console, cli_ctx)

            # Save the auth_method preference for future commands
            set_auth_method("keyring" if use_keyring else "cookie_file")

    try:
        asyncio.run(run())
    except EeroAuthenticationException as e:
        cli_ctx.renderer.render_error(_render_auth_error(e))
        sys.exit(ExitCode.AUTH_REQUIRED)
    except EeroException as e:
        cli_ctx.renderer.render_error(str(e))
        sys.exit(ExitCode.GENERIC_ERROR)


def _render_auth_error(exc: EeroAuthenticationException) -> str:
    """Render an auth exception's message, appending ``error_code`` if present.

    ``error_code`` only exists on eero-api 8+ (``getattr`` with a default
    keeps this safe on 7.0.0 too). Never renders ``.envelope``: it can carry
    user tokens, emails or phone numbers.
    """
    message = str(exc)
    error_code = getattr(exc, "error_code", None)
    if error_code:
        message = f"{message} (error code: {error_code})"
    return message


async def _try_reuse_session(client: EeroClient, console: Console, cli_ctx: EeroCliContext) -> bool:
    """Offer to keep the existing session; True only if the user accepts and it works."""
    # Check for an existing session via the client's own state, never the
    # cookie file directly: schema 2 drops session_expiry (migration plan
    # §2.1), and a valid session can live in the keyring alone with no
    # cookie file on disk.
    console.print(
        Panel.fit(
            "An existing authentication session was found.",
            title="Eero Login",
            border_style="blue",
        )
    )
    if not Confirm.ask("Do you want to reuse the existing session?"):
        return False

    with cli_ctx.status("Testing existing session..."):
        try:
            networks = await client.get_networks()
        except EeroException as ex:
            logger.debug("Session validation failed: %s", ex)
            console.print("[yellow]Existing session invalid.[/yellow]")
            return False
        console.print(f"[bold green]Session valid! Found {len(networks)} network(s).[/bold green]")
        return True


async def _request_verification_code(
    client: EeroClient, user_identifier: str, console: Console, cli_ctx: EeroCliContext
) -> None:
    """Send the verification code; exits 3 on any failure."""
    with cli_ctx.status("Requesting verification code..."):
        try:
            result = await client.login(user_identifier)
        except EeroException as ex:
            # Every login() failure exits 3: on eero-api 8+, a rejected
            # identifier (malformed email/phone) already surfaces as
            # EeroAuthenticationException, so there is no separate
            # EeroValidationException case to special-case here.
            error_code = getattr(ex, "error_code", None)
            message = f"[bold red]Error:[/bold red] {ex}"
            if error_code:
                message = f"{message} (error code: {error_code})"
            console.print(message)
            sys.exit(ExitCode.AUTH_REQUIRED)
        if not result:
            console.print("[bold red]Failed to request verification code[/bold red]")
            sys.exit(ExitCode.AUTH_REQUIRED)
        console.print("[bold green]Verification code sent![/bold green]")


def _first_network_id(networks_response: dict[str, Any]) -> Optional[str]:
    """Pick the first network ID out of a ``get_networks()`` envelope."""
    data = networks_response.get("data", {})
    network_list: list[dict[str, Any]] = []
    if isinstance(data, list):
        network_list = data
    elif isinstance(data, dict):
        network_list = data.get("networks") or data.get("data") or []
    if not network_list:
        return None
    first_network = network_list[0]
    net_id = first_network.get("id")
    if not net_id and first_network.get("url"):
        net_id = str(first_network["url"]).rstrip("/").split("/")[-1]
    return str(net_id) if net_id else None


async def _save_preferred_network(client: EeroClient) -> None:
    """Best-effort: remember the first network as the preferred one."""
    try:
        net_id = _first_network_id(await client.get_networks())
        if net_id:
            set_preferred_network(net_id)
            logger.debug("Saved preferred network: %s", net_id)
    except Exception as ex:
        logger.debug("Could not get networks for preferred: %s", ex)


async def _verify_code(
    client: EeroClient, verification_code: str, console: Console, cli_ctx: EeroCliContext
) -> bool:
    """Submit one verification code; True on a successful login."""
    with cli_ctx.status("Verifying..."):
        try:
            result = await client.verify(verification_code)
        except EeroException as ex:
            console.print(f"[bold red]Error:[/bold red] {ex}")
            return False
        if not result:
            return False
        console.print("[bold green]Login successful![/bold green]")
        await _save_preferred_network(client)
        return True


async def _offer_resend(client: EeroClient, console: Console, cli_ctx: EeroCliContext) -> None:
    """Ask whether to resend the verification code and do so if accepted."""
    if Confirm.ask("Resend verification code?"):
        with cli_ctx.status("Resending..."):
            await resend_verification_code(client)
            console.print("[green]Code resent![/green]")


async def _interactive_login(
    client: EeroClient, force: bool, console: Console, cli_ctx: EeroCliContext
) -> bool:
    """Interactive login process."""
    if client.is_authenticated and not force:
        if await _try_reuse_session(client, console, cli_ctx):
            return True

    await clear_all_credentials(client)

    console.print(
        Panel.fit(
            "Please login to your Eero account.\nA verification code will be sent to you.",
            title="Eero Login",
            border_style="blue",
        )
    )
    user_identifier = Prompt.ask("Email or phone number")
    await _request_verification_code(client, user_identifier, console, cli_ctx)

    max_attempts = 3
    for attempt in range(max_attempts):
        verification_code = Prompt.ask("Verification code (check your email/phone)")
        if await _verify_code(client, verification_code, console, cli_ctx):
            return True
        if attempt < max_attempts - 1:
            await _offer_resend(client, console, cli_ctx)

    console.print("[bold red]Too many failed attempts[/bold red]")
    return False


@auth_group.command(name="logout")
@click.pass_context
def auth_logout(ctx: click.Context) -> None:
    """Logout from your Eero account.

    Ends the current session and clears the session token.
    Credentials are preserved for easy re-authentication.
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    if _refuse_if_session_token_managed(cli_ctx):
        sys.exit(ExitCode.USAGE_ERROR)

    # A stale plaintext pre-v8 backup has no reason to survive a logout,
    # regardless of whether there was an active session to end.
    _remove_legacy_backup_if_present(cli_ctx)

    async def run() -> None:
        async with build_client() as client:
            if not client.is_authenticated:
                console.print("[yellow]Not logged in[/yellow]")
                return

            with cli_ctx.status("Logging out..."):
                try:
                    result = await client.logout()
                    if result:
                        console.print("[bold green]Logged out successfully[/bold green]")
                    else:
                        console.print("[bold red]Failed to logout[/bold red]")
                except EeroException as ex:
                    console.print(f"[bold red]Error:[/bold red] {ex}")
                    sys.exit(ExitCode.GENERIC_ERROR)

    try:
        asyncio.run(run())
    except EeroValidationException as e:
        # A bad constructor option (e.g. EEROCTL_ACCEPT_LANGUAGE) raised at
        # build_client() time, before any client method is even called.
        cli_ctx.renderer.render_error(str(e))
        sys.exit(ExitCode.USAGE_ERROR)


@auth_group.command(name="clear")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def auth_clear(ctx: click.Context, force: bool) -> None:
    """Clear all stored authentication data.

    Removes all stored credentials including tokens and session data.
    You will need to login again after this.
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    if _refuse_if_session_token_managed(cli_ctx):
        sys.exit(ExitCode.USAGE_ERROR)

    if not force and not cli_ctx.non_interactive:
        confirmed = Confirm.ask(
            "This will clear all authentication data. Continue?",
            default=False,
        )
        if not confirmed:
            console.print("[yellow]Cancelled[/yellow]")
            return
    elif cli_ctx.non_interactive and not force:
        cli_ctx.renderer.render_error(
            "Clearing auth data requires confirmation. Use --force in non-interactive mode."
        )
        sys.exit(ExitCode.SAFETY_RAIL)

    async def run() -> None:
        async with build_client() as client:
            await clear_all_credentials(client)

        # Also remove the plaintext pre-v8 backup: "clear all stored
        # authentication data" must not leave a copy of the token behind.
        _remove_legacy_backup_if_present(cli_ctx)

        # Also delete config.json (contains preferences)
        config_file = get_config_file()
        if config_file.exists():
            try:
                config_file.unlink()
                logger.debug("Deleted config file: %s", config_file)
            except Exception as ex:
                logger.debug("Failed to delete config file: %s", ex)

        console.print("[bold green]Authentication data cleared[/bold green]")

    try:
        asyncio.run(run())
    except EeroValidationException as e:
        # A bad constructor option (e.g. EEROCTL_ACCEPT_LANGUAGE) raised at
        # build_client() time, before any client method is even called.
        cli_ctx.renderer.render_error(str(e))
        sys.exit(ExitCode.USAGE_ERROR)


def _get_session_info() -> _SessionInfo:
    """Probe the cookie file for informational purposes only.

    Never derive session validity from this: see :class:`_SessionInfo`.
    ``schema_version`` is ``None`` for a missing file or a legacy (pre-v8,
    schema 1) record that predates the ``schema_version`` key.
    """
    cookie_file = get_cookie_file()
    info = _SessionInfo(
        path=str(cookie_file),
        present=cookie_file.exists(),
        schema_version=None,
        legacy_backup_present=get_legacy_backup_path(cookie_file).exists(),
    )

    if info["present"]:
        try:
            with open(cookie_file, "r") as f:
                data = json.load(f)
            info["schema_version"] = data.get("schema_version")
        except (OSError, ValueError) as ex:
            logger.debug("Failed to read cookie file: %s", ex)

    return info


def _check_keyring_available() -> bool:
    """Check if the keyring holds a stored eero-api credential."""
    try:
        import keyring

        token = keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_ACCOUNT_NAME)
        return token is not None
    except Exception:
        # keyring backends raise a wide, platform-specific variety of errors
        # (missing backend, locked keychain, ...); "not available" for any
        # of them is the correct fallback, not an EeroException.
        return False


@dataclass(frozen=True)
class _StatusReport:
    """Everything ``eero auth status`` knows, in one place for the renderers."""

    authenticated: bool
    # True: live probe confirmed the session works. False: not
    # authenticated, or the probe rejected the stored token
    # (EeroAuthenticationException/other API error). None: unknown
    # because --offline skipped the probe.
    session_valid: Optional[bool]
    auth_method: str
    session_info: _SessionInfo
    keyring_available: bool
    account_data: Optional[_AccountData]


_STATUS_MARKUP = {
    "valid": "[green]Valid[/green]",
    "stored_not_verified": "[blue]Stored, not verified[/blue]",
    "invalid": "[yellow]Invalid[/yellow]",
    "not_authenticated": "[red]Not authenticated[/red]",
}


def _stored_state(session_token: Optional[str]) -> tuple[_SessionInfo, bool]:
    """Return (cookie-file info, keyring-has-credential) for the stored state."""
    if session_token is None:
        return _get_session_info(), _check_keyring_available()
    # No file or keyring is used in this mode; report accordingly
    # regardless of what may happen to exist on disk. A pre-v8
    # backup, if any, is still a real leftover file worth surfacing.
    cookie_file = get_cookie_file()
    session_info = _SessionInfo(
        path=str(cookie_file),
        present=False,
        schema_version=None,
        legacy_backup_present=get_legacy_backup_path(cookie_file).exists(),
    )
    return session_info, False


def _str_or_none(value: Any) -> Optional[str]:
    """``str(value)`` for a truthy value, else ``None``."""
    return str(value) if value else None


def _parse_user(user: dict[str, Any]) -> _UserData:
    """Build a ``_UserData`` from one raw ``users[]`` entry."""
    return _UserData(
        id=user.get("id"),
        name=user.get("name"),
        email=user.get("email"),
        phone=user.get("phone"),
        role=user.get("role"),
        created_at=_str_or_none(user.get("created_at")),
    )


def _parse_account(raw_account: dict[str, Any]) -> Optional[_AccountData]:
    """Extract account data from a ``GET /account`` envelope; None if malformed."""
    account = raw_account.get("data", raw_account)
    if not isinstance(account, dict):
        return None
    account_id = account.get("id")
    if not account_id and account.get("url"):
        account_id = account["url"].rstrip("/").split("/")[-1]
    return _AccountData(
        id=account_id,
        name=account.get("name"),
        premium_status=account.get("premium_status"),
        premium_expiry=_str_or_none(account.get("premium_expiry")),
        created_at=_str_or_none(account.get("created_at")),
        users=[_parse_user(u) for u in (account.get("users") or []) if isinstance(u, dict)],
    )


async def _probe_session(
    client: EeroClient, cli_ctx: EeroCliContext, is_auth: bool, offline: bool
) -> tuple[Optional[bool], Optional[_AccountData]]:
    """Live-check the stored session; see ``_StatusReport.session_valid``."""
    if not is_auth:
        return False, None
    if offline:
        return None, None
    try:
        with cli_ctx.status("Getting account info..."):
            raw_account = await client.get_account()
    except EeroException as ex:
        logger.debug("Account probe failed: %s", ex)
        return False, None
    return True, _parse_account(raw_account)


def _status_label(is_auth: bool, session_valid: Optional[bool]) -> str:
    """Map the (authenticated, session_valid) pair to its plain status label."""
    if session_valid is True:
        return "valid"
    if session_valid is None:
        return "stored_not_verified"
    return "invalid" if is_auth else "not_authenticated"


def _status_payload(report: _StatusReport) -> dict[str, Any]:
    """The ``eero.auth.status/v2`` structured payload."""
    session_info = report.session_info
    return {
        "authenticated": report.authenticated,
        "session_valid": report.session_valid,
        "auth_method": report.auth_method,
        "storage": {
            "keyring": {"present": report.keyring_available},
            "cookie_file": {
                "path": session_info["path"],
                "present": session_info["present"],
                "schema_version": session_info["schema_version"],
                "legacy_backup_present": session_info["legacy_backup_present"],
            },
        },
        "account": report.account_data,
    }


def _render_status_list(report: _StatusReport) -> None:
    """Parseable key-value rows on stdout."""
    session_info = report.session_info
    schema_version = session_info["schema_version"]
    print(f"status              {_status_label(report.authenticated, report.session_valid)}")
    print(f"auth_method         {report.auth_method}")
    print(f"cookie_file         {session_info['path']}")
    print(f"schema_version      {schema_version if schema_version is not None else 'N/A'}")
    print(f"keyring_available   {report.keyring_available}")
    print(f"legacy_backup       {session_info['legacy_backup_present']}")
    account_data = report.account_data
    if account_data:
        print(f"account_id          {account_data['id']}")
        print(f"account_name        {account_data['name'] or 'N/A'}")
        print(f"premium_status      {account_data['premium_status'] or 'N/A'}")
        print(f"premium_expiry      {account_data['premium_expiry'] or 'N/A'}")
        for u in account_data.get("users", []):
            print(f"user                {u['email']}  {u['role']}  {u['name'] or ''}")


def _session_table(report: _StatusReport) -> Table:
    """The "Session Information" Rich table."""
    session_info = report.session_info
    schema_version = session_info["schema_version"]
    table = Table(title="Session Information")
    table.add_column("Property", style="cyan")
    table.add_column("Value")
    table.add_row(
        "Status", _STATUS_MARKUP[_status_label(report.authenticated, report.session_valid)]
    )
    table.add_row("Auth Method", f"[blue]{report.auth_method}[/blue]")
    table.add_row("Credential Schema", str(schema_version) if schema_version is not None else "N/A")
    table.add_row(
        "Keyring Available",
        "[green]Yes[/green]" if report.keyring_available else "[dim]No[/dim]",
    )
    table.add_row("Cookie File", session_info["path"])
    table.add_row(
        "Legacy Backup",
        "[yellow]Present[/yellow]" if session_info["legacy_backup_present"] else "[dim]No[/dim]",
    )
    return table


def _account_table(account_data: _AccountData) -> Table:
    """The "Account Information" Rich table."""
    table = Table(title="Account Information")
    table.add_column("Property", style="cyan")
    table.add_column("Value")
    table.add_row("Account ID", account_data["id"])
    table.add_row("Account Name", account_data["name"] or "N/A")
    premium = account_data["premium_status"] or "N/A"
    if premium and "active" in premium.lower():
        premium = f"[green]{premium}[/green]"
    table.add_row("Premium Status", premium)
    table.add_row("Premium Expiry", account_data["premium_expiry"] or "N/A")
    table.add_row("Created", account_data["created_at"] or "N/A")
    return table


def _users_table(users: list[_UserData]) -> Table:
    """The "Account Users" Rich table."""
    table = Table(title="Account Users")
    table.add_column("Email", style="cyan")
    table.add_column("Name")
    table.add_column("Role", style="magenta")
    for u in users:
        table.add_row(u["email"], u["name"] or "", u["role"])
    return table


def _render_status_table(report: _StatusReport, console: Console) -> None:
    """Rich tables on stdout, plus a login hint when the session is not confirmed."""
    console.print(_session_table(report))
    account_data = report.account_data
    if account_data:
        console.print()
        console.print(_account_table(account_data))
        if account_data.get("users"):
            console.print()
            console.print(_users_table(account_data["users"]))
    elif report.session_valid is not True:
        console.print()
        console.print("[yellow]Run `eero auth login` to authenticate.[/yellow]")


@auth_group.command(name="status")
@click.option(
    "--offline",
    is_flag=True,
    help=(
        "Report stored state only; skip the live account probe (no API call). "
        "Mutually exclusive with --check: an unverified token must not read as OK."
    ),
)
@click.option(
    "--check",
    "check_only",
    is_flag=True,
    help=(
        "Exit 3 if not authenticated or the stored session is invalid. "
        "Mutually exclusive with --offline: an unverified token must not read as OK."
    ),
)
@click.pass_context
def auth_status(ctx: click.Context, offline: bool, check_only: bool) -> None:
    """Show current authentication status.

    Displays session info, authentication method, and account details. By
    default this makes one live API call (`GET /account`) to confirm the
    stored session actually works; pass --offline to skip it and report only
    what is stored locally.

    --offline and --check cannot be combined: --check's whole purpose is to
    fail on an invalid/revoked token, which --offline cannot detect (it
    never makes the live call), so together they would silently report
    success (exit 0) for a token that no longer works.
    """
    if offline and check_only:
        raise click.UsageError("--offline and --check cannot be used together", ctx=ctx)

    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run() -> bool:
        session_token = get_session_token_override()
        session_info, keyring_available = _stored_state(session_token)

        async with build_client() as client:
            await prepare_client(client)
            is_auth = client.is_authenticated
            session_valid, account_data = await _probe_session(client, cli_ctx, is_auth, offline)

            # Determine auth method: the *configured* method verbatim
            # ("env" under EEROCTL_SESSION_TOKEN, else get_auth_method()'s
            # "keyring"/"cookie_file"), independent of whether the keyring
            # probe actually found a record there -- that's a separate
            # fact, already carried by storage.keyring.present.
            report = _StatusReport(
                authenticated=is_auth,
                session_valid=session_valid,
                auth_method="env" if session_token is not None else get_auth_method(),
                session_info=session_info,
                keyring_available=keyring_available,
                account_data=account_data,
            )

            if cli_ctx.is_structured_output():
                cli_ctx.render_structured(_status_payload(report), "eero.auth.status/v2")
            elif cli_ctx.output_format == OutputFormat.LIST:
                _render_status_list(report)
            else:
                _render_status_table(report, console)

            # "ok" for --check: authenticated, and either confirmed valid or
            # unverified (--offline); never ok when the live probe rejected
            # the token, and never ok with no token at all.
            return is_auth and session_valid is not False

    try:
        ok = asyncio.run(run())
    except EeroValidationException as e:
        # A malformed EEROCTL_SESSION_TOKEN, from prepare_client().
        cli_ctx.renderer.render_error(str(e))
        sys.exit(ExitCode.USAGE_ERROR)

    if check_only and not ok:
        sys.exit(ExitCode.AUTH_REQUIRED)
