"""Eero device formatting utilities for the Eero CLI.

This module provides formatting functions for displaying Eero device data.
Updated to work with raw dict data from transformers.
"""

from typing import Any, Dict, List, Optional, Union

from rich.panel import Panel
from rich.table import Table

from ..transformers.eero import normalize_eero
from .base import (
    DetailLevel,
    build_panel,
    console,
    field,
    field_bool,
    field_status,
    format_eero_status,
)

# ==================== Eero Table ====================


def create_eeros_table(eeros: List[Dict[str, Any]]) -> Table:
    """Create a table displaying Eero devices.

    Args:
        eeros: List of eero dicts (already transformed)

    Returns:
        Rich Table object
    """
    table = Table(title="Eero Devices")
    table.add_column("ID", style="dim")
    table.add_column("Name/Location", style="cyan")
    table.add_column("Model", style="blue")
    table.add_column("Status", style="green")
    table.add_column("Role", style="magenta")
    table.add_column("Clients", style="yellow")
    table.add_column("Firmware", style="cyan")

    for eero in eeros:
        e = normalize_eero(eero) if "_raw" not in eero else eero

        status = e.get("status", "unknown")
        status_text, status_style = format_eero_status(status)

        role = "Gateway" if e.get("is_gateway") else "Leaf"
        clients = str(e.get("connected_clients_count", 0))
        name = e.get("name") or e.get("location") or "Unknown"

        table.add_row(
            e.get("id") or "Unknown",
            name,
            e.get("model") or "Unknown",
            f"[{status_style}]{status_text}[/{status_style}]",
            role,
            clients,
            e.get("os_version") or "Unknown",
        )

    return table


# ==================== Eero Brief View Panels ====================


def _eero_basic_panel(eero: Dict[str, Any], extensive: bool = False) -> Panel:
    """Build the basic eero info panel."""
    status = eero.get("status", "unknown")
    status_text, status_style = format_eero_status(status)
    name = eero.get("name") or eero.get("location") or "Unknown"

    lines = [
        field("Name/Location", name),
        field("Model", eero.get("model")),
        field("Model Number", eero.get("model_number")),
        field("Serial", eero.get("serial")),
        field_status("Status", status_text, status_style),
        field_bool("Gateway", eero.get("is_gateway")),
        field_bool("Wired", eero.get("wired")),
        field("Firmware", eero.get("os_version")),
        field("Clients", eero.get("connected_clients_count", 0)),
    ]

    if extensive:
        lines.extend(
            [
                field("MAC Address", eero.get("mac_address")),
                field("IP Address", eero.get("ip_address")),
                field_bool("Update Available", eero.get("update_available")),
            ]
        )

    return build_panel(lines, f"Eero: {name}", "blue")


def _eero_led_panel(eero: Dict[str, Any]) -> Optional[Panel]:
    """Build the LED/nightlight panel."""
    led_on = eero.get("led_on")
    nightlight_enabled = eero.get("nightlight_enabled")

    if led_on is None and nightlight_enabled is None:
        return None

    lines = []
    if led_on is not None:
        lines.append(field_bool("LED", led_on))
    if eero.get("led_brightness") is not None:
        lines.append(field("LED Brightness", f"{eero.get('led_brightness')}%"))
    if nightlight_enabled is not None:
        lines.append(field_bool("Nightlight", nightlight_enabled))

    nightlight = eero.get("nightlight", {})
    if nightlight and isinstance(nightlight, dict):
        schedule = nightlight.get("schedule")
        if schedule:
            lines.append(field("Schedule", schedule))

    return build_panel(lines, "LED & Nightlight", "yellow") if lines else None


