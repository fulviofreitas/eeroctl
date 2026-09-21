"""Utility functions for the Eero CLI."""

import asyncio
import functools
import json
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Awaitable, Callable, Optional, TypeVar

import click
from eero import EeroClient
from eero.exceptions import EeroAuthenticationException, EeroException
from rich.console import Console

if TYPE_CHECKING:
    from .context import EeroCliContext

# Create console for rich output
console = Console()

logger = logging.getLogger("eeroctl")

T = TypeVar("T")


def backup_legacy_cookie_file(cookie_file: Path) -> Optional[Path]:
    """Back up a pre-v8 (schema 1) credential file before the SDK migrates it.

    eero-api 8 rewrites a schema-1 record to schema 2 on first load, and in
    keyring mode ``ChainedStorage`` promotes the token into the keyring and
    then **deletes** the cookie file entirely (v8 migration plan §8.2, §2.1;
    ``CREDENTIAL_SCHEMA_VERSION`` at ``eero/const.py:86``). Backing up the
    pre-migration file once means a rollback to a 7.x release does not lose
    the stored session.

    No-op, and never raises, when:
        - the file does not exist, or is a directory;
        - the file's content is not valid JSON (or not a JSON object);
        - the parsed record already has a ``schema_version`` key (already
          schema 2+, nothing to protect);
        - a backup already exists at ``<cookie_file>.pre-v8.bak`` (the
          ``O_EXCL`` open fails) -- this makes the function idempotent.

    Only ever touches the exact path passed in; never globs or otherwise
    matches the SDK's own ``.cookies.json.<random>.tmp`` temp files
    (``FileStorage.save``, eero-api 8.0.1).

    Args:
        cookie_file: The exact cookie file path eeroctl is about to hand to
            the SDK.

    Returns:
        The backup file's path if a backup was written this call, else
        ``None``.
    """
    try:
        if not cookie_file.is_file():
            return None
        raw = cookie_file.read_text()
        data = json.loads(raw)
    except (OSError, ValueError):
        return None

    if not isinstance(data, dict) or "schema_version" in data:
        return None

    backup_path = cookie_file.with_name(cookie_file.name + ".pre-v8.bak")
    try:
        fd = os.open(str(backup_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError:
        # Either a backup already exists (O_EXCL) or the directory isn't
        # writable; a failed backup must never block client construction.
        return None

    try:
        with os.fdopen(fd, "w") as f:
            f.write(raw)
    except OSError:
        return None

    # Log the path only -- never the token, which the raw content may carry.
    logger.info("Backed up pre-v8 credential file to %s", backup_path)
    return backup_path


def build_client(
    cli_ctx: Optional["EeroCliContext"] = None,
    *,
    use_keyring: Optional[bool] = None,
    cookie_file: Optional[Path] = None,
) -> EeroClient:
    """Build an EeroClient. The single construction site for the whole CLI.

    Every command that needs an :class:`~eero.EeroClient` goes through this
    function instead of instantiating the class directly, so there is one
    place to change when the client gains new constructor options (see the
    v8 migration plan, §3.4). All private-SDK access (``client._api...``)
    lives in :mod:`eeroctl.sdk_private`, never here or in a command module.

    Args:
        cli_ctx: The active CLI context. Not yet used to influence
            construction; accepted now so callers do not need to change
            again when a later commit plumbs constructor overrides
            (``send_legacy_cookie``, ``accept_language``, ``get_retries``)
            through it.
        use_keyring: Overrides the saved auth-method preference for this
            construction only (e.g. an in-flight ``--no-keyring`` flag that
            has not been persisted yet). Defaults to ``get_use_keyring()``.
        cookie_file: Overrides the configured cookie file path for this
            construction only. Defaults to ``get_cookie_file()``. Skips the
            pre-v8 backup entirely when explicitly ``None`` (the future
            ephemeral ``EEROCTL_SESSION_TOKEN`` mode, which passes no file
            backend to the SDK at all).

    Returns:
        A configured, un-entered :class:`~eero.EeroClient`. Callers use it
        as an async context manager, e.g. ``async with build_client() as
        client:``.
    """
    del cli_ctx  # Reserved for a later commit; unused today.
    resolved_cookie_file = cookie_file if cookie_file is not None else get_cookie_file()
    resolved_use_keyring = use_keyring if use_keyring is not None else get_use_keyring()
    if resolved_cookie_file is not None:
        # Runs for both auth methods: keyring mode still reads the file via
        # SDK ChainedStorage on first load, promotes it, and deletes it.
        backup_legacy_cookie_file(resolved_cookie_file)
    return EeroClient(
        cookie_file=str(resolved_cookie_file) if resolved_cookie_file is not None else None,
        use_keyring=resolved_use_keyring,
    )


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
            try:
                async with build_client() as client:
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


async def run_with_client(func, cli_ctx: Optional["EeroCliContext"] = None):
    """Run a function with an EeroClient instance.

    Respects the use_keyring preference saved during login.

    Any SDK exception that escapes *func* is translated to a user-facing message
    and the exit code that :func:`~eeroctl.errors.handle_cli_error` maps it to.
    Commands with their own handling are unaffected: their handlers run first,
    and only what they re-raise reaches this one.

    Args:
        func: Async function that takes an EeroClient as argument
        cli_ctx: The active CLI context, forwarded to :func:`build_client`.
            Optional so existing callers do not need to change; a later
            commit will start passing it.

    Raises:
        SystemExit: With the mapped exit code when an SDK exception escapes.
    """
    try:
        async with build_client(cli_ctx) as client:
            await func(client)
    except EeroAuthenticationException:
        console.print("[bold red]Not authenticated[/bold red]")
        console.print("Please login first: [bold]eero auth login[/bold]")
        raise SystemExit(1)
    except EeroException as e:
        # Deliberately not `except Exception`: a bare catch would swallow the
        # SystemExit that commands raise via sys.exit() inside the coroutine,
        # and would mask genuine bugs as tidy CLI errors.
        from .errors import handle_cli_error

        raise SystemExit(handle_cli_error(e, console))


def confirm_action(message: str) -> bool:
    """Ask user to confirm an action.

    Args:
        message: The message to display

    Returns:
        True if user confirms, False otherwise
    """
    return click.confirm(message)
