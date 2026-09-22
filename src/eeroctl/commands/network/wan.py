"""WAN commands for the Eero CLI.

Commands:
- eero network wan multistaticip show -- get_multistaticip (client.py:3032)
- eero network wan multistaticip set --config-json -- set_multistaticip
  (client.py:3043); HIGH mesh (migration plan §3.1's mesh-reboot list).
  ``config`` is forwarded to the API unchanged (undocumented shape), hence
  `--config-json`.
- eero network wan secondary set --config-json -- set_secondary_wan_config
  (client.py:3052); HIGH mesh; same undocumented-payload rationale.

Migration plan §12 Q7 (decided 2026-09-21): absent-feature reads exit 0 with
an explicit "not configured"/"unavailable" line and `data: null` in
structured output; exit 5 stays reserved for a wrong id.

The SDK documents (`eero/api/wan.py:49-51`) that a network without the
multi-static-IP feature returns HTTP 404 with error code
`error.network.multistaticip_not_found`, distinguishable via
`EeroNotFoundException.error_code`. That specific error code is treated as
"not configured" (exit 0); any other `EeroNotFoundException` (a wrong
network id) is left to propagate to the standard exit-5 mapping in
`errors.handle_cli_error`.
"""

import asyncio
import json
import sys
from typing import Optional

import click
from eero import EeroClient
from eero.exceptions import EeroNotFoundException

from ...exit_codes import ExitCode
from ...formatting.wan import print_multistaticip, print_multistaticip_not_configured
from ...options import apply_options, common_options, force_option, network_option
from ...safety import SafetyContext, SafetyError, get_write_spec, require_write_confirmation
from ...transformers.wan import extract_multistaticip
from ...utils import run_with_client


def _parse_config_json(console, raw: str) -> dict:
    """Parse a `--config-json` option into a non-empty dict, or exit 2."""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        console.print(f"[red]Invalid --config-json: {e}[/red]")
        sys.exit(ExitCode.USAGE_ERROR)
    if not isinstance(parsed, dict) or not parsed:
        console.print("[red]--config-json must be a non-empty JSON object[/red]")
        sys.exit(ExitCode.USAGE_ERROR)
    return parsed


MULTISTATICIP_NOT_FOUND_ERROR_CODE = "error.network.multistaticip_not_found"
"""The SDK-observed error code for "feature absent" (`eero/api/wan.py:50-51`).

Any other `EeroNotFoundException` here means a wrong network id and is left
to propagate to the standard exit-5 mapping (Q7).
"""


@click.group(name="wan")
@click.pass_context
def wan_group(ctx: click.Context) -> None:
    """Manage WAN configuration.

    \b
    Commands:
      multistaticip - Multi-static-IP configuration
      secondary     - Secondary WAN configuration
    """
    pass


@wan_group.group(name="multistaticip")
@click.pass_context
def multistaticip_group(ctx: click.Context) -> None:
    """Manage multi-static-IP configuration.

    \b
    Commands:
      show - Multi-static-IP configuration (or "not configured")
      set  - Set multi-static-IP configuration
    """
    pass


@multistaticip_group.command(name="show")
@common_options
@click.pass_context
def multistaticip_show(
    ctx: click.Context, output: Optional[str], network_id: Optional[str]
) -> None:
    """Show multi-static-IP configuration.

    Exits 0 with a "not configured" line (and `data: null` in structured
    output) when the network doesn't have this feature -- see Q7 in the
    migration plan. A wrong network id still exits 5.
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_multistaticip(client: EeroClient) -> None:
            with cli_ctx.status("Getting multi-static-IP configuration..."):
                try:
                    raw = await client.get_multistaticip(cli_ctx.network_id)
                except EeroNotFoundException as e:
                    if e.error_code == MULTISTATICIP_NOT_FOUND_ERROR_CODE:
                        print_multistaticip_not_configured(cli_ctx)
                        return
                    raise
            print_multistaticip(cli_ctx, extract_multistaticip(raw))

        await run_with_client(get_multistaticip)

    asyncio.run(run_cmd())


@multistaticip_group.command(name="set")
@click.option(
    "--config-json",
    required=True,
    help="Multi-static-IP configuration as a JSON object.",
)
@force_option
@network_option
@click.pass_context
def multistaticip_set(
    ctx: click.Context, config_json: str, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Set the multi-static-IP configuration.

    Applying this change reboots every eero on the network. The shape of
    the configuration object is not documented by the SDK; pass exactly
    what the API expects via --config-json.
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.err_console
    config = _parse_config_json(console, config_json)

    spec = get_write_spec("network wan multistaticip set")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target="network",
            ctx=SafetyContext(
                force=cli_ctx.force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
            console=console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_multistaticip(client: EeroClient) -> None:
            with cli_ctx.status("Setting multi-static-IP configuration..."):
                result = await client.set_multistaticip(config, cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print("[bold green]Multi-static-IP configuration set.[/bold green]")
                console.print(f"[dim]Verify with `{spec.read_command}`.[/dim]")
            else:
                console.print("[red]Failed to set multi-static-IP configuration[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_multistaticip)

    asyncio.run(run_cmd())


@wan_group.group(name="secondary")
@click.pass_context
def secondary_wan_group(ctx: click.Context) -> None:
    """Manage secondary WAN configuration.

    \b
    Commands:
      set - Set secondary WAN configuration
    """
    pass


@secondary_wan_group.command(name="set")
@click.option(
    "--config-json",
    required=True,
    help="Secondary WAN configuration as a JSON object.",
)
@force_option
@network_option
@click.pass_context
def secondary_wan_set(
    ctx: click.Context, config_json: str, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Set the secondary WAN configuration.

    Applying this change reboots every eero on the network. The shape of
    the configuration object is not documented by the SDK; pass exactly
    what the API expects via --config-json.
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.err_console
    config = _parse_config_json(console, config_json)

    spec = get_write_spec("network wan secondary set")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target="network",
            ctx=SafetyContext(
                force=cli_ctx.force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
            console=console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_secondary_wan(client: EeroClient) -> None:
            with cli_ctx.status("Setting secondary WAN configuration..."):
                result = await client.set_secondary_wan_config(config, cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print("[bold green]Secondary WAN configuration set.[/bold green]")
                console.print(f"[dim]Verify with `{spec.read_command}`.[/dim]")
            else:
                console.print("[red]Failed to set secondary WAN configuration[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_secondary_wan)

    asyncio.run(run_cmd())
