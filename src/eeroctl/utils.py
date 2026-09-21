"""Utility functions for the Eero CLI."""

import asyncio
import functools
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional, TypeVar

import click
from eero import EeroClient
from eero.exceptions import EeroAuthenticationException, EeroException, EeroValidationException
from rich.console import Console

from .context import EeroCliContext
from .exit_codes import ExitCode

# Create console for rich output
console = Console()

logger = logging.getLogger("eeroctl")

T = TypeVar("T")


def looks_like_sdk_reference(value: str) -> bool:
    """Return True when `value` should be handed to an id-validated SDK
    method verbatim, rather than resolved locally by listing and matching.

    Per migration plan §2.5 decision 2, eeroctl never pre-validates ids,
    paths or URLs -- it hands them to the SDK unchanged and lets
    ``EeroValidationException`` (from the SDK's own ``_IDENTIFIER_RE``,
    ``eero/api/links.py:47,65-66``, and ``_require_nested_family``,
    ``eero/api/_params.py:171-216``) map to exit 2 via
    ``handle_cli_error``, *before* any request. This helper only decides
    which resolution path a command takes; it performs no validation of its
    own.

    A value "looks like" an id/path/URL the SDK should see directly when:

    - it starts with ``/``, ``http://`` or ``https://`` (a host-relative
      path or absolute URL, per ``resource_url``'s three branches,
      ``links.py:223-276``); or
    - it contains any of ``/ ? # { }`` -- a bare
      ``_IDENTIFIER_RE``-validated id can never contain these, so their
      presence means either a path/URL shape or a string the SDK is
      guaranteed to reject (e.g. ``"a/b"``, ``"x?y=1"``, ``"{x}"``); or
    - it is the empty string -- never a valid name/serial/MAC to resolve
      locally, and the one corpus case (``""``) not already covered by the
      character check above; the SDK rejects it the same way (empty does
      not match ``_IDENTIFIER_RE``).

    Everything else (plain names, serials, MAC addresses like
    ``"aabbccddeeff"``, bare numeric ids) returns False and keeps going
    through the existing list-and-match resolvers -- names must keep
    working exactly as before.
    """
    if not isinstance(value, str):
        return False
    if value == "":
        return True
    if value.startswith(("/", "http://", "https://")):
        return True
    return any(ch in value for ch in "/?#{}")


def get_session_token_override() -> Optional[str]:
    """Return the ``EEROCTL_SESSION_TOKEN`` value, or ``None`` if unset/empty.

    When set, eeroctl builds an ephemeral, in-memory session (SDK
    ``MemoryStorage``, via ``cookie_file=None, use_keyring=False``) instead
    of touching disk or the keyring at all -- v8 migration plan §3.4, Q6.
    """
    token = os.environ.get("EEROCTL_SESSION_TOKEN")
    return token if token else None


async def prepare_client(client: EeroClient) -> None:
    """Apply ``EEROCTL_SESSION_TOKEN`` to an already-entered client, if set.

    Must run *after* ``async with client:`` (``__aenter__`` opens the
    aiohttp session -- v8.0.1 ``client.py:99-101``), so every call site that
    builds a client via :func:`build_client` calls this immediately after
    entering the context manager, before running command logic.

    ``EeroClient.set_session_token`` is async (v8.0.1 ``client.py:362``:
    ``async def set_session_token(self, token: str) -> None``), which is
    why this cannot live inside :func:`build_client` itself (a sync
    function that returns an un-entered client).

    Never logs or echoes the token. A malformed value raises
    ``EeroValidationException`` (v8.0.1 ``api/auth.py:530-532``, printable
    ASCII / no CR-LF), which callers must let propagate: ``with_client``
    and ``run_with_client`` both map it to exit 2 via the existing error
    handling.

    Args:
        client: An entered (``__aenter__``-ed) :class:`~eero.EeroClient`.
    """
    token = get_session_token_override()
    if token is not None:
        await client.set_session_token(token)


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


def _resolve_cli_ctx(cli_ctx: Optional[EeroCliContext]) -> Optional[EeroCliContext]:
    """Resolve the active CLI context when the caller didn't pass one.

    Most ``run_with_client`` call sites across the command modules predate
    the ``cli_ctx`` parameter; touching every one of them is out of scope
    for this commit. Falling back to Click's own current context (which
    already carries the ``EeroCliContext`` as ``ctx.obj``) means those
    call sites still pick up ``accept_language``/``get_retries``/
    ``send_legacy_cookie`` without any change.
    """
    if cli_ctx is not None:
        return cli_ctx
    click_ctx = click.get_current_context(silent=True)
    if click_ctx is None:
        return None
    obj = click_ctx.obj
    return obj if isinstance(obj, EeroCliContext) else None


