"""Multi-static-IP WAN read for the Eero CLI.

Command:
- eero network wan multistaticip show -- get_multistaticip (client.py:3032)

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
from typing import Optional

import click
from eero import EeroClient
from eero.exceptions import EeroNotFoundException

from ...formatting.wan import print_multistaticip, print_multistaticip_not_configured
from ...options import apply_options, common_options
from ...transformers.wan import extract_multistaticip
from ...utils import run_with_client

MULTISTATICIP_NOT_FOUND_ERROR_CODE = "error.network.multistaticip_not_found"
"""The SDK-observed error code for "feature absent" (`eero/api/wan.py:50-51`).

Any other `EeroNotFoundException` here means a wrong network id and is left
to propagate to the standard exit-5 mapping (Q7).
"""


@click.group(name="wan")
@click.pass_context
def wan_group(ctx: click.Context) -> None:
    """View WAN configuration.

    \b
    Commands:
      multistaticip - Multi-static-IP configuration
    """
    pass


@wan_group.group(name="multistaticip")
@click.pass_context
def multistaticip_group(ctx: click.Context) -> None:
    """View multi-static-IP configuration.

    \b
    Commands:
      show - Multi-static-IP configuration (or "not configured")
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
