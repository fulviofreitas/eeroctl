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

import click
from eero import EeroClient
from eero.exceptions import EeroAuthenticationException, EeroException
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from ..context import EeroCliContext, ensure_cli_context, get_cli_context
from ..exit_codes import ExitCode
from ..utils import get_cookie_file


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
                    console.print(
                        "[yellow]Session expired. Starting new login...[/yellow]"
                    )

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
            "Please login to your Eero account.\n" "A verification code will be sent to you.",
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


@auth_group.command(name="status")
@click.pass_context
def auth_status(ctx: click.Context) -> None:
    """Show current authentication status.

    Displays whether you are currently authenticated and
    shows basic account information if available.
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run() -> None:
        async with EeroClient(cookie_file=str(get_cookie_file())) as client:
            is_auth = client.is_authenticated

            if cli_ctx.is_json_output():
                data = {
                    "authenticated": is_auth,
                    "session_valid": False,
                    "networks": [],
                }

                if is_auth:
                    try:
                        networks = await client.get_networks()
                        data["session_valid"] = True
                        data["networks"] = [{"id": n.id, "name": n.name} for n in networks]
                    except Exception:
                        pass

                renderer.render_json(data, "eero.auth.status/v1")
            else:
                if is_auth:
                    try:
                        with cli_ctx.status("Checking session..."):
                            networks = await client.get_networks()

                        content = (
                            "[bold]Status:[/bold] [green]Authenticated[/green]\n"
                            f"[bold]Networks:[/bold] {len(networks)}"
                        )
                        for net in networks:
                            content += f"\n  • {net.name} ({net.id})"

                        console.print(
                            Panel(content, title="Authentication Status", border_style="green")
                        )
                    except Exception:
                        console.print(
                            Panel(
                                "[bold]Status:[/bold] [yellow]Session Expired[/yellow]\n"
                                "Run `eero auth login` to authenticate.",
                                title="Authentication Status",
                                border_style="yellow",
                            )
                        )
                else:
                    console.print(
                        Panel(
                            "[bold]Status:[/bold] [red]Not Authenticated[/red]\n"
                            "Run `eero auth login` to authenticate.",
                            title="Authentication Status",
                            border_style="red",
                        )
                    )

    asyncio.run(run())
