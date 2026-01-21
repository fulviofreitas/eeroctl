"""Eero device formatting utilities for the Eero CLI.

This module provides formatting functions for displaying Eero mesh node data.
"""

from typing import Any, List, Optional

from eero.models.eero import Eero
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
    format_eero_status,
)

# ==================== Helper Functions ====================


def _format_ethernet_speed(speed: Optional[str]) -> str:
    """Format ethernet port speed for display."""
    if not speed:
        return "Unknown"
    speed_map = {
        "P10000": "10 Gbps",
        "P2500": "2.5 Gbps",
        "P1000": "1 Gbps",
        "P100": "100 Mbps",
        "P10": "10 Mbps",
    }
    return speed_map.get(speed, speed)


def _format_band(band: str) -> str:
    """Format band string for display."""
    band_map = {
        "band_2_4GHz": "2.4 GHz",
        "band_5GHz": "5 GHz",
        "band_5GHz_full": "5 GHz",
        "band_5GHz_low": "5 GHz (low)",
        "band_5GHz_high": "5 GHz (high)",
        "band_6GHz": "6 GHz",
    }
    return band_map.get(band, band or "Unknown")


def _get_neighbor_location(neighbor: Any) -> Optional[str]:
    """Extract location from a neighbor object."""
    if not neighbor:
        return None

    if hasattr(neighbor, "metadata"):
        return getattr(neighbor.metadata, "location", None)
    elif isinstance(neighbor, dict):
        metadata = neighbor.get("metadata", {})
        return metadata.get("location") if metadata else None

    return None


# ==================== Eero Table ====================


def create_eeros_table(eeros: List[Eero]) -> Table:
    """Create a table displaying Eero devices.

    Args:
        eeros: List of Eero objects

    Returns:
        Rich Table object
    """
    table = Table(title="Eero Devices")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="magenta")
    table.add_column("Model", style="green")
    table.add_column("IP", style="blue")
    table.add_column("Status", style="yellow")
    table.add_column("Type", style="red")
    table.add_column("Role", style="white")
    table.add_column("Connection", style="green")

    for eero in eeros:
        eero_id = eero.eero_id if hasattr(eero, "eero_id") else ""
        eero_name = str(eero.location) if eero.location else ""
        device_type = "Primary" if eero.is_primary_node else "Secondary"
        role = "Gateway" if eero.gateway else "Leaf"
        _, status_style = format_eero_status(eero.status)

        table.add_row(
            eero_id,
            eero_name,
            eero.model,
            eero.ip_address or "",
            f"[{status_style}]{eero.status}[/{status_style}]",
            device_type,
            role,
            eero.connection_type or "Unknown",
        )

    return table


# ==================== Eero Brief View Panels ====================


def _eero_basic_panel(eero: Eero, extensive: bool = False) -> Panel:
    """Build the basic eero info panel."""
    eero_id = eero.eero_id if hasattr(eero, "eero_id") else "Unknown"
    eero_name = str(eero.location) if eero.location else ""
    role = "Gateway" if eero.gateway else "Leaf"
    device_type = "Primary" if eero.is_primary_node else "Secondary"
    _, status_style = format_eero_status(eero.status)

    lines = [
        field("ID", eero_id),
        field("Name", eero_name),
        field("Model", eero.model),
    ]

    if extensive:
        lines.extend(
            [
                field("Model Number", getattr(eero, "model_number", None)),
                field("Model Variant", getattr(eero, "model_variant", None), "N/A"),
            ]
        )

    lines.extend(
        [
            field("Serial", eero.serial),
            field("MAC Address", eero.mac_address),
            field("IP Address", eero.ip_address),
            field_status("Status", eero.status, status_style),
        ]
    )

    state = getattr(eero, "state", None)
    if state:
        state_style = "green" if state == "ONLINE" else "red"
        lines.append(field_status("State", state, state_style))

    lines.extend(
        [
            field("Type", device_type),
            field("Role", role),
            field("Connection", eero.connection_type),
        ]
    )

    if extensive:
        lines.extend(
            [
                field_bool("Wired", getattr(eero, "wired", False)),
                field_bool("Using WAN", getattr(eero, "using_wan", False)),
            ]
        )
    else:
        mesh_quality = getattr(eero, "mesh_quality_bars", None)
        if mesh_quality is not None:
            quality_style = (
                "green" if mesh_quality >= 4 else "yellow" if mesh_quality >= 2 else "red"
            )
            filled = "●" * mesh_quality
            empty = "○" * (5 - mesh_quality)
            lines.append(
                f"[bold]Mesh Quality:[/bold] [{quality_style}]{filled}{empty} "
                f"({mesh_quality}/5)[/{quality_style}]"
            )

        lines.extend(
            [
                field("Connected Clients", eero.connected_clients_count),
                field("Firmware", eero.os),
                field("Uptime", f"{eero.uptime or 0} days"),
            ]
        )

        if getattr(eero, "update_available", False):
            lines.append("[bold]Update:[/bold] [yellow]Update available[/yellow]")

    return build_panel(lines, f"Eero: {eero_name}", "blue")


