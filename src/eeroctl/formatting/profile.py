"""Profile formatting utilities for the Eero CLI.

This module provides formatting functions for displaying profile data.
Updated to work with raw dict data from transformers.
"""

from typing import Any, Dict, List, Optional, Union

from rich.panel import Panel
from rich.table import Table

from ..transformers.profile import normalize_profile
from .base import (
    DetailLevel,
    build_panel,
    console,
    field,
    field_bool,
)

# ==================== Profile Table ====================


def create_profiles_table(profiles: List[Dict[str, Any]]) -> Table:
    """Create a table displaying profiles.

    Args:
        profiles: List of profile dicts (already transformed)

    Returns:
        Rich Table object
    """
    table = Table(title="Profiles")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Paused", style="magenta")
    table.add_column("Devices", style="yellow")
    table.add_column("Schedule", style="green")
    table.add_column("Default", style="blue")

    for profile in profiles:
        p = normalize_profile(profile) if "_raw" not in profile else profile

        paused = "[red]Yes[/red]" if p.get("paused") else "[green]No[/green]"
        schedule = "[green]Yes[/green]" if p.get("schedule_enabled") else "[dim]No[/dim]"
        default = "[cyan]Yes[/cyan]" if p.get("default") else "[dim]No[/dim]"

        table.add_row(
            p.get("id") or "Unknown",
            p.get("name") or "Unknown",
            paused,
            str(p.get("device_count", 0)),
            schedule,
            default,
        )

    return table


def create_profile_devices_table(devices: List[Dict[str, Any]]) -> Table:
    """Create a table displaying devices in a profile.

    Args:
        devices: List of device dicts

    Returns:
        Rich Table object
    """
    table = Table(title="Profile Devices")
    table.add_column("Name", style="cyan")
    table.add_column("MAC", style="yellow")
    table.add_column("IP", style="green")
    table.add_column("Connected", style="magenta")

    for device in devices:
        name = (
            device.get("nickname")
            or device.get("hostname")
            or device.get("display_name")
            or "Unknown"
        )
        mac = device.get("mac") or "Unknown"
        ip = device.get("ip") or device.get("ipv4") or "Unknown"
        connected = "[green]Yes[/green]" if device.get("connected") else "[dim]No[/dim]"

        table.add_row(name, mac, ip, connected)

    return table


# ==================== Profile Brief View Panels ====================


def _profile_basic_panel(profile: Dict[str, Any], extensive: bool = False) -> Panel:
    """Build the basic profile info panel."""
    name = profile.get("name", "Unknown")

    lines = [
        field("Name", name),
        field_bool("Paused", profile.get("paused")),
        field_bool("Default", profile.get("default")),
        field("Devices", profile.get("device_count", 0)),
        field("Connected Devices", profile.get("connected_device_count", 0)),
        field_bool("Schedule Enabled", profile.get("schedule_enabled")),
    ]

    if extensive:
        lines.extend(
            [
                field("State", profile.get("state")),
            ]
        )

    return build_panel(lines, f"Profile: {name}", "blue")


def _profile_content_filter_panel(profile: Dict[str, Any]) -> Optional[Panel]:
    """Build the content filter panel."""
    content_filter = profile.get("content_filter", {})
    if not content_filter:
        return None

    lines = [
        field_bool("Safe Search", content_filter.get("safe_search")),
        field_bool("YouTube Restricted", content_filter.get("youtube_restricted")),
        field_bool("Block Adult Content", content_filter.get("block_adult")),
        field_bool("Block Illegal Content", content_filter.get("block_illegal")),
        field_bool("Block Violent Content", content_filter.get("block_violent")),
    ]

    return build_panel(lines, "Content Filters", "magenta")


def _profile_custom_lists_panel(profile: Dict[str, Any]) -> Optional[Panel]:
    """Build the custom block/allow lists panel."""
    block_list = profile.get("custom_block_list", [])
    allow_list = profile.get("custom_allow_list", [])

    if not block_list and not allow_list:
        return None

    lines = []

    if block_list:
        lines.append(f"[bold]Blocked Domains:[/bold] {len(block_list)}")
        for domain in block_list[:5]:  # Show first 5
            lines.append(f"  • {domain}")
        if len(block_list) > 5:
            lines.append(f"  [dim]... and {len(block_list) - 5} more[/dim]")

    if allow_list:
        lines.append(f"[bold]Allowed Domains:[/bold] {len(allow_list)}")
        for domain in allow_list[:5]:  # Show first 5
            lines.append(f"  • {domain}")
        if len(allow_list) > 5:
            lines.append(f"  [dim]... and {len(allow_list) - 5} more[/dim]")

    return build_panel(lines, "Custom Lists", "yellow")


# ==================== List Output Data ====================


def get_profile_list_data(profile: Union[Dict[str, Any], Any]) -> Dict[str, Any]:
    """Get curated profile data for list output.

    Returns the same fields shown in the table output, as a flat dictionary.

    Args:
        profile: Profile dict or model object

    Returns:
        Dictionary with curated fields for list output
    """
    # Normalize to dict if needed
    if isinstance(profile, dict):
        p = normalize_profile(profile) if "_raw" not in profile else profile
    else:
        if hasattr(profile, "model_dump"):
            p = normalize_profile(profile.model_dump())
        else:
            p = normalize_profile(vars(profile))

    data = {
        "Name": p.get("name"),
        "Paused": "Yes" if p.get("paused") else "No",
        "Default": "Yes" if p.get("default") else "No",
        "Devices": p.get("device_count", 0),
        "Connected Devices": p.get("connected_device_count", 0),
        "Schedule Enabled": "Yes" if p.get("schedule_enabled") else "No",
        "State": p.get("state"),
    }

    # Content filter
    content_filter = p.get("content_filter", {})
    if content_filter:
        data["Safe Search"] = "Enabled" if content_filter.get("safe_search_enabled") else "Disabled"

    # Count blocked apps
    blocked_apps = p.get("blocked_applications", [])
    if blocked_apps:
        data["Blocked Apps"] = len(blocked_apps)

    return data


# ==================== Main Profile Details Function ====================


def print_profile_details(
    profile: Union[Dict[str, Any], Any], detail_level: DetailLevel = "brief"
) -> None:
    """Print profile information with configurable detail level.

    Args:
        profile: Profile dict or model object
        detail_level: "brief" or "full"
    """
    # Normalize to dict if needed
    if isinstance(profile, dict):
        p = normalize_profile(profile) if "_raw" not in profile else profile
    else:
        # Legacy model support - convert to dict
        if hasattr(profile, "model_dump"):
            p = normalize_profile(profile.model_dump())
        else:
            p = normalize_profile(vars(profile))

    extensive = detail_level == "full"

    # Basic info panel (always shown)
    console.print(_profile_basic_panel(p, extensive))

    # Content filter panel
    filter_panel = _profile_content_filter_panel(p)
    if filter_panel:
        console.print(filter_panel)

    # Custom lists panel
    lists_panel = _profile_custom_lists_panel(p)
    if lists_panel:
        console.print(lists_panel)
