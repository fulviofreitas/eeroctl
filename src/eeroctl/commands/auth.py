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
from typing import Any, Optional, TypedDict

import click
from eero import EeroClient
from eero.exceptions import EeroAuthenticationException, EeroException, EeroValidationException
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
    get_session_token_override,
    prepare_client,
    set_auth_method,
    set_preferred_network,
)

logger = logging.getLogger(__name__)

# EEROCTL_SESSION_TOKEN fully owns the session for the process; there is
# nothing on disk or in the keyring to log in/out of or clear.
_SESSION_TOKEN_REFUSAL = (
    "session comes from EEROCTL_SESSION_TOKEN; unset it to manage stored credentials"
)


def _refuse_if_session_token_managed(cli_ctx: EeroCliContext) -> bool:
    """Refuse auth login/logout/clear when EEROCTL_SESSION_TOKEN is set.

    Returns:
        True if the command must stop here (caller should ``sys.exit(2)``).
    """
    if get_session_token_override() is None:
        return False
    cli_ctx.renderer.render_error(_SESSION_TOKEN_REFUSAL)
    return True


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


async def _interactive_login(
    client: EeroClient, force: bool, console, cli_ctx: EeroCliContext
) -> bool:
    """Interactive login process."""
    # Check for an existing session via the client's own state, never the
    # cookie file directly: schema 2 drops session_expiry (migration plan
    # §2.1), and a valid session can live in the keyring alone with no
    # cookie file on disk.
    if client.is_authenticated and not force:
        console.print(
            Panel.fit(
                "An existing authentication session was found.",
                title="Eero Login",
                border_style="blue",
            )
        )
        reuse = Confirm.ask("Do you want to reuse the existing session?")

        if reuse:
            with cli_ctx.status("Testing existing session..."):
                try:
                    networks = await client.get_networks()
                    console.print(
                        f"[bold green]Session valid! Found {len(networks)} network(s).[/bold green]"
                    )
                    return True
                except EeroException as ex:
                    logger.debug("Session validation failed: %s", ex)
                    console.print("[yellow]Existing session invalid.[/yellow]")

    # Clear existing auth data
    await clear_all_credentials(client)

    # Start fresh login
    console.print(
        Panel.fit(
            "Please login to your Eero account.\nA verification code will be sent to you.",
            title="Eero Login",
            border_style="blue",
        )
    )

    user_identifier = Prompt.ask("Email or phone number")

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

    # Verification loop
    max_attempts = 3
    for attempt in range(max_attempts):
        verification_code = Prompt.ask("Verification code (check your email/phone)")

        with cli_ctx.status("Verifying..."):
            try:
                result = await client.verify(verification_code)
                if result:
                    console.print("[bold green]Login successful![/bold green]")

                    # Get networks and save preferred network to config
                    try:
                        networks_response = await client.get_networks()
                        data = networks_response.get("data", {})
                        network_list: list[dict[str, Any]] = []
                        if isinstance(data, list):
                            network_list = data
                        elif isinstance(data, dict):
                            network_list = data.get("networks") or data.get("data") or []

                        if network_list:
                            first_network = network_list[0]
                            net_id = first_network.get("id")
                            if not net_id and first_network.get("url"):
                                net_id = str(first_network["url"]).rstrip("/").split("/")[-1]
                            if net_id:
                                set_preferred_network(str(net_id))
                                logger.debug("Saved preferred network: %s", net_id)
                    except Exception as ex:
                        logger.debug("Could not get networks for preferred: %s", ex)

                    return True
            except EeroException as ex:
                console.print(f"[bold red]Error:[/bold red] {ex}")

        if attempt < max_attempts - 1:
            resend = Confirm.ask("Resend verification code?")
            if resend:
                with cli_ctx.status("Resending..."):
                    await resend_verification_code(client)
                    console.print("[green]Code resent![/green]")

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


