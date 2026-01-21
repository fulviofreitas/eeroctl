"""Profile formatting utilities for the Eero CLI.

This module provides formatting functions for displaying user profile data.
"""

from typing import Any, Dict, List, Optional

from eero.models.profile import Profile
from rich.panel import Panel
from rich.table import Table

from .base import (
    DetailLevel,
    build_panel,
    console,
    field,
    field_bool,
)

# ==================== Profile Tables ====================


def create_profiles_table(profiles: List[Profile]) -> Table:
    """Create a table displaying profiles.

    Args:
        profiles: List of Profile objects

    Returns:
        Rich Table object
    """
    table = Table(title="Profiles")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("State", style="green")
    table.add_column("Paused", style="yellow")
    table.add_column("Schedule", style="magenta")
    table.add_column("Content Filter", style="cyan")

    for profile in profiles:
        paused_style = "red" if profile.paused else "green"
        schedule_status = "Enabled" if profile.schedule_enabled else "Disabled"
        content_filter_enabled = (
            "Enabled"
            if profile.content_filter and any(vars(profile.content_filter).values())
            else "Disabled"
        )
        state_value = profile.state.value if profile.state else "Unknown"

        table.add_row(
            profile.id or "N/A",
            profile.name,
            state_value,
            f"[{paused_style}]{'Yes' if profile.paused else 'No'}[/{paused_style}]",
            schedule_status,
            content_filter_enabled,
        )

    return table


def create_profile_devices_table(devices: List[Dict[str, Any]]) -> Table:
    """Create a table displaying devices in a profile.

    Args:
        devices: List of device dictionaries from profile

    Returns:
        Rich Table object
    """
    table = Table(title="Profile Devices")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Nickname", style="blue")
    table.add_column("IP", style="green")
    table.add_column("MAC", style="yellow")
    table.add_column("Connected", style="magenta")
    table.add_column("Type", style="cyan")
    table.add_column("Manufacturer", style="green")
    table.add_column("Connection Type", style="blue")
    table.add_column("Eero Location", style="yellow")

    for device in devices:
        device_id = "Unknown"
        if device.get("url"):
            parts = device["url"].split("/")
            if len(parts) >= 2:
                device_id = parts[-1]

        device_name = (
            device.get("display_name")
            or device.get("hostname")
            or device.get("nickname")
            or "Unknown"
        )
        connected = device.get("connected", False)
        connected_style = "green" if connected else "red"
        source = device.get("source", {})
        eero_location = source.get("location") if source else "Unknown"

        table.add_row(
            device_id,
            device_name,
            device.get("nickname") or "",
            device.get("ip") or "Unknown",
            device.get("mac") or "Unknown",
            f"[{connected_style}]{'Yes' if connected else 'No'}[/{connected_style}]",
            device.get("device_type") or "Unknown",
            device.get("manufacturer") or "Unknown",
            device.get("connection_type") or "Unknown",
            eero_location,
        )

    return table


# ==================== Profile Brief View Panels ====================


def _profile_basic_panel(profile: Profile, extensive: bool = False) -> Panel:
    """Build the basic profile info panel."""
    paused_style = "red" if profile.paused else "green"

    lines = [
        field("Name", profile.name),
        field("ID", profile.id),
    ]

    # State
    state_value = profile.state.value if profile.state else "Unknown"
    state_style = "green" if state_value == "Active" else "yellow"
    lines.append(f"[bold]State:[/bold] [{state_style}]{state_value}[/{state_style}]")

    # Paused status
    lines.append(
        f"[bold]Paused:[/bold] [{paused_style}]{'Yes' if profile.paused else 'No'}[/{paused_style}]"
    )

    # Default profile indicator
    is_default = getattr(profile, "default", False)
    if is_default:
        lines.append("[bold]Default:[/bold] [cyan]Yes[/cyan]")

    if extensive:
        lines.extend(
            [
                field("Devices", profile.device_count),
                field("Connected Devices", profile.connected_device_count),
                field_bool("Premium Enabled", profile.premium_enabled),
                field_bool("Schedule Enabled", profile.schedule_enabled),
            ]
        )
    else:
        lines.append(field_bool("Schedule", profile.schedule_enabled))

        # Content filter summary
        filter_enabled = bool(profile.content_filter and any(vars(profile.content_filter).values()))
        lines.append(field_bool("Content Filter", filter_enabled))

    return build_panel(lines, f"Profile: {profile.name}", "blue")