def _eero_connectivity_panel(eero: Eero) -> Panel:
    """Build the connectivity panel for brief view."""
    wired_clients = getattr(eero, "connected_wired_clients_count", 0)
    wireless_clients = getattr(eero, "connected_wireless_clients_count", 0)
    total_clients = eero.connected_clients_count or 0

    lines = [
        field("Total Clients", total_clients),
        field("Wired Clients", wired_clients),
        field("Wireless Clients", wireless_clients),
    ]

    led_on = getattr(eero, "led_on", None)
    if led_on is not None:
        led_brightness = getattr(eero, "led_brightness", 0)
        led_status = f"On ({led_brightness}%)" if led_on else "Off"
        led_style = "green" if led_on else "dim"
        lines.append(f"[bold]LED:[/bold] [{led_style}]{led_status}[/{led_style}]")

    provides_wifi = getattr(eero, "provides_wifi", None)
    if provides_wifi is not None:
        lines.append(field_bool("Provides WiFi", provides_wifi))

    return build_panel(lines, "Connectivity", "green")


def _eero_bands_panel(eero: Eero) -> Optional[Panel]:
    """Build the WiFi bands panel for brief view."""
    bands = getattr(eero, "bands", [])
    if not bands:
        return None

    formatted_bands = [_format_band(band) for band in bands]
    lines = ["[bold]Supported Bands:[/bold]"] + [f"  • {band}" for band in formatted_bands]
    return build_panel(lines, "WiFi Bands", "cyan")


def _eero_ethernet_ports_panel(eero: Eero) -> Optional[Panel]:
    """Build the ethernet ports panel for brief view."""
    ethernet_status = getattr(eero, "ethernet_status", None)
    if not ethernet_status or not hasattr(ethernet_status, "statuses"):
        return None

    statuses = getattr(ethernet_status, "statuses", [])
    if not statuses:
        return None

    lines = []
    for port in statuses:
        port_name = getattr(port, "port_name", None) or "?"
        has_carrier = getattr(port, "has_carrier", False) or getattr(port, "hasCarrier", False)
        speed = getattr(port, "speed", None)
        is_wan = getattr(port, "is_wan_port", False) or getattr(port, "isWanPort", False)
        neighbor = getattr(port, "neighbor", None)

        if has_carrier:
            speed_str = _format_ethernet_speed(speed)
            port_info = f"[green]●[/green] Port {port_name}: {speed_str}"

            if is_wan:
                port_info += " [cyan](WAN)[/cyan]"

            neighbor_location = _get_neighbor_location(neighbor)
            if neighbor_location:
                port_info += f" → {neighbor_location}"
        else:
            port_info = f"[dim]○[/dim] Port {port_name}: [dim]Disconnected[/dim]"

        lines.append(port_info)

    return build_panel(lines, "Ethernet Ports", "yellow") if lines else None


def _eero_timing_brief_panel(eero: Eero) -> Optional[Panel]:
    """Build the timing panel for brief view."""
    last_reboot = getattr(eero, "last_reboot", None)
    last_heartbeat = getattr(eero, "last_heartbeat", None)
    joined = getattr(eero, "joined", None)
    heartbeat_ok = getattr(eero, "heartbeat_ok", None)

    if not (last_reboot or last_heartbeat or joined):
        return None

    lines = []

    if last_reboot:
        lines.append(field("Last Reboot", format_datetime(last_reboot)))

    if last_heartbeat:
        heartbeat_str = format_datetime(last_heartbeat)
        hb_style = "green" if heartbeat_ok else "yellow"
        lines.append(f"[bold]Last Heartbeat:[/bold] [{hb_style}]{heartbeat_str}[/{hb_style}]")

    if joined:
        lines.append(field("Joined Network", format_datetime(joined, include_time=False)))

    return build_panel(lines, "Timing", "magenta")


def _eero_organization_panel(eero: Eero) -> Optional[Panel]:
    """Build the organization panel for brief view."""
    org_info = getattr(eero, "organization", None)
    if not org_info:
        return None

    org_name = (
        org_info.get("name") if isinstance(org_info, dict) else getattr(org_info, "name", None)
    )

    if not org_name:
        return None

    return build_panel([field("ISP/Organization", org_name)], "Organization", "blue")


