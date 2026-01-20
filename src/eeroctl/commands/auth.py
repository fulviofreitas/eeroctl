"""Authentication commands for the Eero CLI.

Commands:
- eero auth login: Start authentication flow
- eero auth logout: End current session
- eero auth clear: Clear all stored credentials
- eero auth status: Show authentication status
"""

import asyncio
import json
import os
import sys
from typing import TypedDict

import click
from eero import EeroClient
from eero.exceptions import EeroAuthenticationException, EeroException
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from ..context import EeroCliContext, ensure_cli_context, get_cli_context
from ..exit_codes import ExitCode
from ..output import OutputFormat
from ..utils import get_cookie_file


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
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run() -> None:
        async with EeroClient(
            cookie_file=str(get_cookie_file()),
            use_keyring=not no_keyring,
        ) as client:
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

    try:
        asyncio.run(run())
    except EeroAuthenticationException as e:
        cli_ctx.renderer.render_error(str(e))
        sys.exit(ExitCode.AUTH_REQUIRED)
    except EeroException as e:
        cli_ctx.renderer.render_error(str(e))
        sys.exit(ExitCode.GENERIC_ERROR)


async def _interactive_login(
    client: EeroClient, force: bool, console, cli_ctx: EeroCliContext
) -> bool:
    """Interactive login process."""
    cookie_file = get_cookie_file()

    # Check for existing session
    if os.path.exists(cookie_file) and not force:
        try:
            with open(cookie_file, "r") as f:
                cookies = json.load(f)
                if cookies.get("user_token") and cookies.get("session_id"):
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
                                    f"[bold green]Session valid! "
                                    f"Found {len(networks)} network(s).[/bold green]"
                                )
                                return True
                            except Exception:
                                console.print("[yellow]Existing session invalid.[/yellow]")
        except Exception:
            pass

    # Clear existing auth data
    await client._api.auth.clear_auth_data()

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
            if not result:
                console.print("[bold red]Failed to request verification code[/bold red]")
                return False
            console.print("[bold green]Verification code sent![/bold green]")
        except EeroException as ex:
            console.print(f"[bold red]Error:[/bold red] {ex}")
            return False

    # Verification loop
    max_attempts = 3
    for attempt in range(max_attempts):
        verification_code = Prompt.ask("Verification code (check your email/phone)")

        with cli_ctx.status("Verifying..."):
            try:
                result = await client.verify(verification_code)
                if result:
                    console.print("[bold green]Login successful![/bold green]")
                    return True
            except EeroException as ex:
                console.print(f"[bold red]Error:[/bold red] {ex}")

        if attempt < max_attempts - 1:
            resend = Confirm.ask("Resend verification code?")
            if resend:
                with cli_ctx.status("Resending..."):
                    await client._api.auth.resend_verification_code()
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

    async def run() -> None:
        async with EeroClient(cookie_file=str(get_cookie_file())) as client:
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

    asyncio.run(run())


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
        async with EeroClient(cookie_file=str(get_cookie_file())) as client:
            await client._api.auth.clear_auth_data()
            console.print("[bold green]Authentication data cleared[/bold green]")

    asyncio.run(run())


def _get_session_info() -> dict:
    """Read session info from cookie file."""
    from datetime import datetime

    cookie_file = get_cookie_file()
    session_info = {
        "cookie_file": str(cookie_file),
        "cookie_exists": cookie_file.exists(),
        "session_expiry": None,
        "session_expired": True,  # Default to expired
        "has_token": False,
        "preferred_network_id": None,
    }

    if cookie_file.exists():
        try:
            with open(cookie_file, "r") as f:
                data = json.load(f)
            session_info["session_expiry"] = data.get("session_expiry")
            session_info["preferred_network_id"] = data.get("preferred_network_id")
            session_info["has_token"] = bool(data.get("user_token"))

            # Check if session is expired based on expiry date
            expiry_str = data.get("session_expiry")
            if expiry_str:
                try:
                    expiry = datetime.fromisoformat(expiry_str)
                    session_info["session_expired"] = datetime.now() > expiry
                except ValueError:
                    pass
        except Exception:
            pass

    return session_info


def _check_keyring_available() -> bool:
    """Check if keyring is available and has eero credentials."""
    try:
        import keyring

        token = keyring.get_password("eero", "user_token")
        return token is not None
    except Exception:
        return False


@auth_group.command(name="status")
@click.pass_context
def auth_status(ctx: click.Context) -> None:
    """Show current authentication status.

    Displays session info, authentication method, and account details.
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    async def run() -> None:
        cookie_file = get_cookie_file()
        session_info = _get_session_info()
        keyring_available = _check_keyring_available()

        async with EeroClient(cookie_file=str(cookie_file)) as client:
            is_auth = client.is_authenticated
            account_data: _AccountData | None = None

            # Determine session validity based on expiry date, not API call
            # (API call may fail due to network issues, not expired session)
            session_valid = (
                is_auth and session_info["has_token"] and not session_info["session_expired"]
            )

            # Try to get account info if we have a valid session
            if session_valid:
                try:
                    with cli_ctx.status("Getting account info..."):
                        account = await client.get_account()
                    users_list: list[_UserData] = [
                        _UserData(
                            id=u.id,
                            name=u.name,
                            email=u.email,
                            phone=u.phone,
                            role=u.role,
                            created_at=str(u.created_at) if u.created_at else None,
                        )
                        for u in (account.users or [])
                    ]
                    account_data = _AccountData(
                        id=account.id,
                        name=account.name,
                        premium_status=account.premium_status,
                        premium_expiry=(
                            str(account.premium_expiry) if account.premium_expiry else None
                        ),
                        created_at=str(account.created_at) if account.created_at else None,
                        users=users_list,
                    )
                except Exception:
                    # API call failed but session may still be valid per expiry date
                    pass

            # Determine auth method
            auth_method = "keyring" if keyring_available else "cookie"

            if cli_ctx.is_structured_output():
                data = {
                    "authenticated": is_auth,
                    "session_valid": session_valid,
                    "auth_method": auth_method,
                    "session": {
                        "cookie_file": session_info["cookie_file"],
                        "expiry": session_info["session_expiry"],
                        "preferred_network_id": session_info["preferred_network_id"],
                    },
                    "keyring_available": keyring_available,
                    "account": account_data,
                }
                cli_ctx.render_structured(data, "eero.auth.status/v1")

            elif cli_ctx.output_format == OutputFormat.LIST:
                # List format - parseable key-value rows
                status = (
                    "valid" if session_valid else ("expired" if is_auth else "not_authenticated")
                )
                print(f"status              {status}")
                print(f"auth_method         {auth_method}")
                print(f"cookie_file         {session_info['cookie_file']}")
                print(f"session_expiry      {session_info['session_expiry'] or 'N/A'}")
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

                if session_valid:
                    status_display = "[green]Valid[/green]"
                elif is_auth and session_info["session_expired"]:
                    status_display = "[yellow]Expired[/yellow]"
                else:
                    status_display = "[red]Not Authenticated[/red]"

                session_table.add_row("Status", status_display)
                session_table.add_row("Auth Method", f"[blue]{auth_method}[/blue]")
                session_table.add_row("Cookie File", session_info["cookie_file"])
                session_table.add_row("Session Expiry", session_info["session_expiry"] or "N/A")
                session_table.add_row(
                    "Keyring Available",
                    "[green]Yes[/green]" if keyring_available else "[dim]No[/dim]",
                )

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
                elif not session_valid:
                    console.print()
                    console.print("[yellow]Run `eero auth login` to authenticate.[/yellow]")

    asyncio.run(run())
