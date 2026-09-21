"""CLI entry point with noun-first command structure.

This module provides the main CLI entry point with global flags
and registers command groups from the commands/ module.
"""

import logging
import re
import sys
from importlib.metadata import version
from typing import TYPE_CHECKING, Optional

import click
import eero
from rich.console import Console

from .commands import (
    activity_group,
    auth_group,
    completion_group,
    device_group,
    eero_group,
    network_group,
    profile_group,
    troubleshoot_group,
)
from .context import create_cli_context
from .utils import ensure_config, get_default_output, get_preferred_network

if TYPE_CHECKING:
    from .context import EeroCliContext

_LOGGER = logging.getLogger(__name__)

# -- SDK unverified-write warning surfacing (migration plan §3.3) --

_UNCHARACTERISED_WRITE_MARKER = "not been fully characterised"
"""Substring of eero-api's `warn_uncharacterised_write` text (DIGEST §5,
`api/_writes.py:66-72`). Filtering on message content rather than a logger
name prefix is deliberate: the SDK's write-warning loggers are not
uniformly named (most are `eero.api.<module>`, but at least one site logs
through `eero.client` instead), so a name-based filter would miss those --
DIGEST §5 explicitly recommends this over "a logger prefix alone".
"""

_OPERATION_PATTERN = re.compile(r"Issuing write \((.*?)\):")
"""Extracts the `%s` from "Issuing write (%s): its side effects..."."""


class _SdkWarningFilter(logging.Filter):
    """Captures eero-api's uncharacterised-write WARNINGs.

    Installed on the root logger's handler(s), not on a specific
    ``eero.api`` :class:`logging.Logger`: Python's propagation machinery
    only consults *handler*-level filters as a record climbs the logger
    hierarchy (``Logger.callHandlers``) -- a filter added to an ancestor
    ``Logger`` object via ``addFilter`` is never invoked for a descendant
    logger's own records, only for records logged directly through that
    exact logger. Attaching to the handler(s) that
    ``logging.basicConfig()`` installs on the root logger is the only place
    that actually observes every ``eero.api.<module>`` (and ``eero.client``)
    record on its way to the console.

    In normal and ``--quiet`` mode, suppresses the raw ``WARNING:...`` log
    line and instead prints one concise stderr note per distinct write
    operation via :meth:`EeroCliContext.record_sdk_warning` /
    :meth:`~eeroctl.output.OutputRenderer.render_sdk_warning_note`.
    ``--quiet`` still records the note into ``meta.warnings`` -- it only
    suppresses the stderr line. In ``--debug`` mode, the raw log line passes
    through unchanged instead (and this filter skips its own note, so the
    warning is not shown twice).
    """

    def __init__(self, cli_ctx: "EeroCliContext", debug: bool) -> None:
        super().__init__()
        self._cli_ctx = cli_ctx
        self._debug = debug

    def filter(self, record: logging.LogRecord) -> bool:
        """Return True to let *record* reach the handler's stream, else False."""
        message = record.getMessage()
        if _UNCHARACTERISED_WRITE_MARKER not in message:
            return True  # Not one of ours; never touch unrelated log records.

        match = _OPERATION_PATTERN.search(message)
        operation = match.group(1) if match else "unknown"

        # Always record -- meta.warnings must be populated the same way
        # whether or not --debug/--quiet changed what got printed.
        note = self._cli_ctx.record_sdk_warning(operation)

        if self._debug:
            return True  # Pass the raw SDK line through unchanged.

        if note is not None and not self._cli_ctx.quiet:
            self._cli_ctx.renderer.render_sdk_warning_note(note)

        return False  # Suppress the raw WARNING line.


# ==================== Version Info ====================


def _get_version_info() -> str:
    """Build version string with Python and eero-api versions."""
    eeroctl_version = version("eeroctl")
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return f"%(prog)s {eeroctl_version}\nPython {python_version}\neero-api {eero.__version__}"


# ==================== Main CLI Group ====================


@click.group(invoke_without_command=True)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug logging.",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Suppress non-essential output.",
)
@click.option(
    "--no-color",
    is_flag=True,
    help="Disable colored output.",
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["table", "list", "json", "yaml", "text"]),
    default=None,
    help="Output format (default from config, or 'table').",
)
@click.option(
    "--network-id",
    "-n",
    help="Network ID to operate on.",
)
@click.option(
    "--non-interactive",
    is_flag=True,
    help="Never prompt for input; fail if confirmation required.",
)
@click.option(
    "--force",
    "-y",
    "--yes",
    is_flag=True,
    help="Skip confirmation prompts for disruptive actions.",
)
@click.version_option(message=_get_version_info())
@click.pass_context
def cli(
    ctx: click.Context,
    debug: bool,
    quiet: bool,
    no_color: bool,
    output: Optional[str],
    network_id: Optional[str],
    non_interactive: bool,
    force: bool,
):
    """Eero network management CLI.

    Manage your Eero mesh Wi-Fi network from the command line.
    Use --help with any command for more information.
    """
    # Ensure config file exists with defaults
    ensure_config()

    # Setup logging. force=True installs a fresh root handler every
    # invocation (relevant in-process, e.g. under CliRunner in tests) so the
    # SDK-warning filter below is never attached to a stale handler left
    # over from an earlier command.
    if debug:
        logging.basicConfig(level=logging.DEBUG, force=True)
    else:
        logging.basicConfig(level=logging.WARNING, force=True)

    # Create console
    console = Console(force_terminal=not no_color, no_color=no_color, quiet=quiet)

    # Determine output format: command line > config > default
    effective_output = output if output is not None else get_default_output()

    # Create context
    cli_ctx = create_cli_context(
        debug=debug,
        quiet=quiet,
        no_color=no_color,
        output_format=effective_output,
        non_interactive=non_interactive,
        force=force,
    )

    # Surface the SDK's uncharacterised-write WARNINGs through the renderer
    # instead of the raw `WARNING:eero.api.dns:...` log line (migration plan
    # §3.3). Attached to the root logger's *handlers* -- see
    # _SdkWarningFilter's docstring for why a bare `addFilter` on an
    # `eero.api` Logger object would silently do nothing.
    sdk_warning_filter = _SdkWarningFilter(cli_ctx, debug=debug)
    for handler in logging.getLogger().handlers:
        handler.addFilter(sdk_warning_filter)

    # Override console with the configured one
    cli_ctx.console = console

    # Load preferred network if not specified
    if network_id:
        cli_ctx.network_id = network_id
    else:
        preferred_network = get_preferred_network()
        if preferred_network:
            cli_ctx.network_id = preferred_network

    ctx.obj = cli_ctx

    # Show help if no command specified
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ==================== Register Command Groups ====================

cli.add_command(auth_group, name="auth")
cli.add_command(network_group, name="network")
cli.add_command(eero_group, name="eero")
cli.add_command(device_group, name="device")
cli.add_command(profile_group, name="profile")
cli.add_command(activity_group, name="activity")
cli.add_command(troubleshoot_group, name="troubleshoot")
cli.add_command(completion_group, name="completion")


# ==================== Entry Point ====================


def main():
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