def _eero_performance_panel(eero: Dict[str, Any]) -> Optional[Panel]:
    """Build the performance panel."""
    uptime = eero.get("uptime")
    mesh_quality = eero.get("mesh_quality_bars")

    if uptime is None and mesh_quality is None:
        return None

    lines = []

    if uptime is not None:
        hours = uptime // 3600
        days = hours // 24
        if days > 0:
            lines.append(field("Uptime", f"{days} days, {hours % 24} hours"))
        else:
            lines.append(field("Uptime", f"{hours} hours"))

    if mesh_quality is not None:
        bars_style = "green" if mesh_quality >= 4 else "yellow" if mesh_quality >= 2 else "red"
        filled = "●" * mesh_quality
        empty = "○" * (5 - mesh_quality)
        lines.append(
            f"[bold]Mesh Quality:[/bold] [{bars_style}]{filled}{empty} ({mesh_quality}/5)[/{bars_style}]"
        )

    if eero.get("memory_usage") is not None:
        lines.append(field("Memory Usage", f"{eero.get('memory_usage')}%"))

    if eero.get("cpu_usage") is not None:
        lines.append(field("CPU Usage", f"{eero.get('cpu_usage')}%"))

    return build_panel(lines, "Performance", "green") if lines else None


def _eero_connection_panel(eero: Dict[str, Any]) -> Panel:
    """Build the connection/network panel."""
    lines = [
        field("IP Address", eero.get("ip_address")),
        field("MAC Address", eero.get("mac_address")),
        field("Connection Type", eero.get("connection_type")),
        field("State", eero.get("state")),
    ]

    # Add timestamps if available
    last_heartbeat = eero.get("last_heartbeat")
    if last_heartbeat:
        if hasattr(last_heartbeat, "strftime"):
            lines.append(field("Last Heartbeat", last_heartbeat.strftime("%Y-%m-%d %H:%M:%S")))
        else:
            lines.append(field("Last Heartbeat", str(last_heartbeat)[:19]))

    joined = eero.get("joined")
    if joined:
        if hasattr(joined, "strftime"):
            lines.append(field("Joined", joined.strftime("%Y-%m-%d")))
        else:
            lines.append(field("Joined", str(joined)[:10]))

    last_reboot = eero.get("last_reboot")
    if last_reboot:
        lines.append(field("Last Reboot", str(last_reboot)[:19].replace("T", " ")))

    return build_panel(lines, "Connection", "green")


def _eero_ethernet_panel(eero: Dict[str, Any]) -> Optional[Panel]:
    """Build the ethernet ports panel."""
    raw = eero.get("_raw", {})
    ethernet_status = raw.get("ethernet_status") or eero.get("ethernet_status")

    if not ethernet_status or not isinstance(ethernet_status, dict):
        return None

    statuses = ethernet_status.get("statuses", [])
    if not statuses:
        return None

    lines = []

    for port in statuses:
        port_name = port.get("port_name", "?")
        has_carrier = port.get("hasCarrier", False)
        speed = port.get("speed", "Unknown")

        # Format speed (P1000 -> 1Gbps, P100 -> 100Mbps)
        if speed == "P1000":
            speed_display = "1 Gbps"
        elif speed == "P100":
            speed_display = "100 Mbps"
        elif speed == "P10":
            speed_display = "10 Mbps"
        else:
            speed_display = speed

        carrier_style = "green" if has_carrier else "dim"
        carrier_text = "Connected" if has_carrier else "No Link"

        # Check for neighbor
        neighbor = port.get("neighbor")
        neighbor_text = ""
        if neighbor and isinstance(neighbor, dict):
            metadata = neighbor.get("metadata", {})
            neighbor_location = metadata.get("location")
            if neighbor_location:
                neighbor_text = f" → {neighbor_location}"

        lines.append(
            f"[bold]Port {port_name}:[/bold] [{carrier_style}]{carrier_text}[/{carrier_style}]"
            f" ({speed_display}){neighbor_text}"
        )

    return build_panel(lines, "Ethernet Ports", "cyan") if lines else None


def _eero_wifi_panel(eero: Dict[str, Any]) -> Optional[Panel]:
    """Build the WiFi bands panel."""
    bands = eero.get("bands", [])

    if not bands:
        return None

    lines = []

    # Format band names nicely
    band_names = {
        "band_2_4GHz": "2.4 GHz",
        "band_5GHz_low": "5 GHz (Low)",
        "band_5GHz_high": "5 GHz (High)",
        "band_6GHz": "6 GHz",
    }

    for band in bands:
        display_name = band_names.get(band, band)
        lines.append(f"[bold]•[/bold] {display_name}")

    provides_wifi = eero.get("provides_wifi", True)
    if not provides_wifi:
        lines.append("[dim]WiFi disabled[/dim]")

    return build_panel(lines, "WiFi Bands", "magenta") if lines else None


