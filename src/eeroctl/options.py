"""Shared CLI option decorators for flexible option placement.

This module provides reusable Click option decorators that can be applied
to any command, allowing options like --output, --network-id, and --force
to be placed anywhere in the command line.

Example:
    # Options can now appear at any level:
    eero network list --output json
    eero --output json network list
    eero device block "iPhone" --force

Usage:
    from ..options import output_option, network_option, apply_options

    @network_group.command(name="list")
    @output_option
    @click.pass_context
    def network_list(ctx: click.Context, output: str | None) -> None:
        apply_options(ctx, output=output)
        cli_ctx = get_cli_context(ctx)
        # cli_ctx.output_format now has the effective value
"""

import functools
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from typing import Any, Callable, Optional, TypeVar
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import click

from .context import EeroCliContext, get_cli_context

F = TypeVar("F", bound=Callable[..., Any])


# =============================================================================
# Option Value Resolution
# =============================================================================


def get_effective_value(
    ctx: click.Context,
    local_value: Any,
    attr_name: str,
    default: Any = None,
) -> Any:
    """Get the effective option value with proper precedence.

    Precedence (highest to lowest):
    1. Local value (if not None) - explicitly passed to this command
    2. Parent context value - from EeroCliContext in parent
    3. Default value

    Args:
        ctx: Click context
        local_value: Value passed to the current command (None = not specified)
        attr_name: Attribute name on EeroCliContext to check
        default: Default value if nothing else is set

    Returns:
        The effective value to use
    """
    # If a local value was explicitly provided, use it
    if local_value is not None:
        return local_value

    # Walk up the context chain to find EeroCliContext
    current: Optional[click.Context] = ctx
    while current is not None:
        if isinstance(current.obj, EeroCliContext):
            parent_value = getattr(current.obj, attr_name, None)
            if parent_value is not None:
                return parent_value
        current = current.parent

    return default


def apply_options(
    ctx: click.Context,
    *,
    output: Optional[str] = None,
    network_id: Optional[str] = None,
    force: Optional[bool] = None,
    non_interactive: Optional[bool] = None,
    debug: Optional[bool] = None,
    quiet: Optional[bool] = None,
    no_color: Optional[bool] = None,
) -> EeroCliContext:
    """Apply local option values to the CLI context with proper precedence.

    This function updates the EeroCliContext with effective values,
    merging local values with inherited parent values.

    Args:
        ctx: Click context
        output: Local --output value (None = inherit from parent)
        network_id: Local --network-id value (None = inherit from parent)
        force: Local --force value (None = inherit from parent)
        non_interactive: Local --non-interactive value (None = inherit from parent)
        debug: Local --debug value (None = inherit from parent)
        quiet: Local --quiet value (None = inherit from parent)
        no_color: Local --no-color value (None = inherit from parent)

    Returns:
        The updated EeroCliContext

    Example:
        @network_group.command(name="list")
        @output_option
        @network_option
        @click.pass_context
        def network_list(ctx, output, network_id):
            cli_ctx = apply_options(ctx, output=output, network_id=network_id)
            # Now use cli_ctx with effective values
    """
    cli_ctx = get_cli_context(ctx)

    # Apply output format
    if output is not None:
        cli_ctx.output_format = output
    elif cli_ctx.output_format is None:
        cli_ctx.output_format = "table"

    # Apply network ID
    if network_id is not None:
        cli_ctx.network_id = network_id

    # Apply force flag (for boolean, we need special handling)
    if force is not None:
        cli_ctx.force = force

    # Apply non-interactive flag
    if non_interactive is not None:
        cli_ctx.non_interactive = non_interactive

    # Apply debug flag
    if debug is not None:
        cli_ctx.debug = debug

    # Apply quiet flag
    if quiet is not None:
        cli_ctx.quiet = quiet

    # Apply no_color flag
    if no_color is not None:
        cli_ctx.no_color = no_color

    # Invalidate cached renderer if format or display options changed
    if output is not None or quiet is not None or no_color is not None:
        cli_ctx._renderer = None

    return cli_ctx


