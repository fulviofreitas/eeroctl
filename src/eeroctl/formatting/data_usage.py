"""Rendering for `network usage *` (closes #46).

<!-- unverified shape --> Response shapes are undocumented beyond the
envelope (no live sample captured yet, migration plan §5.3), so every
command in this family goes through the generic key/value renderer.
"""

from typing import Any

from ..context import EeroCliContext
from .generic import render_generic


def print_data_usage_summary(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network usage summary` (`get_data_usage`)."""
    render_generic(cli_ctx, data, "eero.network.usage.summary/v1")


def print_data_usage_breakdown(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network usage breakdown` (`get_data_usage_breakdown`)."""
    render_generic(cli_ctx, data, "eero.network.usage.breakdown/v1")


def print_devices_data_usage(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network usage devices` (`get_devices_data_usage`)."""
    render_generic(cli_ctx, data, "eero.network.usage.devices/v1")


def print_device_data_usage(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network usage device <mac>` (`get_device_data_usage`)."""
    render_generic(cli_ctx, data, "eero.network.usage.device/v1")


def print_eeros_data_usage_summary(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network usage eeros` (`get_eeros_data_usage_summary`)."""
    render_generic(cli_ctx, data, "eero.network.usage.eeros/v1")


def print_eero_data_usage(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network usage eero <id>` (`get_eero_data_usage`)."""
    render_generic(cli_ctx, data, "eero.network.usage.eero/v1")


def print_profile_data_usage(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network usage profile <id>` (`get_profile_data_usage`)."""
    render_generic(cli_ctx, data, "eero.network.usage.profile/v1")


def print_unprofiled_devices_data_usage(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network usage unprofiled` (`get_unprofiled_devices_data_usage`)."""
    render_generic(cli_ctx, data, "eero.network.usage.unprofiled/v1")


def print_unprofiled_data_usage_summary(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network usage unprofiled --summary` (`get_unprofiled_data_usage_summary`)."""
    render_generic(cli_ctx, data, "eero.network.usage.unprofiled.summary/v1")


def print_data_usage_report_settings(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `network usage report show` (`get_data_usage_report_settings`)."""
    render_generic(cli_ctx, data, "eero.network.usage.report.show/v1")