def _eero_clients_panel(eero: Dict[str, Any]) -> Optional[Panel]:
    """Build the clients breakdown panel."""
    total = eero.get("connected_clients_count", 0)
    wired = eero.get("connected_wired_clients_count", 0)
    wireless = eero.get("connected_wireless_clients_count", 0)

    if total == 0:
        return None

    lines = [
        field("Total Clients", total),
        field("Wireless", wireless),
        field("Wired", wired),
    ]

    return build_panel(lines, "Connected Clients", "yellow")


# ==================== Main Eero Details Function ====================


def _normalize_eero_data(eero: Union[Dict[str, Any], Any]) -> Dict[str, Any]:
    """Normalize eero data to a consistent dict format."""
    if isinstance(eero, dict):
        return normalize_eero(eero) if "_raw" not in eero else eero
    if hasattr(eero, "model_dump"):
        return normalize_eero(eero.model_dump())
    return normalize_eero(vars(eero))


def _format_timestamp(value: Any, include_time: bool = True) -> str:
    """Format a timestamp value."""
    if value is None:
        return "-"
    if hasattr(value, "strftime"):
        if include_time:
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return value.strftime("%Y-%m-%d")
    s = str(value)
    if include_time:
        return s[:19].replace("T", " ")
    return s[:10]


def _format_bool(value: Any) -> str:
    """Format a boolean value as Enabled/Disabled to match table output."""
    return "Enabled" if value else "Disabled"


def _format_wifi_bands(bands: List[str]) -> Optional[str]:
    """Format WiFi bands to match table output."""
    if not bands:
        return None
    band_names = {
        "band_2_4GHz": "2.4 GHz",
        "band_5GHz_low": "5 GHz (Low)",
        "band_5GHz_high": "5 GHz (High)",
        "band_5GHz_full": "5 GHz",
        "band_6GHz": "6 GHz",
    }
    formatted = [band_names.get(b, b) for b in bands]
    return ", ".join(formatted)


def _format_ethernet_ports(eero: Dict[str, Any]) -> List[str]:
    """Format ethernet ports to match table output."""
    raw = eero.get("_raw", {})
    ethernet_status = raw.get("ethernet_status") or eero.get("ethernet_status")

    if not ethernet_status or not isinstance(ethernet_status, dict):
        return []

    statuses = ethernet_status.get("statuses", [])
    if not statuses:
        return []

    lines = []
    for port in statuses:
        port_name = port.get("port_name", "?")
        has_carrier = port.get("hasCarrier", False)
        speed = port.get("speed", "Unknown")

        # Format speed (P1000 -> 1Gbps, P100 -> 100Mbps)
        if speed == "P1000":
            speed_display = "1 Gbps"
        elif speed == "P100":
            speed_display = "100 Mbps"
        elif speed == "P10":
            speed_display = "10 Mbps"
        elif speed == "P10000":
            speed_display = "10 Gbps"
        else:
            speed_display = speed

        carrier_text = "Connected" if has_carrier else "No Link"

        # Check for neighbor
        neighbor = port.get("neighbor")
        neighbor_text = ""
        if neighbor and isinstance(neighbor, dict):
            metadata = neighbor.get("metadata", {})
            neighbor_location = metadata.get("location")
            if neighbor_location:
                neighbor_text = f" -> {neighbor_location}"

        lines.append(f"Port {port_name}: {carrier_text} ({speed_display}){neighbor_text}")

    return lines


