"""Advanced network commands for the Eero CLI.

Commands:
- eero network routing: Show routing information
- eero network thread: Thread protocol settings
- eero network support: Support and diagnostics
"""

import asyncio
import json
import sys
from typing import Optional

import click
from eero import EeroClient
from rich.panel import Panel

from ...context import get_cli_context
from ...exit_codes import ExitCode
from ...safety import SafetyContext, SafetyError, get_write_spec, require_write_confirmation
from ...utils import run_with_client

# ==================== Routing Subcommand ====================


@click.command(name="routing")
@click.pass_context
def routing_show(ctx: click.Context) -> None:
    """Show routing information."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_routing(client: EeroClient) -> None:
            with cli_ctx.status("Getting routing information..."):
                routing = await client.get_routing(cli_ctx.network_id)

            if cli_ctx.is_json_output():
                renderer.render_json(routing, "eero.network.routing.show/v1")
            elif cli_ctx.is_list_output():
                renderer.render_text(routing, "eero.network.routing.show/v1")
            else:
                console.print(
                    Panel(
                        json.dumps(routing, indent=2),
                        title="Routing Information",
                        border_style="blue",
                    )
                )

        await run_with_client(get_routing)

    asyncio.run(run_cmd())


# ==================== Thread Subcommand Group ====================


@click.group(name="thread")
@click.pass_context
def thread_cmd_group(ctx: click.Context) -> None:
    """Manage Thread protocol settings.

    Thread is used for smart home devices. Enable/disable
    is under security settings.

    \b
    Commands:
      show - Show Thread protocol information
      set  - Update credential syncing / regenerate credentials
    """
    pass


@thread_cmd_group.command(name="show")
@click.pass_context
def thread_show(ctx: click.Context) -> None:
    """Show Thread protocol information."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_thread(client: EeroClient) -> None:
            with cli_ctx.status("Getting Thread information..."):
                thread_data = await client.get_thread(cli_ctx.network_id)

            if cli_ctx.is_json_output():
                renderer.render_json(thread_data, "eero.network.thread.show/v1")
            elif cli_ctx.is_list_output():
                renderer.render_text(thread_data, "eero.network.thread.show/v1")
            else:
                console.print(
                    Panel(
                        json.dumps(thread_data, indent=2),
                        title="Thread Protocol",
                        border_style="blue",
                    )
                )

        await run_with_client(get_thread)

    asyncio.run(run_cmd())


@thread_cmd_group.command(name="set")
@click.option(
    "--credential-syncing/--no-credential-syncing",
    "credential_syncing",
    default=None,
    help="Enable/disable Thread credential syncing",
)
@click.option("--regenerate", is_flag=True, help="Regenerate the network's Thread credentials")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def thread_set(
    ctx: click.Context,
    credential_syncing: Optional[bool],
    regenerate: bool,
    force: bool,
) -> None:
    """Update Thread protocol settings.

    At least one of --credential-syncing/--no-credential-syncing or
    --regenerate is required.
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.err_console
    effective_force = force or cli_ctx.force

    if credential_syncing is None and not regenerate:
        console.print(
            "[red]At least one of --credential-syncing/--no-credential-syncing "
            "or --regenerate is required[/red]"
        )
        sys.exit(ExitCode.USAGE_ERROR)

    spec = get_write_spec("network thread set")
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
            console=cli_ctx.err_console,
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def set_thread(client: EeroClient) -> None:
            ok = True

            if credential_syncing is not None:
                with cli_ctx.status("Updating Thread credential syncing..."):
                    result = await client.update_thread(
                        enable_credential_syncing=credential_syncing,
                        network_id=cli_ctx.network_id,
                    )
                meta = result.get("meta", {}) if isinstance(result, dict) else {}
                ok = ok and (meta.get("code") == 200 or bool(result))

            if regenerate:
                with cli_ctx.status("Regenerating Thread credentials..."):
                    result = await client.regenerate_thread_credentials(cli_ctx.network_id)
                meta = result.get("meta", {}) if isinstance(result, dict) else {}
                ok = ok and (meta.get("code") == 200 or bool(result))

            if ok:
                console.print("[bold green]Thread settings updated.[/bold green]")
            else:
                console.print("[red]Failed to update Thread settings[/red]")
                sys.exit(ExitCode.GENERIC_ERROR)

        await run_with_client(set_thread)

    asyncio.run(run_cmd())


# ==================== Support Subcommand Group ====================


@click.group(name="support")
@click.pass_context
def support_group(ctx: click.Context) -> None:
    """Support and diagnostics.

    \b
    Commands:
      show   - Show support information
      bundle - Export support bundle
    """
    pass


@support_group.command(name="show")
@click.pass_context
def support_show(ctx: click.Context) -> None:
    """Show support information."""
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console
    renderer = cli_ctx.renderer

    async def run_cmd() -> None:
        async def get_support(client: EeroClient) -> None:
            with cli_ctx.status("Getting support information..."):
                support_data = await client.get_support(cli_ctx.network_id)

            if cli_ctx.is_json_output():
                renderer.render_json(support_data, "eero.network.support.show/v1")
            elif cli_ctx.is_list_output():
                renderer.render_text(support_data, "eero.network.support.show/v1")
            else:
                console.print(
                    Panel(
                        json.dumps(support_data, indent=2),
                        title="Support Information",
                        border_style="blue",
                    )
                )

        await run_with_client(get_support)

    asyncio.run(run_cmd())


@support_group.group(name="bundle")
@click.pass_context
def bundle_group(ctx: click.Context) -> None:
    """Manage support bundles."""
    pass


@bundle_group.command(name="export")
@click.option("--out", "-o", required=True, help="Output file path")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def bundle_export(ctx: click.Context, out: str, force: bool) -> None:
    """Export support bundle to file.

    Creates a diagnostic bundle for Eero support.
    """
    cli_ctx = get_cli_context(ctx)
    console = cli_ctx.console

    spec = get_write_spec("network support bundle export")
    cli_ctx.active_write_spec = spec
    try:
        require_write_confirmation(
            spec,
            target=f"to {out}",
            ctx=SafetyContext(
                force=force or cli_ctx.force,
                non_interactive=cli_ctx.non_interactive,
                dry_run=cli_ctx.dry_run,
            ),
        )
    except SafetyError as e:
        cli_ctx.renderer.render_error(e.message)
        sys.exit(e.exit_code)

    async def run_cmd() -> None:
        async def export_bundle(client: EeroClient) -> None:
            with cli_ctx.status("Generating support bundle..."):
                support_data = await client.get_support(cli_ctx.network_id)
                diagnostics = await client.get_diagnostics(cli_ctx.network_id)

            bundle = {
                "support": support_data,
                "diagnostics": diagnostics,
            }

            with open(out, "w") as f:
                json.dump(bundle, f, indent=2, default=str)

            console.print(f"[bold green]Support bundle exported to {out}[/bold green]")

        await run_with_client(export_bundle)

    asyncio.run(run_cmd())
