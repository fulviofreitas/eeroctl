"""Port forwarding commands for the Eero CLI.

Commands:
- eero network forwards list: List all port forwards
- eero network forwards show: Show details of a port forward
- eero network forwards create: Create a port forward
- eero network forwards update: Update a port forward
- eero network forwards delete: Delete a port forward
"""

import asyncio
import json
import sys
from typing import Any, Optional

import click
from eero import EeroClient
from rich.panel import Panel
from rich.table import Table

from ...context import get_cli_context
from ...exit_codes import ExitCode
from ...options import apply_options, force_option, network_option
from ...safety import SafetyContext, SafetyError, get_write_spec, require_write_confirmation
from ...transformers import extract_list
from ...utils import run_with_client


def _parse_config_json(console: Any, raw: str) -> dict:
    """Parse a `--config-json` option into a non-empty dict, or exit 2.

    The SDK types `forward_data`/`reservation_data` as an opaque
    ``Dict[str, Any]`` with no documented shape (migration plan §4 phase C
    rows 32/33); eeroctl accepts the caller's JSON object verbatim rather
    than guessing field names.
    """
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        console.print(f"[red]Invalid --config-json: {e}[/red]")
        sys.exit(ExitCode.USAGE_ERROR)
    if not isinstance(parsed, dict) or not parsed:
        console.print("[red]--config-json must be a non-empty JSON object[/red]")
        sys.exit(ExitCode.USAGE_ERROR)
    return parsed


@click.group(name="forwards")
@click.pass_context
def forwards_group(ctx: click.Context) -> None:
    """Manage port forwarding rules.

    \b
    Commands:
      list   - List all port forwards
      show   - Show details of a port forward
      create - Create a port forward
      update - Update a port forward
      delete - Delete a port forward
    """
    pass


@forwards_group.command(name="list")
@click.pass_context
def forwards_list(ctx: click.Context) -> None:
    """List all port forwarding rules."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_forwards(client: EeroClient) -> None:
            with cli_ctx.status("Getting port forwards..."):
                raw_response = await client.get_forwards(cli_ctx.network_id)

            # Extract forwards list from raw response
            forwards = extract_list(raw_response, "forwards")

            if cli_ctx.is_json_output():
                renderer.render_json(raw_response, "eero.network.forwards.list/v1")
            else:
                if not forwards:
                    console.print("[yellow]No port forwards configured[/yellow]")
                    return

                table = Table(title="Port Forwards")
                table.add_column("ID", style="dim")
                table.add_column("Name", style="cyan")
                table.add_column("External Port")
                table.add_column("Internal IP")
                table.add_column("Internal Port")
                table.add_column("Protocol")

                for fwd in forwards:
                    table.add_row(
                        str(fwd.get("id", "")),
                        fwd.get("name", ""),
                        str(fwd.get("external_port", "")),
                        fwd.get("internal_ip", ""),
                        str(fwd.get("internal_port", "")),
                        fwd.get("protocol", "tcp"),
                    )

                console.print(table)

        await run_with_client(get_forwards)

    asyncio.run(run_cmd())


@forwards_group.command(name="show")
@click.argument("forward_id")
@click.pass_context
def forwards_show(ctx: click.Context, forward_id: str) -> None:
    """Show details of a port forward.

    Unlike `eero show`/`device show`/`profile show`, this command cannot
    forward `forward_id` verbatim to an id-validated SDK read: the facade
    exposes no singular `get_forward`, only `get_forwards` (list) plus
    `update_forward`/`delete_forward` (writes -- unsafe to call from a read
    command just to borrow their id validation, since a well-shaped id would
    reach the transport as a real mutation). Per migration plan §2.5 rule
    ("forward to the id-taking SDK method ... else document"): documented
    gap, not fixed. A hostile `forward_id` is still reported "not found"
    (exit 5), not rejected as invalid (exit 2); see
    `tests/cli/test_link_validation.py::TestForwardsShowRejectsHostileIds`.
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_forward(client: EeroClient) -> None:
            with cli_ctx.status("Getting port forward..."):
                raw_response = await client.get_forwards(cli_ctx.network_id)

            # Extract forwards list from raw response
            forwards = extract_list(raw_response, "forwards")

            target = None
            for fwd in forwards:
                if str(fwd.get("id")) == forward_id:
                    target = fwd
                    break

            if not target:
                console.print(f"[red]Port forward '{forward_id}' not found[/red]")
                sys.exit(ExitCode.NOT_FOUND)

            if cli_ctx.is_json_output():
                renderer.render_json(target, "eero.network.forwards.show/v1")
            elif cli_ctx.is_list_output():
                renderer.render_text(target, "eero.network.forwards.show/v1")
            else:
                content = "\n".join(f"[bold]{k}:[/bold] {v}" for k, v in target.items())
                console.print(
                    Panel(content, title=f"Port Forward: {forward_id}", border_style="blue")
                )

        await run_with_client(get_forward)

    asyncio.run(run_cmd())