def _eero_power_panel(eero: Eero) -> Optional[Panel]:
    """Build the power info panel for brief view."""
    power_info = getattr(eero, "power_info", None)
    if not power_info:
        return None

    power_source = (
        power_info.get("power_source")
        if isinstance(power_info, dict)
        else getattr(power_info, "power_source", None)
    )

    if not power_source:
        return None

    return build_panel([field("Power Source", power_source)], "Power", "yellow")


def _eero_location_panel(eero: Eero) -> Optional[Panel]:
    """Build the location panel for brief view."""
    if not eero.location:
        return None

    if isinstance(eero.location, str):
        return build_panel([eero.location], "Location", "yellow")

    if hasattr(eero.location, "address") and (eero.location.address or eero.location.city):
        location_parts = []
        if eero.location.address:
            location_parts.append(eero.location.address)

        city_state = []
        if eero.location.city:
            city_state.append(eero.location.city)
        if eero.location.state:
            city_state.append(eero.location.state)
        if city_state:
            location_parts.append(", ".join(city_state))

        if eero.location.zip_code:
            location_parts.append(eero.location.zip_code)
        if eero.location.country:
            location_parts.append(eero.location.country)

        return build_panel(location_parts, "Location", "yellow")

    return None


# ==================== Eero Extensive View Panels ====================


def _eero_network_info_panel(eero: Eero) -> Optional[Panel]:
    """Build the network info panel for extensive view."""
    network_info = getattr(eero, "network", {})
    if not network_info:
        return None

    lines = [
        field("Network Name", network_info.get("name")),
        field("Network URL", network_info.get("url")),
        field("Network Created", network_info.get("created")),
    ]
    return build_panel(lines, "Network Information", "green")


def _eero_timing_extensive_panel(eero: Eero) -> Panel:
    """Build the timing panel for extensive view."""
    lines = [
        field("Joined", getattr(eero, "joined", None)),
        field("Last Reboot", getattr(eero, "last_reboot", None)),
        field("Last Heartbeat", getattr(eero, "last_heartbeat", None)),
        field_bool("Heartbeat OK", getattr(eero, "heartbeat_ok", False)),
    ]
    return build_panel(lines, "Timing Information", "yellow")


def _eero_firmware_panel(eero: Eero) -> Panel:
    """Build the firmware info panel for extensive view."""
    lines = [
        field("OS", eero.os),
        field("OS Version", getattr(eero, "os_version", None)),
        field_bool("Update Available", getattr(eero, "update_available", False)),
    ]
    return build_panel(lines, "Firmware Information", "cyan")


def _eero_update_status_panel(eero: Eero) -> Optional[Panel]:
    """Build the update status panel for extensive view."""
    update_status = getattr(eero, "update_status", None)
    if not update_status:
        return None

    lines = [
        field_bool("Support Expired", getattr(update_status, "support_expired", False)),
        field(
            "Support Expiration",
            getattr(update_status, "support_expiration_string", None),
            "N/A",
        ),
    ]
    return build_panel(lines, "Update Status", "magenta")


def _eero_client_info_panel(eero: Eero) -> Panel:
    """Build the client info panel for extensive view."""
    lines = [
        field("Connected Clients", eero.connected_clients_count),
        field("Wired Clients", getattr(eero, "connected_wired_clients_count", 0)),
        field("Wireless Clients", getattr(eero, "connected_wireless_clients_count", 0)),
    ]
    return build_panel(lines, "Client Information", "blue")


def _eero_led_panel(eero: Eero) -> Panel:
    """Build the LED info panel for extensive view."""
    lines = [
        field_bool("LED On", getattr(eero, "led_on", False)),
        field("LED Brightness", f"{getattr(eero, 'led_brightness', 0)}%"),
    ]
    return build_panel(lines, "LED Information", "green")


def _eero_mesh_panel(eero: Eero) -> Panel:
    """Build the mesh info panel for extensive view."""
    lines = [
        field("Mesh Quality", f"{getattr(eero, 'mesh_quality_bars', 0)}/5"),
        field_bool("Auto Provisioned", getattr(eero, "auto_provisioned", False)),
        field_bool("Provides WiFi", getattr(eero, "provides_wifi", False)),
    ]
    return build_panel(lines, "Mesh Information", "cyan")


def _eero_wifi_bssids_panel(eero: Eero) -> Optional[Panel]:
    """Build the WiFi BSSIDs panel for extensive view."""
    wifi_bssids = getattr(eero, "wifi_bssids", [])
    if not wifi_bssids:
        return None

    lines = ["[bold]WiFi BSSIDs:[/bold]"] + [f"  • {bssid}" for bssid in wifi_bssids]
    return build_panel(lines, "WiFi BSSIDs", "magenta")