def _profile_device_summary_panel(profile: Profile) -> Optional[Panel]:
    """Build the device summary panel for brief view."""
    devices = profile.devices
    if not devices:
        return None

    total_devices = len(devices)
    connected_count = sum(1 for d in devices if d.get("connected", False))
    disconnected_count = total_devices - connected_count

    # Count by device type
    device_types: Dict[str, int] = {}
    for device in devices:
        device_type = device.get("device_type", "unknown")
        device_types[device_type] = device_types.get(device_type, 0) + 1

    lines = [
        field("Total Devices", total_devices),
        f"[bold]Connected:[/bold] [green]{connected_count}[/green]",
        f"[bold]Disconnected:[/bold] [dim]{disconnected_count}[/dim]",
    ]

    # Add device type breakdown if there are multiple types
    if len(device_types) > 1:
        lines.append("")
        lines.append("[bold]By Type:[/bold]")
        sorted_types = sorted(device_types.items(), key=lambda x: x[1], reverse=True)
        for dtype, count in sorted_types[:5]:
            dtype_display = dtype.replace("_", " ").title()
            lines.append(f"  • {dtype_display}: {count}")

    return build_panel(lines, "Device Summary", "green")


def _profile_content_filters_panel(profile: Profile) -> Optional[Panel]:
    """Build the content filters panel for brief view."""
    # Try unified_content_filters first
    unified_filters = getattr(profile, "unified_content_filters", None)
    if unified_filters:
        dns_policies = (
            unified_filters.get("dns_policies", {})
            if isinstance(unified_filters, dict)
            else getattr(unified_filters, "dns_policies", {})
        )

        if dns_policies:
            lines = []
            filter_map = {
                "block_gaming_content": "Gaming",
                "block_illegal_content": "Illegal Content",
                "block_messaging_content": "Messaging",
                "block_pornographic_content": "Adult Content",
                "block_social_content": "Social Media",
                "block_shopping_content": "Shopping",
                "block_streaming_content": "Streaming",
                "block_violent_content": "Violent Content",
                "safe_search_enabled": "Safe Search",
                "youtube_restricted": "YouTube Restricted",
            }

            enabled_filters = []
            for key, label in filter_map.items():
                value = (
                    dns_policies.get(key, False)
                    if isinstance(dns_policies, dict)
                    else getattr(dns_policies, key, False)
                )
                if value:
                    enabled_filters.append(label)

            if enabled_filters:
                lines.append("[bold]Blocked Categories:[/bold]")
                for f in enabled_filters:
                    lines.append(f"  • [red]{f}[/red]")
                return build_panel(lines, "Content Filters", "yellow")

    # Fallback to content_filter
    if profile.content_filter:
        filter_enabled = any(vars(profile.content_filter).values())
        if filter_enabled:
            lines = ["[bold]Active Filters:[/bold]"]
            for name, value in vars(profile.content_filter).items():
                if value:
                    display_name = " ".join(word.capitalize() for word in name.split("_"))
                    lines.append(f"  • [red]{display_name}[/red]")
            return build_panel(lines, "Content Filters", "yellow")

    return None


def _profile_dns_security_panel(profile: Profile) -> Optional[Panel]:
    """Build the DNS security panel for brief view."""
    premium_dns = getattr(profile, "premium_dns", None)
    if not premium_dns:
        return None

    dns_policies = (
        premium_dns.get("dns_policies", {})
        if isinstance(premium_dns, dict)
        else getattr(premium_dns, "dns_policies", {})
    )

    ad_block = (
        premium_dns.get("ad_block_settings", {})
        if isinstance(premium_dns, dict)
        else getattr(premium_dns, "ad_block_settings", {})
    )

    lines = []

    # DNS policies
    policy_map = {
        "block_pornographic_content": "Block Adult",
        "block_illegal_content": "Block Illegal",
        "block_violent_content": "Block Violent",
        "safe_search_enabled": "Safe Search",
    }

    for key, label in policy_map.items():
        value = (
            dns_policies.get(key, False)
            if isinstance(dns_policies, dict)
            else getattr(dns_policies, key, False)
        )
        if value:
            lines.append(f"[bold]{label}:[/bold] [green]Enabled[/green]")

    # Ad blocking
    ad_block_enabled = (
        ad_block.get("enabled", False)
        if isinstance(ad_block, dict)
        else getattr(ad_block, "enabled", False)
    )
    if ad_block_enabled:
        lines.append("[bold]Ad Block:[/bold] [green]Enabled[/green]")

    # DNS provider
    dns_provider = (
        premium_dns.get("dns_provider")
        if isinstance(premium_dns, dict)
        else getattr(premium_dns, "dns_provider", None)
    )
    if dns_provider:
        lines.append(field("DNS Provider", dns_provider))

    return build_panel(lines, "DNS Security", "magenta") if lines else None