@auth_group.command(name="status")
@click.option(
    "--offline",
    is_flag=True,
    help="Report stored state only; skip the live account probe (no API call)",
)
@click.option(
    "--check",
    "check_only",
    is_flag=True,
    help="Exit 3 if not authenticated or the stored session is invalid",
)
@click.pass_context
def auth_status(ctx: click.Context, offline: bool, check_only: bool) -> None:
    """Show current authentication status.

    Displays session info, authentication method, and account details. By
    default this makes one live API call (`GET /account`) to confirm the
    stored session actually works; pass --offline to skip it and report only
    what is stored locally.
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run() -> bool:
        session_token = get_session_token_override()
        if session_token is not None:
            # No file or keyring is used in this mode; report accordingly
            # regardless of what may happen to exist on disk.
            session_info = _SessionInfo(
                path=str(get_cookie_file()), present=False, schema_version=None
            )
            keyring_available = False
        else:
            session_info = _get_session_info()
            keyring_available = _check_keyring_available()

        async with build_client() as client:
            await prepare_client(client)
            is_auth = client.is_authenticated
            account_data: _AccountData | None = None
            # True: live probe confirmed the session works. False: not
            # authenticated, or the probe rejected the stored token
            # (EeroAuthenticationException/other API error). None: unknown
            # because --offline skipped the probe.
            session_valid: Optional[bool]

            if not is_auth:
                session_valid = False
            elif offline:
                session_valid = None
            else:
                try:
                    with cli_ctx.status("Getting account info..."):
                        raw_account = await client.get_account()
                except EeroException as ex:
                    logger.debug("Account probe failed: %s", ex)
                    session_valid = False
                else:
                    session_valid = True
                    # Extract data from raw response envelope
                    account = raw_account.get("data", raw_account)
                    if isinstance(account, dict):
                        # Extract account ID from URL if not directly available
                        account_id = account.get("id")
                        if not account_id and account.get("url"):
                            account_id = account["url"].rstrip("/").split("/")[-1]

                        users_list: list[_UserData] = [
                            _UserData(
                                id=u.get("id"),
                                name=u.get("name"),
                                email=u.get("email"),
                                phone=u.get("phone"),
                                role=u.get("role"),
                                created_at=(
                                    str(u.get("created_at")) if u.get("created_at") else None
                                ),
                            )
                            for u in (account.get("users") or [])
                            if isinstance(u, dict)
                        ]
                        account_data = _AccountData(
                            id=account_id,
                            name=account.get("name"),
                            premium_status=account.get("premium_status"),
                            premium_expiry=(
                                str(account.get("premium_expiry"))
                                if account.get("premium_expiry")
                                else None
                            ),
                            created_at=(
                                str(account.get("created_at"))
                                if account.get("created_at")
                                else None
                            ),
                            users=users_list,
                        )

            # Determine auth method: the *configured* method verbatim
            # ("env" under EEROCTL_SESSION_TOKEN, else get_auth_method()'s
            # "keyring"/"cookie_file"), independent of whether the keyring
            # probe actually found a record there -- that's a separate
            # fact, already carried by storage.keyring.present.
            auth_method = "env" if session_token is not None else get_auth_method()
            schema_version = session_info["schema_version"]

            if cli_ctx.is_structured_output():
                data = {
                    "authenticated": is_auth,
                    "session_valid": session_valid,
                    "auth_method": auth_method,
                    "storage": {
                        "keyring": {"present": keyring_available},
                        "cookie_file": {
                            "path": session_info["path"],
                            "present": session_info["present"],
                            "schema_version": schema_version,
                        },
                    },
                    "account": account_data,
                }
                cli_ctx.render_structured(data, "eero.auth.status/v2")

            elif cli_ctx.output_format == OutputFormat.LIST:
                # List format - parseable key-value rows
                if session_valid is True:
                    status = "valid"
                elif session_valid is None:
                    status = "stored_not_verified"
                elif is_auth:
                    status = "invalid"
                else:
                    status = "not_authenticated"
                print(f"status              {status}")
                print(f"auth_method         {auth_method}")
                print(f"cookie_file         {session_info['path']}")
                print(
                    f"schema_version      {schema_version if schema_version is not None else 'N/A'}"
                )
                print(f"keyring_available   {keyring_available}")
                if account_data:
                    print(f"account_id          {account_data['id']}")
                    print(f"account_name        {account_data['name'] or 'N/A'}")
                    print(f"premium_status      {account_data['premium_status'] or 'N/A'}")
                    print(f"premium_expiry      {account_data['premium_expiry'] or 'N/A'}")
                    for u in account_data.get("users", []):
                        print(f"user                {u['email']}  {u['role']}  {u['name'] or ''}")

            else:
                # Table format - Rich tables
                # Session info table
                session_table = Table(title="Session Information")
                session_table.add_column("Property", style="cyan")
                session_table.add_column("Value")

                if session_valid is True:
                    status_display = "[green]Valid[/green]"
                elif session_valid is None:
                    status_display = "[blue]Stored, not verified[/blue]"
                elif is_auth:
                    status_display = "[yellow]Invalid[/yellow]"
                else:
                    status_display = "[red]Not authenticated[/red]"

                session_table.add_row("Status", status_display)
                session_table.add_row("Auth Method", f"[blue]{auth_method}[/blue]")
                session_table.add_row(
                    "Credential Schema",
                    str(schema_version) if schema_version is not None else "N/A",
                )
                session_table.add_row(
                    "Keyring Available",
                    "[green]Yes[/green]" if keyring_available else "[dim]No[/dim]",
                )
                session_table.add_row("Cookie File", session_info["path"])

                console.print(session_table)

                # Account info table (only if we got account data)
                if account_data:
                    console.print()
                    account_table = Table(title="Account Information")
                    account_table.add_column("Property", style="cyan")
                    account_table.add_column("Value")

                    account_table.add_row("Account ID", account_data["id"])
                    account_table.add_row("Account Name", account_data["name"] or "N/A")
                    premium = account_data["premium_status"] or "N/A"
                    if premium and "active" in premium.lower():
                        premium = f"[green]{premium}[/green]"
                    account_table.add_row("Premium Status", premium)
                    account_table.add_row("Premium Expiry", account_data["premium_expiry"] or "N/A")
                    account_table.add_row("Created", account_data["created_at"] or "N/A")

                    console.print(account_table)

                    # Users table
                    if account_data.get("users"):
                        console.print()
                        users_table = Table(title="Account Users")
                        users_table.add_column("Email", style="cyan")
                        users_table.add_column("Name")
                        users_table.add_column("Role", style="magenta")

                        for u in account_data["users"]:
                            users_table.add_row(u["email"], u["name"] or "", u["role"])

                        console.print(users_table)
                elif session_valid is not True:
                    console.print()
                    console.print("[yellow]Run `eero auth login` to authenticate.[/yellow]")

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
