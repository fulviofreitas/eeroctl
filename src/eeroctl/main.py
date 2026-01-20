"""CLI entry point with noun-first command structure.

This module provides the main CLI entry point with global flags
and registers command groups from the commands/ module.
"""

import logging
import sys
from importlib.metadata import version
from typing import Optional

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
from .utils import get_preferred_network

_LOGGER = logging.getLogger(__name__)


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
    default="table",
    help="Output format (default: table).",
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
    output: str,
    network_id: Optional[str],
    non_interactive: bool,
    force: bool,
):
    """Eero network management CLI.

    Manage your Eero mesh Wi-Fi network from the command line.
    Use --help with any command for more information.
    """
    # Setup logging
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    # Create console
    console = Console(force_terminal=not no_color, no_color=no_color, quiet=quiet)

    # Create context
    cli_ctx = create_cli_context(
        debug=debug,
        quiet=quiet,
        no_color=no_color,
        output_format=output,
        non_interactive=non_interactive,
        force=force,
    )

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
