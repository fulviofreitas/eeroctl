"""Device formatting utilities for the Eero CLI.

This module provides formatting functions for displaying connected device data.
"""

from typing import List, Optional

from eero.models.device import Device
from rich.panel import Panel
from rich.table import Table

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


def create_devices_table(devices: List[Device]) -> Table:
    """Create a table displaying network devices.

    Args:
        devices: List of Device objects

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
    table.add_column("Interface", style="cyan")

    for device in devices:
        status_text, status_style = format_device_status(device.status)
        device_name = device.display_name or device.hostname or device.nickname or "Unknown"
        ip_address = device.ip or device.ipv4 or "Unknown"
        mac_address = device.mac or "Unknown"
        connection_type = device.connection_type or "Unknown"
        eero_location = device.source.location if device.source else "Unknown"

        interface_info = ""
        if device.interface:
            if device.interface.frequency and device.interface.frequency_unit:
                interface_info = f"{device.interface.frequency} {device.interface.frequency_unit}"
            elif device.interface.frequency:
                interface_info = f"{device.interface.frequency} GHz"
        elif device.connectivity and device.connectivity.frequency:
            interface_info = f"{device.connectivity.frequency} MHz"

        table.add_row(
            device.id or "Unknown",
            device_name,
            device.nickname or "",
            ip_address,
            mac_address,
            f"[{status_style}]{status_text}[/{status_style}]",
            device.device_type or "Unknown",
            device.manufacturer or "Unknown",
            connection_type,
            eero_location,
            interface_info or "Unknown",
        )

    return table


# ==================== Device Brief View Panels ====================


def _device_basic_panel(device: Device, extensive: bool = False) -> Panel:
    """Build the basic device info panel."""
    status_text, status_style = format_device_status(device.status)
    device_name = device.display_name or device.hostname or device.nickname or "Unknown"
    ip_address = device.ip or device.ipv4 or "Unknown"
    mac_address = device.mac or "Unknown"

    # Profile display
    profile_display = "None"
    if device.profile:
        profile_name = device.profile.name or "Unknown"
        profile_id = device.profile_id or "Unknown"
        profile_display = f"{profile_name} ({profile_id})"
    elif device.profile_id:
        profile_display = f"Unknown ({device.profile_id})"

    lines = [
        field("Name", device_name),
        field("Nickname", device.nickname, "None"),
        field("MAC Address", mac_address),
        field("IP Address", ip_address),
        field("Hostname", device.hostname),
        field_status("Status", status_text, status_style),
        field("Manufacturer", device.manufacturer),
        field("Model", device.model_name),
        field("Type", device.device_type),
        field_bool("Connected", device.connected),
        field_bool("Guest", device.is_guest),
        field_bool("Paused", device.paused),
        field_bool("Blocked", device.blacklisted),
        field("Profile", profile_display),
        field("Connection Type", device.connection_type),
    ]

    if extensive:
        lines.append(field("Eero Location", device.source.location if device.source else "Unknown"))

    return build_panel(lines, f"Device: {device_name}", "blue")


def _device_connected_eero_panel(device: Device) -> Optional[Panel]:
    """Build the connected eero panel for brief view."""
    source = device.source
    if not source:
        return None

    location = getattr(source, "location", None)
    model = getattr(source, "model", None)
    display_name = getattr(source, "display_name", None)
    is_gateway = getattr(source, "is_gateway", False)

    lines = []

    if location:
        lines.append(field("Location", location))
    if display_name and display_name != location:
        lines.append(field("Eero Name", display_name))
    if model:
        lines.append(field("Model", model))
    if is_gateway:
        lines.append("[bold]Role:[/bold] [cyan]Gateway[/cyan]")

    return build_panel(lines, "Connected Eero", "green") if lines else None


def _device_connectivity_panel(device: Device) -> Optional[Panel]:
    """Build the connectivity panel for brief view."""
    connectivity = device.connectivity
    if not connectivity:
        return None

    lines = []

    # Signal strength with visual indicator
    signal = getattr(connectivity, "signal", None)
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
    score_bars = getattr(connectivity, "score_bars", None)
    if score_bars is not None:
        bars_style = "green" if score_bars >= 4 else "yellow" if score_bars >= 2 else "red"
        filled = "●" * score_bars
        empty = "○" * (5 - score_bars)
        lines.append(
            f"[bold]Quality:[/bold] [{bars_style}]{filled}{empty} ({score_bars}/5)[/{bars_style}]"
        )

    # Frequency
    frequency = getattr(connectivity, "frequency", None)
    if frequency:
        band = "5 GHz" if frequency > 3000 else "2.4 GHz"
        lines.append(field("Frequency", f"{frequency} MHz ({band})"))

    # Bitrates
    rx_bitrate = getattr(connectivity, "rx_bitrate", None)
    if rx_bitrate:
        lines.append(field("RX Bitrate", rx_bitrate))

    tx_bitrate = getattr(connectivity, "tx_bitrate", None)
    if tx_bitrate:
        lines.append(field("TX Bitrate", tx_bitrate))

    # Channel width from rx_rate_info
    rx_rate_info = getattr(connectivity, "rx_rate_info", None)
    if rx_rate_info:
        channel_width = rx_rate_info.get("channel_width", "")
        if channel_width:
            width_display = channel_width.replace("WIDTH_", "").replace("MHz", " MHz")
            lines.append(field("Channel Width", width_display))

        phy_type = rx_rate_info.get("phy_type", "")
        if phy_type:
            phy_map = {
                "HE": "WiFi 6 (802.11ax)",
                "VHT": "WiFi 5 (802.11ac)",
                "HT": "WiFi 4 (802.11n)",
            }
            lines.append(field("PHY Type", phy_map.get(phy_type, phy_type)))

    return build_panel(lines, "Connectivity", "cyan") if lines else None


def _device_wifi_panel(device: Device) -> Optional[Panel]:
    """Build the WiFi details panel for brief view."""
    wireless = getattr(device, "wireless", False)
    connection_type = device.connection_type
    if not wireless and connection_type != "wireless":
        return None

    lines = []

    ssid = getattr(device, "ssid", None)
    if ssid:
        lines.append(field("Network (SSID)", ssid))

    interface = device.interface
    if interface:
        freq = getattr(interface, "frequency", None)
        freq_unit = getattr(interface, "frequency_unit", None)
        if freq:
            freq_display = f"{freq} {freq_unit}" if freq_unit else f"{freq} GHz"
            lines.append(field("Band", freq_display))

    channel = getattr(device, "channel", None)
    if channel:
        lines.append(field("Channel", channel))

    auth = getattr(device, "auth", None)
    if auth:
        auth_display = auth.upper() if auth else "Unknown"
        lines.append(field("Security", auth_display))

    subnet_kind = getattr(device, "subnet_kind", None)
    if subnet_kind:
        lines.append(field("Subnet", subnet_kind))

    return build_panel(lines, "WiFi Details", "magenta") if lines else None


def _device_timing_panel(device: Device) -> Optional[Panel]:
    """Build the timing panel for brief view."""
    last_active = getattr(device, "last_active", None)
    first_active = getattr(device, "first_active", None)

    if not (last_active or first_active):
        return None

    lines = []

    if last_active:
        lines.append(field("Last Active", format_datetime(last_active)))

    if first_active:
        lines.append(field("First Seen", format_datetime(first_active)))

    return build_panel(lines, "Activity", "yellow")


def _device_ips_panel(device: Device) -> Optional[Panel]:
    """Build the IP addresses panel for brief view."""
    ips = getattr(device, "ips", [])

    if not ips or len(ips) <= 1:
        return None

    lines = ["[bold]All IP Addresses:[/bold]"]
    for ip in ips:
        if ":" in str(ip):
            lines.append(f"  • {ip} [dim](IPv6)[/dim]")
        else:
            lines.append(f"  • {ip}")

    return build_panel(lines, "IP Addresses", "blue")


def _device_connection_panel(device: Device) -> Optional[Panel]:
    """Build the connection details panel for brief view."""
    connection = device.connection
    if not connection:
        return None

    lines = [
        field("Type", connection.type),
        field("Connected To", connection.connected_to),
        field("Connected Via", connection.connected_via),
    ]

    if connection.frequency:
        lines.append(field("Frequency", connection.frequency))
    if connection.signal_strength is not None:
        lines.append(field("Signal Strength", connection.signal_strength))
    if connection.tx_rate is not None:
        lines.append(field("TX Rate", f"{connection.tx_rate} Mbps"))
    if connection.rx_rate is not None:
        lines.append(field("RX Rate", f"{connection.rx_rate} Mbps"))

    return build_panel(lines, "Connection Details", "green")


def _device_tags_panel(device: Device) -> Optional[Panel]:
    """Build the tags panel."""
    tags = device.tags
    if not tags:
        return None

    lines = [f"[bold]{tag.name}:[/bold] {tag.color or 'No color'}" for tag in tags]
    return build_panel(lines, "Tags", "yellow")


# ==================== Device Extensive View Panels ====================


def _device_connectivity_extensive_panel(device: Device) -> Optional[Panel]:
    """Build the connectivity panel for extensive view."""
    connectivity = device.connectivity
    if not connectivity:
        return None

    channel_width = "N/A"
    if connectivity.rx_rate_info and "channel_width" in connectivity.rx_rate_info:
        channel_width = connectivity.rx_rate_info["channel_width"]

    lines = [
        field("Signal", connectivity.signal, "N/A"),
        field("Score", connectivity.score, "N/A"),
        field("Score Bars", connectivity.score_bars, "N/A"),
        field("Frequency", f"{connectivity.frequency or 'N/A'} MHz"),
        field("RX Bitrate", connectivity.rx_bitrate, "N/A"),
        field("Channel Width", channel_width),
    ]
    return build_panel(lines, "Connectivity", "green")


def _device_interface_panel(device: Device) -> Optional[Panel]:
    """Build the interface panel for extensive view."""
    interface = device.interface
    if not interface:
        return None

    lines = [
        field(
            "Frequency",
            f"{interface.frequency or 'N/A'} {interface.frequency_unit or ''}",
        ),
        field("Channel", device.channel, "N/A"),
        field("Authentication", device.auth, "N/A"),
    ]
    return build_panel(lines, "Interface", "cyan")


# ==================== Main Device Details Function ====================


def print_device_details(device: Device, detail_level: DetailLevel = "brief") -> None:
    """Print device information with configurable detail level.

    Args:
        device: Device object
        detail_level: "brief" or "full"
    """
    extensive = detail_level == "full"

    # Basic info panel (always shown)
    console.print(_device_basic_panel(device, extensive))

    if not extensive:
        # Brief view panels

        # Connected eero info
        eero_panel = _device_connected_eero_panel(device)
        if eero_panel:
            console.print(eero_panel)

        # Connectivity info
        connectivity_panel = _device_connectivity_panel(device)
        if connectivity_panel:
            console.print(connectivity_panel)

        # WiFi details
        wifi_panel = _device_wifi_panel(device)
        if wifi_panel:
            console.print(wifi_panel)

        # Activity/timing
        timing_panel = _device_timing_panel(device)
        if timing_panel:
            console.print(timing_panel)

        # IP addresses (if multiple)
        ips_panel = _device_ips_panel(device)
        if ips_panel:
            console.print(ips_panel)

        # Connection details (if available)
        connection_panel = _device_connection_panel(device)
        if connection_panel:
            console.print(connection_panel)

        # Tags
        tags_panel = _device_tags_panel(device)
        if tags_panel:
            console.print(tags_panel)

    else:
        # Extensive view panels

        # Connectivity
        connectivity_panel = _device_connectivity_extensive_panel(device)
        if connectivity_panel:
            console.print(connectivity_panel)

        # Interface
        interface_panel = _device_interface_panel(device)
        if interface_panel:
            console.print(interface_panel)