def build_client(
    cli_ctx: Optional[EeroCliContext] = None,
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

    When ``EEROCTL_SESSION_TOKEN`` is set (see
    :func:`get_session_token_override`), this always builds an ephemeral,
    in-memory client (``cookie_file=None, use_keyring=False`` -> SDK
    ``MemoryStorage``) regardless of *use_keyring*/*cookie_file*: the
    pre-v8 backup is skipped too, since it never touches disk. Callers must
    still call :func:`prepare_client` after entering the client to actually
    apply the token (see that function's docstring for why).

    Args:
        cli_ctx: The active CLI context. When ``None``, resolved via
            :func:`_resolve_cli_ctx` (Click's current context) so callers
            that cannot cheaply thread it through still get the right
            ``accept_language``/``get_retries``/``send_legacy_cookie``.
        use_keyring: Overrides the saved auth-method preference for this
            construction only (e.g. an in-flight ``--no-keyring`` flag that
            has not been persisted yet). Defaults to ``get_use_keyring()``.
            Ignored under ``EEROCTL_SESSION_TOKEN``.
        cookie_file: Overrides the configured cookie file path for this
            construction only. Defaults to ``get_cookie_file()``. Skips the
            pre-v8 backup entirely when explicitly ``None``. Ignored under
            ``EEROCTL_SESSION_TOKEN``.

    Returns:
        A configured, un-entered :class:`~eero.EeroClient`. Callers use it
        as an async context manager, e.g. ``async with build_client() as
        client:``.
    """
    resolved_cli_ctx = _resolve_cli_ctx(cli_ctx)

    if get_session_token_override() is not None:
        resolved_cookie_file: Optional[Path] = None
        resolved_use_keyring = False
    else:
        resolved_cookie_file = cookie_file if cookie_file is not None else get_cookie_file()
        resolved_use_keyring = use_keyring if use_keyring is not None else get_use_keyring()
        if resolved_cookie_file is not None:
            # Runs for both auth methods: keyring mode still reads the file
            # via SDK ChainedStorage on first load, promotes it, and
            # deletes it.
            backup_legacy_cookie_file(resolved_cookie_file)

    accept_language = (
        resolved_cli_ctx.accept_language if resolved_cli_ctx is not None else get_accept_language()
    )
    get_retries = (
        resolved_cli_ctx.get_retries if resolved_cli_ctx is not None else get_get_retries()
    )
    send_legacy_cookie = (
        resolved_cli_ctx.send_legacy_cookie
        if resolved_cli_ctx is not None
        else get_send_legacy_cookie()
    )

    return EeroClient(
        cookie_file=str(resolved_cookie_file) if resolved_cookie_file is not None else None,
        use_keyring=resolved_use_keyring,
        accept_language=accept_language,
        get_retries=get_retries,
        send_legacy_cookie=send_legacy_cookie,
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
                    await prepare_client(client)
                    return await func(*args, client=client, **kwargs)
            except EeroAuthenticationException:
                console.print("[bold red]Not authenticated[/bold red]")
                console.print("Please login first: [bold]eero auth login[/bold]")
                sys.exit(3)  # ExitCode.AUTH_REQUIRED
            except EeroValidationException as e:
                # A malformed EEROCTL_SESSION_TOKEN surfaces here from
                # prepare_client(); route it through the same mapping
                # run_with_client uses so it exits 2, not an unhandled
                # traceback.
                from .errors import handle_cli_error

                sys.exit(handle_cli_error(e, console))

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

    ``EEROCTL_CONFIG_DIR``, when set, overrides both the POSIX and Windows
    defaults below (v8 migration plan §3.4, Q6).

    Returns:
        Path to the configuration directory
    """
    override = os.environ.get("EEROCTL_CONFIG_DIR")
    if override:
        config_dir = Path(override).expanduser()
    elif os.name == "nt":  # Windows
        config_dir = Path(os.environ["APPDATA"]) / "eeroctl"
    else:
        config_dir = Path.home() / ".config" / "eeroctl"

    # 0o700: the directory holds cookies.json (a bearer token) and its
    # pre-v8 backup. mkdir's mode only applies to a newly created
    # directory (subject to umask); chmod it explicitly too, so a
    # directory that already existed with looser permissions is tightened
    # on every run. Never fatal: an unowned or read-only parent must not
    # block the CLI from working.
    config_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(config_dir, 0o700)
    except OSError:
        pass

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
    "accept_language": "en-US",
    "get_retries": 0,
    "send_legacy_cookie": True,
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


# ==================== EeroClient Constructor Options ====================


def get_accept_language() -> str:
    """Get the configured `Accept-Language` value for the SDK client.

    Returns:
        The configured value. Defaults to ``"en-US"`` if not set.
    """
    config = _load_config()
    return config.get("accept_language", "en-US")


def get_get_retries() -> int:
    """Get the configured number of extra GET-only retry attempts.

    Returns:
        The configured value. Defaults to ``0`` if not set.
    """
    config = _load_config()
    return config.get("get_retries", 0)


def get_send_legacy_cookie() -> bool:
    """Get whether the SDK should also send the legacy `s=` session cookie.

    Returns:
        The configured value. Defaults to ``True`` if not set.
    """
    config = _load_config()
    return config.get("send_legacy_cookie", True)


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


async def run_with_client(func, cli_ctx: Optional[EeroCliContext] = None):
    """Run a function with an EeroClient instance.

    Respects the use_keyring preference saved during login.

    Any SDK exception that escapes *func* is translated to a user-facing message
    and the exit code that :func:`~eeroctl.errors.handle_cli_error` maps it to.
    Commands with their own handling are unaffected: their handlers run first,
    and only what they re-raise reaches this one.

    Args:
        func: Async function that takes an EeroClient as argument
        cli_ctx: The active CLI context, forwarded to :func:`build_client`.
            Optional: when omitted, ``build_client`` resolves it from
            Click's current context instead (see ``_resolve_cli_ctx``), so
            existing callers do not need to change.

    Raises:
        SystemExit: With the mapped exit code when an SDK exception escapes.
    """
    try:
        async with build_client(cli_ctx) as client:
            await prepare_client(client)
            await func(client)
    except EeroAuthenticationException:
        console.print("[bold red]Not authenticated[/bold red]")
        console.print("Please login first: [bold]eero auth login[/bold]")
        raise SystemExit(ExitCode.AUTH_REQUIRED)
    except EeroException as e:
        # Deliberately not `except Exception`: a bare catch would swallow the
        # SystemExit that commands raise via sys.exit() inside the coroutine,
        # and would mask genuine bugs as tidy CLI errors.
        from .errors import handle_cli_error

        raise SystemExit(handle_cli_error(e, console))


def _write_accepted(result: Any) -> bool:
    """Classify a write's response as accepted or not.

    Per the migration plan (§3.2 item 4), a write is treated as *accepted*
    -- not settled, the SDK never guarantees that -- when either:

    - the response is ``None`` or not a ``{"meta": ..., "data": ...}``
      envelope at all (some facade calls return the parsed body directly),
      or
    - it is an envelope whose ``meta.code`` is a 2xx status.

    Anything else (an envelope with a missing or non-2xx ``meta.code``) is
    not accepted.

    Args:
        result: The raw return value of the write coroutine.

    Returns:
        True if the write should be reported as accepted.
    """
    if result is None or not isinstance(result, dict):
        return True
    meta = result.get("meta")
    code = meta.get("code") if isinstance(meta, dict) else None
    return isinstance(code, int) and 200 <= code < 300


async def write_if_changed(
    read: Callable[[], Awaitable[T]],
    desired: T,
    write: Callable[[], Awaitable[Any]],
    *,
    compare: Optional[Callable[[T, T], bool]] = None,
    force: bool = False,
    console: Optional[Console] = None,
    read_command: str = "",
) -> bool:
    """Read-first, skip-unchanged, write-once helper for toggle-shaped writes.

    Generalises the pattern ``commands/network/dns.py`` already used for
    DNS writes (migration plan §3.2 item 4): read the current state, skip
    the write entirely when it already matches what was requested, and
    otherwise write exactly once -- never in a retry loop, since
    ``get_retries`` is GET-only by SDK design and a failed write must not
    be retried blindly.

    Args:
        read: Zero-argument async callable returning the current,
            already-comparable state (e.g. a bool, not a raw envelope --
            callers project the envelope down to the comparable value
            themselves, the same way ``dns.py``'s ``_current_state`` does).
        desired: The state the caller wants.
        write: Zero-argument async callable performing the write. Called
            at most once.
        compare: Optional equality predicate; defaults to ``==``. Pass this
            when *desired*'s natural equality does not match the API's
            (e.g. set-vs-list, or case-insensitive comparisons).
        force: When true, writes even if *read* already matches *desired*.
            Mirrors ``--force``'s existing "skip confirmation" contract by
            also skipping the no-op short-circuit, so a user who explicitly
            asked to force a write still gets one.
        console: Rich console for the "already configured" /
            "verify with ..." messages. Defaults to a new stderr console.
        read_command: The command to suggest for verifying the result,
            e.g. ``"eero network sqm show"``. Included in the post-write
            message when the write is accepted.

    Returns:
        True if a write was issued and accepted; False if the write was
        skipped because the state already matched (and ``force`` was not
        set).

    Raises:
        SystemExit: With ``ExitCode.GENERIC_ERROR`` (1) when the write's
            response is not a 2xx acceptance.
    """
    if console is None:
        console = Console(stderr=True)

    current = await read()
    is_equal = compare(current, desired) if compare is not None else current == desired

    if is_equal and not force:
        already_note = f" Check with `{read_command}`." if read_command else ""
        console.print(f"[dim]Already configured as requested; no change made.{already_note}[/dim]")
        return False

    result = await write()

    if not _write_accepted(result):
        console.print("[red]Write was not applied.[/red]")
        sys.exit(ExitCode.GENERIC_ERROR)

    note = f" Verify with `{read_command}`." if read_command else ""
    console.print(f"[bold green]Write accepted.[/bold green]{note}")
    return True


def confirm_action(message: str) -> bool:
    """Ask user to confirm an action.

    Args:
        message: The message to display

    Returns:
        True if user confirms, False otherwise
    """
    return click.confirm(message)
