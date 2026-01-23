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


# ==================== Config Defaults ====================

# Default configuration values
DEFAULT_CONFIG = {
    "default_output": "table",
    "auth_method": "keyring",
    "preferred_network_id": None,
}

# Valid values for config options
VALID_OUTPUT_FORMATS = ("table", "list", "json", "yaml", "text")
VALID_AUTH_METHODS = ("keyring", "cookie_file")


def ensure_config() -> dict:
    """Ensure config file exists with default values.

    Creates the config file with defaults if it doesn't exist.
    Returns the current config.

    Returns:
        The current configuration dictionary
    """
    config_file = get_config_file()

    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
            # Merge with defaults for any missing keys
            updated = False
            for key, default_value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = default_value
                    updated = True
            if updated:
                with open(config_file, "w") as f:
                    json.dump(config, f, indent=2)
            return config
        except (json.JSONDecodeError, IOError):
            pass

    # Create new config with defaults
    config = DEFAULT_CONFIG.copy()
    try:
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
    except IOError as e:
        console.print(f"[bold red]Error creating config: {e}[/bold red]")

    return config


def _load_config() -> dict:
    """Load config from file, returning defaults if not exists."""
    config_file = get_config_file()

    if not config_file.exists():
        return DEFAULT_CONFIG.copy()

    try:
        with open(config_file, "r") as f:
            config = json.load(f)
        # Merge with defaults for any missing keys
        result = DEFAULT_CONFIG.copy()
        result.update(config)
        return result
    except (json.JSONDecodeError, IOError):
        return DEFAULT_CONFIG.copy()


def _save_config(config: dict) -> None:
    """Save config to file."""
    config_file = get_config_file()
    try:
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
    except IOError as e:
        console.print(f"[bold red]Error saving config: {e}[/bold red]")


# ==================== Preferred Network ====================


def set_preferred_network(network_id: str) -> None:
    """Set the preferred network ID in the configuration.

    Args:
        network_id: The network ID to set as preferred
    """
    config = _load_config()
    config["preferred_network_id"] = network_id
    _save_config(config)


def get_preferred_network() -> Optional[str]:
    """Get the preferred network ID from the configuration.

    Returns:
        The preferred network ID or None if not set
    """
    config = _load_config()
    return config.get("preferred_network_id")


# ==================== Auth Method ====================


def set_auth_method(method: str) -> None:
    """Set the authentication method in the configuration.

    Args:
        method: Authentication method ('keyring' or 'cookie_file')
    """
    if method not in VALID_AUTH_METHODS:
        raise ValueError(f"Invalid auth method: {method}. Must be one of {VALID_AUTH_METHODS}")
    config = _load_config()
    config["auth_method"] = method
    _save_config(config)


def get_auth_method() -> str:
    """Get the authentication method from the configuration.

    Returns:
        The authentication method ('keyring' or 'cookie_file').
        Defaults to 'keyring' if not set.
    """
    config = _load_config()
    return config.get("auth_method", "keyring")


# Legacy compatibility
def set_use_keyring(use_keyring: bool) -> None:
    """Set the auth method based on keyring preference (legacy).

    Args:
        use_keyring: Whether to use keyring for credential storage
    """
    set_auth_method("keyring" if use_keyring else "cookie_file")


def get_use_keyring() -> bool:
    """Get whether keyring should be used (legacy).

    Returns:
        True if keyring should be used, False otherwise.
    """
    return get_auth_method() == "keyring"


# ==================== Default Output ====================


def set_default_output(output_format: str) -> None:
    """Set the default output format in the configuration.

    Args:
        output_format: Output format ('table', 'list', 'json', 'yaml', 'text')
    """
    if output_format not in VALID_OUTPUT_FORMATS:
        raise ValueError(
            f"Invalid output format: {output_format}. Must be one of {VALID_OUTPUT_FORMATS}"
        )
    config = _load_config()
    config["default_output"] = output_format
    _save_config(config)


def get_default_output() -> str:
    """Get the default output format from the configuration.

    Returns:
        The default output format. Defaults to 'table' if not set.
    """
    config = _load_config()
    return config.get("default_output", "table")


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