def get_eero_show_fields(eero: Union[Dict[str, Any], Any]) -> List[tuple]:
    """Get the canonical list of fields to display for eero show.

    This is the SINGLE SOURCE OF TRUTH for eero show output fields.
    Both table (rich panels) and list (text) output use this.
    Field labels and value formatting match the table panel output.

    Args:
        eero: Eero dict or model object

    Returns:
        List of (label, value) tuples
    """
    e = _normalize_eero_data(eero)

    name = e.get("name") or e.get("location") or "Unknown"

    fields = [
        # Basic info - matches _eero_basic_panel
        ("Name/Location", name),
        ("Model", e.get("model")),
        ("Model Number", e.get("model_number")),
        ("Serial", e.get("serial")),
        ("Status", e.get("status")),
        ("Gateway", _format_bool(e.get("is_gateway"))),
        ("Wired", _format_bool(e.get("wired"))),
        ("Firmware", e.get("os_version")),
        ("Clients", e.get("connected_clients_count", 0)),
        # Connection - matches _eero_connection_panel
        ("IP Address", e.get("ip_address")),
        ("MAC Address", e.get("mac_address")),
        ("Connection Type", e.get("connection_type")),
        ("State", e.get("state")),
        ("Last Heartbeat", _format_timestamp(e.get("last_heartbeat"))),
        ("Joined", _format_timestamp(e.get("joined"), include_time=False)),
        ("Last Reboot", _format_timestamp(e.get("last_reboot"))),
        # Clients breakdown - matches _eero_clients_panel
        ("Total Clients", e.get("connected_clients_count", 0)),
        ("Wireless", e.get("connected_wireless_clients_count", 0)),
        ("Wired Clients", e.get("connected_wired_clients_count", 0)),
    ]

    # Ethernet Ports - matches _eero_ethernet_panel
    ethernet_lines = _format_ethernet_ports(e)
    for line in ethernet_lines:
        fields.append(("Ethernet", line))

    # WiFi Bands - matches _eero_wifi_panel
    bands = e.get("bands", [])
    if bands:
        fields.append(("WiFi Bands", _format_wifi_bands(bands)))

    # LED/Nightlight - matches _eero_led_panel
    if e.get("led_on") is not None:
        fields.append(("LED", _format_bool(e.get("led_on"))))
    if e.get("led_brightness") is not None:
        fields.append(("LED Brightness", f"{e.get('led_brightness')}%"))
    if e.get("nightlight_enabled") is not None:
        fields.append(("Nightlight", _format_bool(e.get("nightlight_enabled"))))

    # Performance - matches _eero_performance_panel
    mesh_quality = e.get("mesh_quality_bars")
    if mesh_quality is not None:
        fields.append(("Mesh Quality", f"{mesh_quality}/5"))

    return fields


def get_eero_list_data(eero: Union[Dict[str, Any], Any]) -> Dict[str, Any]:
    """Get curated eero data for list output.

    Uses get_eero_show_fields() as the single source of truth.

    Args:
        eero: Eero dict or model object

    Returns:
        Dictionary with curated fields for list output
    """
    return {label: value for label, value in get_eero_show_fields(eero)}


def print_eero_details(
    eero: Union[Dict[str, Any], Any], detail_level: DetailLevel = "brief"
) -> None:
    """Print eero information with configurable detail level.

    Args:
        eero: Eero dict or model object
        detail_level: "brief" or "full"
    """
    # Normalize to dict if needed
    if isinstance(eero, dict):
        e = normalize_eero(eero) if "_raw" not in eero else eero
    else:
        # Legacy model support - convert to dict
        if hasattr(eero, "model_dump"):
            e = normalize_eero(eero.model_dump())
        else:
            e = normalize_eero(vars(eero))

    extensive = detail_level == "full"

    # Basic info panel (always shown)
    console.print(_eero_basic_panel(e, extensive))

    # Connection panel (always shown)
    console.print(_eero_connection_panel(e))

    # Clients panel
    clients_panel = _eero_clients_panel(e)
    if clients_panel:
        console.print(clients_panel)

    # Ethernet ports panel
    ethernet_panel = _eero_ethernet_panel(e)
    if ethernet_panel:
        console.print(ethernet_panel)

    # WiFi bands panel
    wifi_panel = _eero_wifi_panel(e)
    if wifi_panel:
        console.print(wifi_panel)

    # LED/Nightlight panel
    led_panel = _eero_led_panel(e)
    if led_panel:
        console.print(led_panel)

    # Performance panel
    perf_panel = _eero_performance_panel(e)
    if perf_panel:
        console.print(perf_panel)