def _profile_blocked_apps_panel(profile: Profile) -> Optional[Panel]:
    """Build the blocked applications panel."""
    premium_dns = getattr(profile, "premium_dns", None)
    if not premium_dns:
        return None

    blocked_apps = (
        premium_dns.get("blocked_applications", [])
        if isinstance(premium_dns, dict)
        else getattr(premium_dns, "blocked_applications", [])
    )

    if not blocked_apps:
        return None

    lines = ["[bold]Blocked Applications:[/bold]"] + [f"  • {app}" for app in blocked_apps]
    return build_panel(lines, "Blocked Apps", "red")


def _profile_custom_lists_panel(profile: Profile) -> Optional[Panel]:
    """Build the custom block/allow lists panel for brief view."""
    block_list = profile.custom_block_list or []
    allow_list = profile.custom_allow_list or []

    if not block_list and not allow_list:
        return None

    lines = []

    if block_list:
        lines.append(f"[bold]Blocked Domains:[/bold] [red]{len(block_list)}[/red]")
        for domain in block_list[:3]:
            lines.append(f"  • {domain}")
        if len(block_list) > 3:
            lines.append(f"  [dim]... and {len(block_list) - 3} more[/dim]")

    if allow_list:
        if lines:
            lines.append("")
        lines.append(f"[bold]Allowed Domains:[/bold] [green]{len(allow_list)}[/green]")
        for domain in allow_list[:3]:
            lines.append(f"  • {domain}")
        if len(allow_list) > 3:
            lines.append(f"  [dim]... and {len(allow_list) - 3} more[/dim]")

    return build_panel(lines, "Custom Lists", "cyan")


def _profile_schedule_panel(profile: Profile) -> Optional[Panel]:
    """Build the schedule panel."""
    if not profile.schedule_enabled or not profile.schedule_blocks:
        return None

    lines = [
        f"[bold]{', '.join(block.days)}:[/bold] {block.start_time} - {block.end_time}"
        for block in profile.schedule_blocks
    ]
    return build_panel(lines, "Schedule", "green")


# ==================== Main Profile Details Function ====================


def print_profile_details(profile: Profile, detail_level: DetailLevel = "brief") -> None:
    """Print profile information with configurable detail level.

    Args:
        profile: Profile object
        detail_level: "brief" or "full"
    """
    extensive = detail_level == "full"

    # Basic info panel (always shown)
    console.print(_profile_basic_panel(profile, extensive))

    if not extensive:
        # Brief view panels

        # Device summary
        summary_panel = _profile_device_summary_panel(profile)
        if summary_panel:
            console.print(summary_panel)

        # Content filters
        filters_panel = _profile_content_filters_panel(profile)
        if filters_panel:
            console.print(filters_panel)

        # DNS security
        dns_panel = _profile_dns_security_panel(profile)
        if dns_panel:
            console.print(dns_panel)

        # Blocked apps
        apps_panel = _profile_blocked_apps_panel(profile)
        if apps_panel:
            console.print(apps_panel)

        # Custom lists
        lists_panel = _profile_custom_lists_panel(profile)
        if lists_panel:
            console.print(lists_panel)

        # Devices table
        if profile.devices:
            console.print(create_profile_devices_table(profile.devices))
        else:
            console.print("[bold yellow]No devices in this profile[/bold yellow]")

    else:
        # Extensive view panels

        # Schedule
        schedule_panel = _profile_schedule_panel(profile)
        if schedule_panel:
            console.print(schedule_panel)

        # Content filter details
        if profile.content_filter:
            filter_enabled = any(vars(profile.content_filter).values())
            if filter_enabled:
                filter_settings = []
                for name, value in vars(profile.content_filter).items():
                    if value:
                        display_name = " ".join(word.capitalize() for word in name.split("_"))
                        filter_settings.append(f"[bold]{display_name}:[/bold] Enabled")
                console.print(build_panel(filter_settings, "Content Filtering", "yellow"))

        # Block/Allow lists (full)
        if profile.custom_block_list:
            console.print(build_panel(profile.custom_block_list, "Blocked Domains", "red"))
        if profile.custom_allow_list:
            console.print(build_panel(profile.custom_allow_list, "Allowed Domains", "green"))
