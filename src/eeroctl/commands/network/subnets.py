"""Subnet commands for the Eero CLI.

Commands:
- eero network subnets show                    -- get_subnets_config
  (client.py:2991)
- eero network subnets filters show <subnet-id> -- get_subnet_content_filters
  (client.py:3023)
- eero network subnets set --config-json        -- set_subnets_config
  (client.py:2998); HIGH mesh (migration plan §3.1's mesh-reboot list).
  ``config`` is forwarded to the API unchanged with no key/value validation
  (`api/subnets.py:78-104`), so this stays `--config-json` rather than
  guessing field names.
- eero network subnets delete <type>            -- delete_subnet
  (client.py:3007); HIGH mesh
- eero network subnets filters set <subnet-id> --config-json
  -- set_subnet_content_filters (client.py:3016); MEDIUM + unverified.
  DIGEST deviation from the task brief: the facade signature is
  ``set_subnet_content_filters(network_id, filters)`` -- no ``subnet_id``
  parameter; the endpoint (`subnets_config/dns_policies/content_filters`)
  is network-scoped and the API's own declared fields are ``content_filters``
  and ``subnets`` (`api/subnets.py:150-151`), so the subnet the filters
  apply to is expected inside ``filters`` itself. ``<subnet-id>`` is kept as
  a required CLI argument (for the read-first/read-command messaging against
  `get_subnet_content_filters`) but is not passed to the SDK separately --
  the caller's ``--config-json`` payload must already carry the ``subnets``
  field naming it.

Both reads are plain GETs; the subnet id for `filters show` names a nested
sub-resource -- passed to the SDK verbatim, which validates it (no
client-side link parsing needed here).
"""

import asyncio
import json
import sys
from typing import Optional

import click
from eero import EeroClient

from ...exit_codes import ExitCode
from ...formatting.subnets import print_subnet_content_filters, print_subnets_config
from ...options import apply_options, common_options, force_option, network_option
from ...safety import SafetyContext, SafetyError, get_write_spec, require_write_confirmation
from ...transformers.subnets import extract_subnet_content_filters, extract_subnets_config
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


@click.group(name="subnets")
@click.pass_context
def subnets_group(ctx: click.Context) -> None:
    """Manage subnet configuration and content filters.

    \b
    Commands:
      show    - Subnet configuration
      set     - Set subnet configuration
      delete  - Delete a subnet
      filters - Per-subnet content filters
    """
    pass


@subnets_group.command(name="show")
@common_options
@click.pass_context
def subnets_show(ctx: click.Context, output: Optional[str], network_id: Optional[str]) -> None:
    """Show subnet configuration."""
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_subnets(client: EeroClient) -> None:
            with cli_ctx.status("Getting subnet configuration..."):
                raw = await client.get_subnets_config(cli_ctx.network_id)
            print_subnets_config(cli_ctx, extract_subnets_config(raw))

        await run_with_client(get_subnets)

    asyncio.run(run_cmd())


@subnets_group.command(name="set")
@click.option(
    "--config-json",
    required=True,
    help='Subnet configuration as a JSON object, e.g. \'{"subnet_type": "guest", ...}\'',
)
@force_option
@network_option
@click.pass_context
def subnets_set(
    ctx: click.Context, config_json: str, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Set the subnet configuration.

    Applying this change reboots every eero on the network. The shape of
    the configuration object is not documented by the SDK; pass exactly
    what the API expects via --config-json.
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.err_console
    config = _parse_config_json(console, config_json)

    spec = get_write_spec("network subnets set")
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
        async def set_subnets(client: EeroClient) -> None:
            with cli_ctx.status("Setting subnet configuration..."):
                result = await client.set_subnets_config(config, cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print("[bold green]Subnet configuration set.[/bold green]")
                console.print(f"[dim]Verify with `{spec.read_command}`.[/dim]")
            else:
                console.print("[red]Failed to set subnet configuration[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_subnets)

    asyncio.run(run_cmd())


@subnets_group.command(name="delete")
@click.argument("subnet_type")
@force_option
@network_option
@click.pass_context
def subnets_delete(
    ctx: click.Context, subnet_type: str, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Delete a subnet's configuration.

    Applying this change reboots every eero on the network.

    \b
    Arguments:
      SUBNET_TYPE  The subnet type to delete, as returned by
                   'network subnets show' (the `subnet_type` field)
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.err_console

    spec = get_write_spec("network subnets delete")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target=subnet_type,
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
        async def delete(client: EeroClient) -> None:
            with cli_ctx.status(f"Deleting subnet '{subnet_type}'..."):
                result = await client.delete_subnet(subnet_type, cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print("[bold green]Subnet deleted.[/bold green]")
            else:
                console.print("[red]Failed to delete subnet[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(delete)

    asyncio.run(run_cmd())


@subnets_group.group(name="filters")
@click.pass_context
def subnet_filters_group(ctx: click.Context) -> None:
    """Manage per-subnet content filters.

    \b
    Commands:
      show <subnet-id> - Content filters for one subnet
      set <subnet-id>  - Set content filters
    """
    pass


@subnet_filters_group.command(name="show")
@click.argument("subnet_id")
@common_options
@click.pass_context
def subnet_filters_show(
    ctx: click.Context, subnet_id: str, output: Optional[str], network_id: Optional[str]
) -> None:
    """Show content filters for one subnet.

    \b
    Arguments:
      SUBNET_ID  The subnet's id, as returned by 'network subnets show'
    """
    cli_ctx = apply_options(ctx, output=output, network_id=network_id)

    async def run_cmd() -> None:
        async def get_filters(client: EeroClient) -> None:
            with cli_ctx.status(f"Getting content filters for subnet {subnet_id}..."):
                raw = await client.get_subnet_content_filters(subnet_id, cli_ctx.network_id)
            print_subnet_content_filters(cli_ctx, extract_subnet_content_filters(raw))

        await run_with_client(get_filters)

    asyncio.run(run_cmd())


@subnet_filters_group.command(name="set")
@click.argument("subnet_id")
@click.option(
    "--config-json",
    required=True,
    help='Content filters as a JSON object, e.g. \'{"content_filters": {...}, "subnets": [...]}\'',
)
@force_option
@network_option
@click.pass_context
def subnet_filters_set(
    ctx: click.Context,
    subnet_id: str,
    config_json: str,
    force: Optional[bool],
    network_id: Optional[str],
) -> None:
    """Set content filters for one or more subnets.

    The endpoint this command calls is network-scoped, not subnet-scoped
    (`set_subnet_content_filters` takes no subnet id); SUBNET_ID is used
    here only to read back and verify the result via 'filters show', and
    must also be named inside --config-json's own payload for the API to
    apply the filters to it.

    \b
    Arguments:
      SUBNET_ID  The subnet's id, as returned by 'network subnets show'
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.err_console
    filters = _parse_config_json(console, config_json)

    spec = get_write_spec("network subnets filters set")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target=subnet_id,
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
        async def set_filters(client: EeroClient) -> None:
            with cli_ctx.status(f"Setting content filters for subnet {subnet_id}..."):
                result = await client.set_subnet_content_filters(filters, cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print("[bold green]Subnet content filters set.[/bold green]")
                console.print(
                    f"[dim]Verify with `eero network subnets filters show {subnet_id}`.[/dim]"
                )
            else:
                console.print("[red]Failed to set subnet content filters[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_filters)

    asyncio.run(run_cmd())
