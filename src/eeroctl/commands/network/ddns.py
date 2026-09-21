"""Dynamic DNS (DDNS) commands for the Eero CLI.

Commands:
- eero network ddns enable: Enable dynamic DNS
- eero network ddns disable: Disable dynamic DNS
"""

import asyncio
import sys
from typing import Any, Optional

import click
from eero import EeroClient

from ...context import get_cli_context
from ...safety import SafetyContext, SafetyError, get_write_spec, require_write_confirmation
from ...transformers import extract_data
from ...utils import run_with_client, write_if_changed


@click.group(name="ddns")
@click.pass_context
def ddns_group(ctx: click.Context) -> None:
    """Manage dynamic DNS (DDNS).

    \b
    Commands:
      enable  - Enable dynamic DNS
      disable - Disable dynamic DNS
    """
    pass


def _set_ddns(ctx: click.Context, enable: bool, force: Optional[bool]) -> None:
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    action = "enable" if enable else "disable"
    effective_force = force or cli_ctx.force

    spec = get_write_spec(f"network ddns {action}")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target="network",
            ctx=SafetyContext(
                force=effective_force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
            console=cli_ctx.console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_ddns(client: EeroClient) -> None:
            method = client.enable_ddns if enable else client.disable_ddns

            async def read() -> bool:
                # `ddns` has no dedicated GET -- read it from the raw
                # `get_network` envelope, the same field the phase-A
                # extended `security show` reads (migration plan §2.7).
                with cli_ctx.status("Reading current DDNS setting..."):
                    raw_network = await client.get_network(cli_ctx.network_id)
                net_data = extract_data(raw_network) if isinstance(raw_network, dict) else {}
                return bool(net_data.get("ddns", not enable))

            async def write() -> Any:
                with cli_ctx.status(f"{action.capitalize()}ing DDNS..."):
                    return await method(cli_ctx.network_id)

            await write_if_changed(
                read,
                enable,
                write,
                force=effective_force,
                console=console,
                read_command=spec.read_command,
            )

        await run_with_client(set_ddns)

    asyncio.run(run_cmd())


@ddns_group.command(name="enable")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def ddns_enable(ctx: click.Context, force: bool) -> None:
    """Enable dynamic DNS."""
    _set_ddns(ctx, True, force)


@ddns_group.command(name="disable")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def ddns_disable(ctx: click.Context, force: bool) -> None:
    """Disable dynamic DNS."""
    _set_ddns(ctx, False, force)