def _eero_bands_extensive_panel(eero: Eero) -> Optional[Panel]:
    """Build the bands panel for extensive view."""
    bands = getattr(eero, "bands", [])
    if not bands:
        return None

    lines = ["[bold]Supported Bands:[/bold]"] + [f"  • {band}" for band in bands]
    return build_panel(lines, "Supported Bands", "blue")


def _eero_ethernet_addresses_panel(eero: Eero) -> Optional[Panel]:
    """Build the ethernet addresses panel for extensive view."""
    ethernet_addresses = getattr(eero, "ethernet_addresses", [])
    if not ethernet_addresses:
        return None

    lines = ["[bold]Ethernet Addresses:[/bold]"] + [f"  • {addr}" for addr in ethernet_addresses]
    return build_panel(lines, "Ethernet Addresses", "yellow")


def _eero_port_details_panel(eero: Eero) -> Optional[Panel]:
    """Build the port details panel for extensive view."""
    port_details = getattr(eero, "port_details", [])
    if not port_details:
        return None

    lines = ["[bold]Port Details:[/bold]"] + [
        f"  • Port {getattr(item, 'port_name', 'Unknown')} "
        f"({getattr(item, 'position', 'Unknown')}): "
        f"{getattr(item, 'ethernet_address', 'Unknown')}"
        for item in port_details
    ]
    return build_panel(lines, "Port Details", "cyan")


def _eero_resources_panel(eero: Eero) -> Optional[Panel]:
    """Build the resources panel for extensive view."""
    resources = getattr(eero, "resources", {})
    if not resources:
        return None

    lines = ["[bold]Available Resources:[/bold]"] + [
        f"  • {key}: {value}" for key, value in resources.items()
    ]
    return build_panel(lines, "Available Resources", "blue")


def _eero_messages_panel(eero: Eero) -> Optional[Panel]:
    """Build the messages panel for extensive view."""
    messages = getattr(eero, "messages", [])
    if not messages:
        return None

    lines = ["[bold]Messages:[/bold]"] + [f"  • {msg}" for msg in messages]
    return build_panel(lines, "Messages", "red")


def _eero_health_panel(eero: Eero) -> Optional[Panel]:
    """Build the health issues panel (shown if issues exist)."""
    if not eero.health or not eero.health.issues:
        return None

    lines = [
        f"[bold]{issue.get('type', 'Issue')}:[/bold] {issue.get('description', 'No description')}"
        for issue in eero.health.issues
    ]
    return build_panel(lines, "Health Issues", "red")


# ==================== Main Eero Details Function ====================


def print_eero_details(eero: Eero, detail_level: DetailLevel = "brief") -> None:
    """Print Eero device information with configurable detail level.

    Args:
        eero: Eero object
        detail_level: "brief" or "full"
    """
    extensive = detail_level == "full"

    # Basic info panel (always shown)
    console.print(_eero_basic_panel(eero, extensive))

    if not extensive:
        # Brief view panels
        console.print(_eero_connectivity_panel(eero))

        # Optional brief panels
        for panel_func in [
            _eero_bands_panel,
            _eero_ethernet_ports_panel,
            _eero_timing_brief_panel,
            _eero_organization_panel,
            _eero_power_panel,
            _eero_location_panel,
        ]:
            panel = panel_func(eero)
            if panel:
                console.print(panel)
    else:
        # Extensive view panels
        for panel_func in [
            _eero_network_info_panel,
        ]:
            panel = panel_func(eero)
            if panel:
                console.print(panel)

        # Required extensive panels
        console.print(_eero_timing_extensive_panel(eero))
        console.print(_eero_firmware_panel(eero))

        # Optional extensive panels
        for panel_func in [
            _eero_update_status_panel,
        ]:
            panel = panel_func(eero)
            if panel:
                console.print(panel)

        # Required extensive panels
        console.print(_eero_client_info_panel(eero))
        console.print(_eero_led_panel(eero))
        console.print(_eero_mesh_panel(eero))

        # Optional extensive panels
        for panel_func in [
            _eero_wifi_bssids_panel,
            _eero_bands_extensive_panel,
            _eero_ethernet_addresses_panel,
            _eero_port_details_panel,
            _eero_resources_panel,
            _eero_messages_panel,
        ]:
            panel = panel_func(eero)
            if panel:
                console.print(panel)

    # Health issues (always shown if present, regardless of detail level)
    health_panel = _eero_health_panel(eero)
    if health_panel:
        console.print(health_panel)