# =============================================================================
# Individual Option Decorators
# =============================================================================


def output_option(func: F) -> F:
    """Add --output/-o option to a command.

    When applied, the command can accept --output anywhere in the invocation.
    Use apply_options() or get_effective_value() to merge with parent values.

    The option uses default=None to distinguish "not specified" from
    an explicit default, enabling proper inheritance from parent context.

    Example:
        @command.command()
        @output_option
        @click.pass_context
        def list_items(ctx, output):
            cli_ctx = apply_options(ctx, output=output)
    """

    @click.option(
        "--output",
        "-o",
        type=click.Choice(["table", "list", "json", "yaml", "text"]),
        default=None,
        help="Output format.",
    )
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def network_option(func: F) -> F:
    """Add --network-id/-n option to a command.

    When applied, the command can accept --network-id anywhere in the invocation.
    Use apply_options() or get_effective_value() to merge with parent values.

    Example:
        @command.command()
        @network_option
        @click.pass_context
        def show_network(ctx, network_id):
            cli_ctx = apply_options(ctx, network_id=network_id)
    """

    @click.option(
        "--network-id",
        "-n",
        default=None,
        help="Network ID to operate on.",
    )
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def force_option(func: F) -> F:
    """Add --force/-y/--yes option to a command.

    When applied, the command can accept --force anywhere in the invocation.
    Use apply_options() or get_effective_value() to merge with parent values.

    Note: Uses is_flag=True with flag_value/default pattern to support
    three states: True (explicitly set), False (explicitly unset), None (inherit).

    Example:
        @command.command()
        @force_option
        @click.pass_context
        def delete_item(ctx, force):
            cli_ctx = apply_options(ctx, force=force)
    """

    @click.option(
        "--force/--no-force",
        "-y",
        default=None,
        help="Skip confirmation prompts.",
    )
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def non_interactive_option(func: F) -> F:
    """Add --non-interactive option to a command.

    When applied, the command can accept --non-interactive anywhere in the invocation.
    In non-interactive mode, the CLI will fail if confirmation is required.

    Example:
        @command.command()
        @non_interactive_option
        @click.pass_context
        def dangerous_action(ctx, non_interactive):
            cli_ctx = apply_options(ctx, non_interactive=non_interactive)
    """

    @click.option(
        "--non-interactive/--interactive",
        default=None,
        help="Never prompt for input; fail if confirmation required.",
    )
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def debug_option(func: F) -> F:
    """Add --debug/--no-debug option to a command.

    When applied, the command can accept --debug anywhere in the invocation.
    Debug mode enables verbose logging output.

    Example:
        @command.command()
        @debug_option
        @click.pass_context
        def some_command(ctx, debug):
            cli_ctx = apply_options(ctx, debug=debug)
    """

    @click.option(
        "--debug/--no-debug",
        default=None,
        help="Enable debug logging.",
    )
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def quiet_option(func: F) -> F:
    """Add --quiet/--no-quiet option to a command.

    When applied, the command can accept --quiet/-q anywhere in the invocation.
    Quiet mode suppresses non-essential output.

    Example:
        @command.command()
        @quiet_option
        @click.pass_context
        def some_command(ctx, quiet):
            cli_ctx = apply_options(ctx, quiet=quiet)
    """

    @click.option(
        "--quiet/--no-quiet",
        "-q",
        default=None,
        help="Suppress non-essential output.",
    )
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def no_color_option(func: F) -> F:
    """Add --no-color/--color option to a command.

    When applied, the command can accept --no-color anywhere in the invocation.
    Disables colored output for the command.

    Example:
        @command.command()
        @no_color_option
        @click.pass_context
        def some_command(ctx, no_color):
            cli_ctx = apply_options(ctx, no_color=no_color)
    """

    @click.option(
        "--no-color/--color",
        default=None,
        help="Disable colored output.",
    )
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


