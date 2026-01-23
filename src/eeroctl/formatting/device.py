"""Device formatting utilities for the Eero CLI.

This module provides formatting functions for displaying connected device data.
Updated to work with raw dict data from transformers.
"""

from typing import Any, Dict, List, Optional, Union

from rich.panel import Panel
from rich.table import Table

from ..transformers.device import normalize_device
from .base import (
    DetailLevel,
    build_panel,
    console,
    field,
    field_bool,
    field_status,
    format_datetime,
    format_device_status,
)

# ==================== Device Table ====================


def create_devices_table(devices: List[Dict[str, Any]]) -> Table:
    """Create a table displaying network devices.

    Args:
        devices: List of device dicts (already transformed)

    Returns:
        Rich Table object
    """
    table = Table(title="Connected Devices")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Nickname", style="blue")
    table.add_column("IP", style="green")
    table.add_column("MAC", style="yellow")
    table.add_column("Status", style="magenta")
    table.add_column("Type", style="cyan")
    table.add_column("Manufacturer", style="green")
    table.add_column("Connection Type", style="blue")
    table.add_column("Eero Location", style="yellow")

    for device in devices:
        dev = normalize_device(device) if "_raw" not in device else device

        # Determine status
        if dev.get("connected"):
            if dev.get("blocked"):
                status = "blocked"
            else:
                status = "connected"
        else:
            status = "disconnected"

        status_text, status_style = format_device_status(status)
        device_name = (
            dev.get("display_name") or dev.get("hostname") or dev.get("nickname") or "Unknown"
        )
        ip_address = dev.get("ip") or dev.get("ipv4") or "Unknown"
        mac_address = dev.get("mac") or "Unknown"
        connection_type = dev.get("connection_type") or "Unknown"
        eero_location = dev.get("source_location") or "Unknown"

        table.add_row(
            dev.get("id") or "Unknown",
            device_name,
            dev.get("nickname") or "",
            ip_address,
            mac_address,
            f"[{status_style}]{status_text}[/{status_style}]",
            dev.get("device_type") or "Unknown",
            dev.get("manufacturer") or "Unknown",
            connection_type,
            eero_location,
        )

    return table


# ==================== Device Brief View Panels ====================


def _device_basic_panel(device: Dict[str, Any], extensive: bool = False) -> Panel:
    """Build the basic device info panel."""
    # Determine status
    if device.get("connected"):
        if device.get("blocked"):
            status = "blocked"
        else:
            status = "connected"
    else:
        status = "disconnected"

    status_text, status_style = format_device_status(status)
    device_name = (
        device.get("display_name") or device.get("hostname") or device.get("nickname") or "Unknown"
    )
    ip_address = device.get("ip") or device.get("ipv4") or "Unknown"
    mac_address = device.get("mac") or "Unknown"

    # Profile display
    profile_display = "None"
    profile = device.get("profile", {})
    if profile:
        profile_name = profile.get("name") or "Unknown" if isinstance(profile, dict) else "Unknown"
        profile_id = device.get("profile_id") or "Unknown"
        profile_display = f"{profile_name} ({profile_id})"
    elif device.get("profile_id"):
        profile_display = f"Unknown ({device.get('profile_id')})"

    lines = [
        field("Name", device_name),
        field("Nickname", device.get("nickname"), "None"),
        field("MAC Address", mac_address),
        field("IP Address", ip_address),
        field("Hostname", device.get("hostname")),
        field_status("Status", status_text, status_style),
        field("Manufacturer", device.get("manufacturer")),
        field("Model", device.get("model_name")),
        field("Type", device.get("device_type")),
        field_bool("Connected", device.get("connected")),
        field_bool("Guest", device.get("is_guest")),
        field_bool("Paused", device.get("paused")),
        field_bool("Blocked", device.get("blocked")),
        field("Profile", profile_display),
        field("Connection Type", device.get("connection_type")),
    ]

    if extensive:
        lines.append(field("Eero Location", device.get("source_location") or "Unknown"))

    return build_panel(lines, f"Device: {device_name}", "blue")


def _device_connectivity_panel(device: Dict[str, Any]) -> Optional[Panel]:
    """Build the connectivity panel for brief view."""
    connectivity = device.get("connectivity", {})
    if not connectivity:
        return None

    lines = []

    # Signal strength with visual indicator
    signal = connectivity.get("signal") if isinstance(connectivity, dict) else None
    if signal:
        try:
            signal_val = int(str(signal).replace(" dBm", "").replace("dBm", ""))
            if signal_val >= -50:
                signal_style = "green"
            elif signal_val >= -70:
                signal_style = "yellow"
            else:
                signal_style = "red"
            lines.append(f"[bold]Signal:[/bold] [{signal_style}]{signal}[/{signal_style}]")
        except (ValueError, AttributeError):
            lines.append(field("Signal", signal))

    # Score bars with visual indicator
    score_bars = connectivity.get("score_bars") if isinstance(connectivity, dict) else None
    if score_bars is not None:
        bars_style = "green" if score_bars >= 4 else "yellow" if score_bars >= 2 else "red"
        filled = "●" * score_bars
        empty = "○" * (5 - score_bars)
        lines.append(
            f"[bold]Quality:[/bold] [{bars_style}]{filled}{empty} ({score_bars}/5)[/{bars_style}]"
        )

    # Frequency
    frequency = connectivity.get("frequency") if isinstance(connectivity, dict) else None
    if frequency:
        band = "5 GHz" if frequency > 3000 else "2.4 GHz"
        lines.append(field("Frequency", f"{frequency} MHz ({band})"))

    # Bitrates
    rx_bitrate = connectivity.get("rx_bitrate") if isinstance(connectivity, dict) else None
    if rx_bitrate:
        lines.append(field("RX Bitrate", rx_bitrate))

    tx_bitrate = connectivity.get("tx_bitrate") if isinstance(connectivity, dict) else None
    if tx_bitrate:
        lines.append(field("TX Bitrate", tx_bitrate))

    return build_panel(lines, "Connectivity", "cyan") if lines else None