@forwards_group.command(name="create")
@click.option(
    "--config-json",
    required=True,
    help='Forward definition as a JSON object, e.g. \'{"name": "SSH", ...}\'',
)
@force_option
@network_option
@click.pass_context
def forwards_create(
    ctx: click.Context, config_json: str, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Create a port forward.

    The shape of the forward object is not documented by the SDK; pass
    exactly what the API expects via --config-json.
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.err_console
    forward_data = _parse_config_json(console, config_json)

    spec = get_write_spec("network forwards create")
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
            console=cli_ctx.err_console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def create(client: EeroClient) -> None:
            with cli_ctx.status("Creating port forward..."):
                result = await client.create_forward(forward_data, cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") in (200, 201) or result:
                console.print("[bold green]Port forward created.[/bold green]")
                console.print(f"[dim]Verify with `{spec.read_command}`.[/dim]")
            else:
                console.print("[red]Failed to create port forward[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(create)

    asyncio.run(run_cmd())


@forwards_group.command(name="update")
@click.argument("forward_id")
@click.option(
    "--config-json",
    required=True,
    help="Fields to update, as a JSON object (at least one field required)",
)
@force_option
@network_option
@click.pass_context
def forwards_update(
    ctx: click.Context,
    forward_id: str,
    config_json: str,
    force: Optional[bool],
    network_id: Optional[str],
) -> None:
    """Update a port forward.

    \b
    Arguments:
      FORWARD_ID  The forward's id
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.err_console
    forward_data = _parse_config_json(console, config_json)

    spec = get_write_spec("network forwards update")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target=forward_id,
            ctx=SafetyContext(
                force=cli_ctx.force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
            console=cli_ctx.err_console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def update(client: EeroClient) -> None:
            with cli_ctx.status("Updating port forward..."):
                result = await client.update_forward(forward_id, forward_data, cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print("[bold green]Port forward updated.[/bold green]")
                console.print(f"[dim]Verify with `{spec.read_command}`.[/dim]")
            else:
                console.print("[red]Failed to update port forward[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(update)

    asyncio.run(run_cmd())


@forwards_group.command(name="delete")
@click.argument("forward_id")
@force_option
@network_option
@click.pass_context
def forwards_delete(
    ctx: click.Context, forward_id: str, force: Optional[bool], network_id: Optional[str]
) -> None:
    """Delete a port forward.

    \b
    Arguments:
      FORWARD_ID  The forward's id
    """
    cli_ctx = apply_options(ctx, network_id=network_id, force=force)
    console = cli_ctx.err_console

    spec = get_write_spec("network forwards delete")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target=forward_id,
            ctx=SafetyContext(
                force=cli_ctx.force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
            console=cli_ctx.err_console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def delete(client: EeroClient) -> None:
            with cli_ctx.status("Deleting port forward..."):
                result = await client.delete_forward(forward_id, cli_ctx.network_id)

            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            if meta.get("code") == 200 or result:
                console.print("[bold green]Port forward deleted.[/bold green]")
            else:
                console.print("[red]Failed to delete port forward[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(delete)

    asyncio.run(run_cmd())