# =============================================================================
# Combined Option Decorators
# =============================================================================


def safety_options(func: F) -> F:
    """Add safety-related options (--force, --non-interactive) to a command.

    Combines force_option and non_interactive_option for commands that
    perform destructive actions requiring confirmation.

    Example:
        @command.command()
        @safety_options
        @click.pass_context
        def reboot_device(ctx, force, non_interactive):
            cli_ctx = apply_options(ctx, force=force, non_interactive=non_interactive)
    """
    return force_option(non_interactive_option(func))


def common_options(func: F) -> F:
    """Add commonly used options (--output, --network-id) to a command.

    Combines output_option and network_option for read commands that
    display data and operate on a specific network.

    Example:
        @command.command()
        @common_options
        @click.pass_context
        def list_devices(ctx, output, network_id):
            cli_ctx = apply_options(ctx, output=output, network_id=network_id)
    """
    return output_option(network_option(func))


def display_options(func: F) -> F:
    """Add display-related options (--debug, --quiet, --no-color) to a command.

    Combines debug_option, quiet_option, and no_color_option for commands
    where per-command display control is useful.

    Example:
        @command.command()
        @display_options
        @click.pass_context
        def verbose_command(ctx, debug, quiet, no_color):
            cli_ctx = apply_options(ctx, debug=debug, quiet=quiet, no_color=no_color)
    """
    return debug_option(quiet_option(no_color_option(func)))


def all_options(func: F) -> F:
    """Add all common options to a command.

    Combines output_option, network_option, force_option, non_interactive_option,
    and display options (debug, quiet, no_color).
    Use for commands that need full control over all settings.

    Example:
        @command.command()
        @all_options
        @click.pass_context
        def full_command(ctx, output, network_id, force, non_interactive, debug, quiet, no_color):
            cli_ctx = apply_options(
                ctx,
                output=output,
                network_id=network_id,
                force=force,
                non_interactive=non_interactive,
                debug=debug,
                quiet=quiet,
                no_color=no_color,
            )
    """
    return common_options(safety_options(display_options(func)))


# =============================================================================
# Time-Window Option Group
# =============================================================================
#
# Shared `--start`/`--end`/`--cadence`/`--timezone` group backing the phase-A read
# families that hit insights/data-usage/channel-utilization endpoints:
#   - eero-api 8.0.1 `get_insights` (client.py:1273): `cadence: str = "daily"`,
#     validated against `INSIGHTS_CADENCES == ("hourly", "daily")` (insights.py:30,137).
#   - eero-api 8.0.1 `get_data_usage` (client.py:1578): `start`/`end`/`cadence` required
#     keyword-only, `cadence` validated against `DATA_USAGE_CADENCES == CADENCE_VALUES ==
#     ("daily", "hourly")` (data_usage.py:28, _params.py:25).
#   - eero-api 8.0.1 `get_channel_utilization` (client.py:2339): `start`/`end` required
#     keyword-only, no cadence.
# See eeroctl-context DIGEST §6/§7 and the migration plan §4 "Shared time-window option
# group" paragraph. This commit only adds the decorator + validation helper; wiring the
# phase-A commands (`network channels`, `activity *`, `network usage *`) onto it is a
# separate commit per family.