def _device_timing_panel(device: Dict[str, Any]) -> Optional[Panel]:
    """Build the timing panel for brief view."""
    last_active = device.get("last_active")
    first_active = device.get("first_active")

    if not (last_active or first_active):
        return None

    lines = []

    if last_active:
        lines.append(field("Last Active", format_datetime(last_active)))

    if first_active:
        lines.append(field("First Seen", format_datetime(first_active)))

    return build_panel(lines, "Activity", "yellow")


# ==================== List Output Data ====================


def _normalize_device_data(device: Union[Dict[str, Any], Any]) -> Dict[str, Any]:
    """Normalize device data to a consistent dict format."""
    if isinstance(device, dict):
        return normalize_device(device) if "_raw" not in device else device
    if hasattr(device, "model_dump"):
        return normalize_device(device.model_dump())
    return normalize_device(vars(device))


def get_device_show_fields(device: Union[Dict[str, Any], Any]) -> List[tuple]:
    """Get the canonical list of fields to display for device show.

    This is the SINGLE SOURCE OF TRUTH for device show output fields.
    Both table (rich panels) and list (text) output use this.

    Args:
        device: Device dict or model object

    Returns:
        List of (label, value) tuples
    """
    dev = _normalize_device_data(device)

    # Determine status
    if dev.get("connected"):
        status = "blocked" if dev.get("blocked") else "connected"
    else:
        status = "disconnected"

    device_name = dev.get("display_name") or dev.get("hostname") or dev.get("nickname") or "Unknown"

    fields = [
        # Basic info
        ("Name", device_name),
        ("Nickname", dev.get("nickname")),
        ("Status", status),
        ("IP Address", dev.get("ip") or dev.get("ipv4")),
        ("MAC Address", dev.get("mac")),
        ("Device Type", dev.get("device_type")),
        ("Manufacturer", dev.get("manufacturer")),
        ("Connection Type", dev.get("connection_type")),
        ("Connected Eero", dev.get("source_location")),
        ("Blocked", "Yes" if dev.get("blocked") else "No"),
        ("Paused", "Yes" if dev.get("paused") else "No"),
    ]

    # Activity times
    last_active = dev.get("last_active")
    if last_active:
        fields.append(("Last Active", format_datetime(last_active)))

    first_active = dev.get("first_active")
    if first_active:
        fields.append(("First Seen", format_datetime(first_active)))

    # Connectivity info
    connectivity = dev.get("connectivity", {})
    if connectivity and isinstance(connectivity, dict):
        if connectivity.get("signal"):
            fields.append(("Signal", f"{connectivity.get('signal')} dBm"))
        if connectivity.get("frequency"):
            freq = connectivity.get("frequency")
            band = "5 GHz" if freq > 3000 else "2.4 GHz"
            fields.append(("Frequency", f"{freq} MHz ({band})"))

    return fields


def get_device_list_data(device: Union[Dict[str, Any], Any]) -> Dict[str, Any]:
    """Get curated device data for list output.

    Uses get_device_show_fields() as the single source of truth.

    Args:
        device: Device dict or model object

    Returns:
        Dictionary with curated fields for list output
    """
    return {label: value for label, value in get_device_show_fields(device)}


# ==================== Main Device Details Function ====================


def print_device_details(
    device: Union[Dict[str, Any], Any], detail_level: DetailLevel = "brief"
) -> None:
    """Print device information with configurable detail level.

    Args:
        device: Device dict or model object
        detail_level: "brief" or "full"
    """
    # Normalize to dict if needed
    if isinstance(device, dict):
        dev = normalize_device(device) if "_raw" not in device else device
    else:
        # Legacy model support - convert to dict
        if hasattr(device, "model_dump"):
            dev = normalize_device(device.model_dump())
        else:
            dev = normalize_device(vars(device))

    extensive = detail_level == "full"

    # Basic info panel (always shown)
    console.print(_device_basic_panel(dev, extensive))

    # Connectivity info
    connectivity_panel = _device_connectivity_panel(dev)
    if connectivity_panel:
        console.print(connectivity_panel)

    # Activity/timing
    timing_panel = _device_timing_panel(dev)
    if timing_panel:
        console.print(timing_panel)
