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
from typing import Any, Callable, Optional, TypeVar

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