class Iso8601ZParamType(click.ParamType):
    """A `click.ParamType` for ISO-8601 UTC timestamps with a mandatory trailing 'Z'.

    Rejects anything else (bare dates, naive timestamps, explicit UTC offsets) so the
    on-wire format eero-api expects (`start`/`end` as `Z`-suffixed strings) is enforced
    before any network call is made. An invalid value fails parsing inside Click, which
    surfaces it as a usage error (exit code 2) before the command callback ever runs.
    """

    name = "iso8601"

    def convert(
        self,
        value: Any,
        param: Optional[click.Parameter],
        ctx: Optional[click.Context],
    ) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str) and value.endswith("Z"):
            try:
                datetime.fromisoformat(f"{value[:-1]}+00:00")
            except ValueError:
                pass
            else:
                return value
        self.fail(
            f"{value!r} is not a valid ISO-8601 UTC timestamp; expected format "
            "YYYY-MM-DDTHH:MM:SSZ (trailing 'Z' required, no explicit UTC offset).",
            param,
            ctx,
        )


class IanaTimezoneParamType(click.ParamType):
    """A `click.ParamType` for IANA timezone names, validated via `zoneinfo.ZoneInfo`."""

    name = "timezone"

    def convert(
        self,
        value: Any,
        param: Optional[click.Parameter],
        ctx: Optional[click.Context],
    ) -> Optional[str]:
        if value is None:
            return None
        try:
            ZoneInfo(str(value))
        except (ZoneInfoNotFoundError, ValueError, KeyError):
            self.fail(
                f"{value!r} is not a valid IANA timezone name (e.g. 'Europe/Lisbon').",
                param,
                ctx,
            )
        return value


ISO8601_TIMESTAMP = Iso8601ZParamType()
IANA_TIMEZONE = IanaTimezoneParamType()

# Default window width applied by resolve_time_window() when --start is omitted, keyed
# by cadence. Matches CADENCE_VALUES / INSIGHTS_CADENCES / DATA_USAGE_CADENCES
# (eero-api _params.py:25, insights.py:30, data_usage.py:28) -- both SDK cadence sets are
# "hourly"/"daily", so a two-entry map covers every phase-A caller.
_DEFAULT_WINDOW_BY_CADENCE: dict[str, timedelta] = {
    "hourly": timedelta(hours=24),
    "daily": timedelta(days=7),
}


