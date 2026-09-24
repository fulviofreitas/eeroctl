"""Rendering for the `network entitlements *` command family.

Response shapes are undocumented (migration plan §4); each function here is a
thin, schema-carrying wrapper over the generic key/value renderer
(`formatting/generic.py`) until a live sample justifies a dedicated table
(§5.3 of the migration plan).
"""

from typing import Any

from ..context import EeroCliContext
from .generic import render_generic


def print_entitlements_show(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network entitlements show` (`get_entitlement_features`)."""
    render_generic(cli_ctx, data, "eero.network.entitlements.show/v1")


def print_entitlements_upsell(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network entitlements upsell` (`get_upsell_features`)."""
    render_generic(cli_ctx, data, "eero.network.entitlements.upsell/v1")


def print_entitlements_capabilities(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network entitlements capabilities` (`get_model_capabilities`)."""
    render_generic(cli_ctx, data, "eero.network.entitlements.capabilities/v1")
