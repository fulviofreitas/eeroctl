"""Utility functions for the Eero CLI."""

import asyncio
import functools
import json
import os
import sys
from pathlib import Path
from typing import Awaitable, Callable, Optional, TypeVar

import click
from eero import EeroClient
from eero.exceptions import EeroAuthenticationException
from rich.console import Console

# Create console for rich output
console = Console()

T = TypeVar("T")


def with_client(func: Callable[..., Awaitable[T]]) -> Callable[..., T]:
    """Decorator that provides an EeroClient to async Click commands.

    This decorator eliminates the repetitive boilerplate pattern of:
        async def run_cmd():
            async def inner(client):
                ...
            await run_with_client(inner)
        asyncio.run(run_cmd())

    Instead, you can write:
        @command.command()
        @click.pass_context
        @with_client
        async def my_command(ctx, client, ...):
            # Just do the work

    The decorator:
    - Creates an EeroClient context
    - Handles authentication errors
    - Runs the async function synchronously via asyncio.run()

    Args:
        func: Async function that receives (ctx, client, *args, **kwargs)

    Returns:
        Synchronous wrapper function
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        async def run():
            cookie_file = get_cookie_file()
            use_keyring = get_use_keyring()
            try:
                async with EeroClient(
                    cookie_file=str(cookie_file),
                    use_keyring=use_keyring,
                ) as client:
                    return await func(*args, client=client, **kwargs)
            except EeroAuthenticationException:
                console.print("[bold red]Not authenticated[/bold red]")
                console.print("Please login first: [bold]eero auth login[/bold]")
                sys.exit(3)  # ExitCode.AUTH_REQUIRED

        return asyncio.run(run())

    return wrapper


def output_option(func):
    """Decorator to add --output option to commands."""
    return click.option(
        "--output",
        type=click.Choice(["brief", "extensive", "json"]),
        default="brief",
        help="Output format (brief, extensive, or json)",
    )(func)


def get_config_dir() -> Path:
    """Get the configuration directory.

    Returns:
        Path to the configuration directory
    """
    if os.name == "nt":  # Windows
        config_dir = Path(os.environ["APPDATA"]) / "eeroctl"
    else:
        config_dir = Path.home() / ".config" / "eeroctl"

    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_cookie_file() -> Path:
    """Get the cookie file path.

    Returns:
        Path to the cookie file
    """
    return get_config_dir() / "cookies.json"


def get_config_file() -> Path:
    """Get the config file path.

    Returns:
        Path to the config file
    """
    return get_config_dir() / "config.json"


def set_preferred_network(network_id: str) -> None:
    """Set the preferred network ID in the configuration.

    Args:
        network_id: The network ID to set as preferred
    """
    config_file = get_config_file()
    config = {}

    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    config["preferred_network_id"] = network_id

    try:
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
    except IOError as e:
        console.print(f"[bold red]Error saving config: {e}[/bold red]")


def get_preferred_network() -> Optional[str]:
    """Get the preferred network ID from the configuration.

    Returns:
        The preferred network ID or None if not set
    """
    config_file = get_config_file()

    if not config_file.exists():
        return None

    try:
        with open(config_file, "r") as f:
            config = json.load(f)
        return config.get("preferred_network_id")
    except (json.JSONDecodeError, IOError):
        return None


def set_use_keyring(use_keyring: bool) -> None:
    """Set the use_keyring preference in the configuration.

    Args:
        use_keyring: Whether to use keyring for credential storage
    """
    config_file = get_config_file()
    config = {}

    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    config["use_keyring"] = use_keyring

    try:
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
    except IOError as e:
        console.print(f"[bold red]Error saving config: {e}[/bold red]")


def get_use_keyring() -> bool:
    """Get the use_keyring preference from the configuration.

    Returns:
        True if keyring should be used, False otherwise.
        Defaults to True if not set.
    """
    config_file = get_config_file()

    if not config_file.exists():
        return True  # Default to using keyring

    try:
        with open(config_file, "r") as f:
            config = json.load(f)
        # Default to True if not explicitly set
        return config.get("use_keyring", True)
    except (json.JSONDecodeError, IOError):
        return True


async def run_with_client(func):
    """Run a function with an EeroClient instance.

    Respects the use_keyring preference saved during login.

    Args:
        func: Async function that takes an EeroClient as argument
    """
    cookie_file = get_cookie_file()
    use_keyring = get_use_keyring()

    try:
        async with EeroClient(
            cookie_file=str(cookie_file),
            use_keyring=use_keyring,
        ) as client:
            await func(client)
    except EeroAuthenticationException:
        console.print("[bold red]Not authenticated[/bold red]")
        console.print("Please login first: [bold]eero auth login[/bold]")
        raise SystemExit(1)


def confirm_action(message: str) -> bool:
    """Ask user to confirm an action.

    Args:
        message: The message to display

    Returns:
        True if user confirms, False otherwise
    """
    return click.confirm(message)
