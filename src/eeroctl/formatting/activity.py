"""Rendering for `activity devices|device|profiles|profile` insights reads.

<!-- unverified shape --> Per-device/per-profile breakdown shapes are not
independently confirmed (no live sample captured yet, migration plan §5.3),
so all five go through the generic key/value renderer for every format.
"""

from typing import Any

from ..context import EeroCliContext
from .generic import render_generic


def print_devices_insights(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `activity devices` (`get_devices_insights`)."""
    render_generic(cli_ctx, data, "eero.activity.devices/v1")


def print_device_insights(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `activity device <id>` (`get_device_insights`)."""
    render_generic(cli_ctx, data, "eero.activity.device/v1")


def print_profiles_insights(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `activity profiles` (`get_profiles_insights`)."""
    render_generic(cli_ctx, data, "eero.activity.profiles/v1")


def print_profile_insights(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `activity profile <id>` (`get_profile_insights`)."""
    render_generic(cli_ctx, data, "eero.activity.profile/v1")


def print_profile_devices_insights(cli_ctx: EeroCliContext, data: Any) -> None:
    """Render `activity profile <id> --devices` (`get_profile_devices_insights`)."""
    render_generic(cli_ctx, data, "eero.activity.profile.devices/v1")