def time_window_options(
    *,
    cadence_required: bool = False,
    cadence_choices: tuple[str, ...] = ("hourly", "daily"),
    include_timezone: bool = False,
) -> Callable[[F], F]:
    """Build a decorator adding `--start`/`--end`/`--cadence`[/`--timezone`] to a command.

    Options are format-validated at parse time via `Iso8601ZParamType` /
    `IanaTimezoneParamType`, so a malformed value is a Click usage error (exit code 2)
    raised before the decorated command's body runs. Options default to `None` (not
    specified); use `resolve_time_window()` in the command body to fill in sensible
    defaults and to reject an inverted window.

    Args:
        cadence_required: Whether `--cadence` must be supplied. Matches the SDK: most
            insights/data-usage facade methods require `cadence` as keyword-only,
            while `get_data_usage_breakdown`, `get_devices_data_usage`, and
            `get_unprofiled_devices_data_usage` take `cadence: Optional[str] = None`
            (eero-api client.py:1605/1624/1728).
        cadence_choices: Allowed `--cadence` values. Defaults to the SDK's two-value
            cadence set (`"hourly"`, `"daily"`) shared by `CADENCE_VALUES` and
            `INSIGHTS_CADENCES` (eero-api _params.py:25, insights.py:30).
        include_timezone: Whether to also add `--timezone` (IANA name). Only
            `get_data_usage`-family endpoints accept it; `get_insights` and
            `get_channel_utilization` do not.

    Returns:
        A decorator that adds the option(s) to a Click command, innermost-first so they
        compose the same way as `common_options`/`safety_options`/`all_options` above.

    Example:
        @network_group.command(name="channels")
        @time_window_options()
        @output_option
        @network_option
        @click.pass_context
        def network_channels(ctx, start, end, cadence, output, network_id):
            start_iso, end_iso = resolve_time_window(start, end, cadence)
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapped: Any = wrapper
        if include_timezone:
            wrapped = click.option(
                "--timezone",
                type=IANA_TIMEZONE,
                default=None,
                help="IANA timezone name (e.g. Europe/Lisbon). Defaults to UTC.",
            )(wrapped)
        # NOTE: --cadence's `default` kwarg is only passed when the flag is optional.
        # Click's required check only fires for a truly-unset value (its internal UNSET
        # sentinel); passing `default=None` explicitly -- even alongside
        # `required=True` -- makes Click treat "not supplied" as an already-satisfied
        # None default, so `--cadence` would silently resolve to None instead of
        # failing with "Missing option '--cadence'." Omitting `default` entirely lets
        # Click fall back to its own UNSET sentinel, which the required check does
        # catch.
        cadence_kwargs: dict[str, Any] = {
            "type": click.Choice(cadence_choices),
            "required": cadence_required,
            "help": "Data cadence." + (" Required." if cadence_required else " Optional."),
        }
        if not cadence_required:
            cadence_kwargs["default"] = None
        wrapped = click.option("--cadence", **cadence_kwargs)(wrapped)
        wrapped = click.option(
            "--end",
            type=ISO8601_TIMESTAMP,
            default=None,
            help="End of window, ISO-8601 UTC (e.g. 2026-09-21T00:00:00Z). Defaults to now.",
        )(wrapped)
        wrapped = click.option(
            "--start",
            type=ISO8601_TIMESTAMP,
            default=None,
            help="Start of window, ISO-8601 UTC (e.g. 2026-09-21T00:00:00Z). "
            "Defaults to a cadence-sized window ending at --end.",
        )(wrapped)
        return wrapped  # type: ignore[return-value]

    return decorator


def resolve_time_window(
    start: Optional[str],
    end: Optional[str],
    cadence: Optional[str] = None,
) -> tuple[str, str]:
    """Resolve `--start`/`--end` values to concrete ISO-8601 UTC strings.

    Values already went through `Iso8601ZParamType` during Click parsing, so they are
    either `None` or well-formed `...Z` strings here.

    Defaulting, when `--end`/`--start` are omitted:
        - `end` defaults to now (UTC, second precision, `Z`-suffixed).
        - `start` defaults to `end` minus a cadence-sized window: 24h for `"hourly"`,
          7d for anything else (including `None`, e.g. when cadence is optional).

    Args:
        start: Raw `--start` value, or `None`.
        end: Raw `--end` value, or `None`.
        cadence: Cadence driving the default window width when `--start` is omitted.

    Returns:
        `(start_iso, end_iso)`, both `Z`-suffixed ISO-8601 UTC strings.

    Raises:
        click.UsageError: if the resolved start is not strictly before the resolved end
            (exit code 2, matching the Click usage-error contract used for `--start`/
            `--end` format errors).
    """
    end_dt = _parse_iso_z(end) if end is not None else _now_utc()
    if start is not None:
        start_dt = _parse_iso_z(start)
    else:
        window = _DEFAULT_WINDOW_BY_CADENCE.get(
            cadence or "daily", _DEFAULT_WINDOW_BY_CADENCE["daily"]
        )
        start_dt = end_dt - window

    if start_dt >= end_dt:
        raise click.UsageError(
            f"--start ({_format_iso_z(start_dt)}) must be before --end ({_format_iso_z(end_dt)})."
        )

    return _format_iso_z(start_dt), _format_iso_z(end_dt)


def _now_utc() -> datetime:
    """Current UTC time at second precision (no microseconds)."""
    return datetime.now(dt_timezone.utc).replace(microsecond=0)


def _parse_iso_z(value: str) -> datetime:
    """Parse a `Z`-suffixed ISO-8601 string (already format-validated) into a datetime."""
    return datetime.fromisoformat(f"{value[:-1]}+00:00")


def _format_iso_z(value: datetime) -> str:
    """Format a datetime as a `Z`-suffixed, second-precision ISO-8601 UTC string."""
    return value.astimezone(dt_timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
