"""Formatting utilities for the Eero CLI.

This module provides reusable formatting functions for displaying
Eero network data using Rich panels and tables.
"""

from typing import Any, Dict, List, Literal, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from eero.const import EeroDeviceStatus
from eero.models.device import Device
from eero.models.eero import Eero
from eero.models.network import Network
from eero.models.profile import Profile

# Create console for rich output
console = Console()

# Type alias for detail level
DetailLevel = Literal["brief", "full"]


# ==================== Status Formatting Helpers ====================


def format_network_status(status_value: str) -> tuple[str, str]:
    """Format network status into display text and style.

    Args:
        status_value: Raw status string

    Returns:
        Tuple of (display_text, style)
    """
    status_str = str(status_value).upper()
    if "ONLINE" in status_str or status_value in ("online", "connected"):
        return "online", "green"
    elif "OFFLINE" in status_str:
        return "offline", "red"
    elif "UPDATING" in status_str:
        return "updating", "yellow"
    return "unknown", "red"


def format_device_status(status: EeroDeviceStatus) -> tuple[str, str]:
    """Format device status into display text and style.

    Args:
        status: Device status enum

    Returns:
        Tuple of (display_text, style)
    """
    if status == EeroDeviceStatus.CONNECTED:
        return "connected", "green"
    elif status == EeroDeviceStatus.BLOCKED:
        return "blocked", "red"
    elif status == EeroDeviceStatus.DISCONNECTED:
        return "disconnected", "yellow"
    return "unknown", "dim"


def format_eero_status(status: str) -> tuple[str, str]:
    """Format eero status into display text and style.

    Args:
        status: Eero status string

    Returns:
        Tuple of (display_text, style)
    """
    if status == "green":
        return status, "green"
    return status, "red"


def format_bool(value: bool, true_text: str = "Yes", false_text: str = "No") -> str:
    """Format a boolean value with color coding.

    Args:
        value: Boolean value
        true_text: Text to display when True
        false_text: Text to display when False

    Returns:
        Formatted string
    """
    if value:
        return f"[green]{true_text}[/green]"
    return f"[dim]{false_text}[/dim]"


def format_enabled(value: bool) -> str:
    """Format an enabled/disabled value."""
    return format_bool(value, "Enabled", "Disabled")


# ==================== Panel Building Helpers ====================


def build_panel(lines: List[str], title: str, border_style: str = "blue") -> Panel:
    """Build a panel from a list of formatted lines.

    Args:
        lines: List of formatted text lines
        title: Panel title
        border_style: Rich border style

    Returns:
        Rich Panel object
    """
    # Filter out None and empty lines
    content = "\n".join(line for line in lines if line)
    return Panel(content, title=title, border_style=border_style)


def field(label: str, value: Any, default: str = "Unknown") -> str:
    """Format a single field line.

    Args:
        label: Field label
        value: Field value
        default: Default value if value is None/empty

    Returns:
        Formatted line string
    """
    display_value = value if value is not None else default
    if display_value == "":
        display_value = default
    return f"[bold]{label}:[/bold] {display_value}"


def field_bool(label: str, value: Optional[bool]) -> str:
    """Format a boolean field line."""
    return f"[bold]{label}:[/bold] {format_enabled(bool(value)) if value is not None else '[dim]Unknown[/dim]'}"


def field_status(label: str, text: str, style: str) -> str:
    """Format a status field line with color."""
    return f"[bold]{label}:[/bold] [{style}]{text}[/{style}]"


# ==================== Network Formatting ====================


def create_network_table(networks: List[Network]) -> Table:
    """Create a table displaying networks.

    Args:
        networks: List of Network objects

    Returns:
        Rich Table object
    """
    table = Table(title="Eero Networks")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Public IP", style="blue")
    table.add_column("ISP", style="magenta")
    table.add_column("Created", style="yellow")

    for network in networks:
        display_status, status_style = format_network_status(str(network.status))
        table.add_row(
            network.id,
            network.name,
            f"[{status_style}]{display_status}[/{status_style}]",
            network.public_ip or "Unknown",
            network.isp_name or "Unknown",
            network.created_at.strftime("%Y-%m-%d") if network.created_at else "Unknown",
        )

    return table


def _network_basic_panel(network: Network, extensive: bool = False) -> Panel:
    """Build the basic network info panel."""
    display_status, status_style = format_network_status(str(network.status))
    updated = network.updated_at.strftime("%Y-%m-%d %H:%M:%S") if network.updated_at else "Unknown"
    created = network.created_at.strftime("%Y-%m-%d %H:%M:%S") if network.created_at else "Unknown"

    lines = [
        field("Name", network.name),
    ]
    if extensive:
        lines.append(field("Display Name", network.display_name, "N/A"))
    lines.extend(
        [
            field_status("Status", display_status, status_style),
            field("Public IP", network.public_ip),
            field("ISP", network.isp_name),
            field("Created", created),
            field("Updated", updated),
        ]
    )
    if extensive:
        lines.extend(
            [
                field("Owner", network.owner),
                field("Network Type", network.network_customer_type),
                field("Premium Status", network.premium_status),
            ]
        )
    else:
        lines.append(field_bool("Guest Network", network.guest_network_enabled))

    return build_panel(lines, f"Network: {network.name}", "blue")


def _network_dhcp_panel(network: Network) -> Optional[Panel]:
    """Build the DHCP configuration panel."""
    if not network.dhcp:
        return None

    lines = [
        field("Subnet Mask", network.dhcp.subnet_mask),
        field("Starting Address", network.dhcp.starting_address),
        field("Ending Address", network.dhcp.ending_address),
        field("Lease Time", f"{network.dhcp.lease_time_seconds // 3600} hours"),
        field("DNS Server", network.dhcp.dns_server, "Default"),
    ]
    return build_panel(lines, "DHCP Configuration", "green")


def _network_settings_panel(network: Network) -> Panel:
    """Build the network settings panel."""
    dns_caching = bool(network.dns and network.dns.get("caching", False)) if network.dns else False

    lines = [
        field_bool("IPv6 Upstream", network.ipv6_upstream),
        field_bool(
            "IPv6 Downstream", network.settings.ipv6_downstream if network.settings else False
        ),
        field_bool("Band Steering", network.band_steering),
        field_bool("Thread", network.thread),
        field_bool("UPnP", network.upnp),
        field_bool(
            "WPA3 Transition", network.settings.wpa3_transition if network.settings else False
        ),
        field_bool("DNS Caching", dns_caching),
        field("Wireless Mode", network.wireless_mode),
        field("MLO Mode", network.mlo_mode),
        field_bool("SQM", network.sqm),
    ]
    return build_panel(lines, "Network Settings", "yellow")


def _network_speed_panel(network: Network) -> Optional[Panel]:
    """Build the speed test results panel."""
    if not network.speed_test:
        return None

    lines = [
        field("Download", f"{network.speed_test.get('down', {}).get('value', 0)} Mbps"),
        field("Upload", f"{network.speed_test.get('up', {}).get('value', 0)} Mbps"),
        field("Latency", f"{network.speed_test.get('latency', {}).get('value', 0)} ms"),
        field("Tested", network.speed_test.get("date", "Unknown")),
    ]
    return build_panel(lines, "Speed Test Results", "cyan")


def _network_resources_panel(network: Network) -> Optional[Panel]:
    """Build the available resources panel."""
    resources = getattr(network, "resources", {})
    if not resources:
        return None

    lines = ["[bold]Available Resources:[/bold]"] + [
        f"  • {key}: {value}" for key, value in resources.items()
    ]
    return build_panel(lines, "Available Resources", "cyan")


def print_network_details(network: Network, detail_level: DetailLevel = "brief") -> None:
    """Print network information with configurable detail level.

    Args:
        network: Network object
        detail_level: "brief" or "full"
    """
    extensive = detail_level == "full"

    # Basic info panel (always shown)
    console.print(_network_basic_panel(network, extensive))

    # Connection info (extensive only)
    if extensive:
        lines = [
            field("Gateway Type", network.gateway),
            field("WAN Type", network.wan_type),
            field("Gateway IP", network.gateway_ip),
            field("Connection Mode", network.connection_mode),
            field("Auto Setup Mode", network.auto_setup_mode),
            field_bool("Backup Internet", network.backup_internet_enabled),
            field_bool("Power Saving", network.power_saving),
        ]
        console.print(build_panel(lines, "Connection Information", "green"))

    # Geographic info (extensive only)
    if extensive:
        geo_info = getattr(network, "geo_ip", {})
        if geo_info:
            lines = [
                field(
                    "Country",
                    f"{geo_info.get('countryName', 'Unknown')} ({geo_info.get('countryCode', 'Unknown')})",
                ),
                field("City", geo_info.get("city")),
                field("Region", geo_info.get("regionName")),
                field("Postal Code", geo_info.get("postalCode")),
                field("Timezone", geo_info.get("timezone")),
                field("ASN", geo_info.get("asn")),
            ]
            console.print(build_panel(lines, "Geographic Information", "yellow"))

    # DHCP info
    dhcp_panel = _network_dhcp_panel(network)
    if dhcp_panel:
        console.print(dhcp_panel)

    # DNS config (extensive only)
    if extensive:
        dns_info = getattr(network, "dns", {})
        if dns_info:
            parent_ips = ", ".join(dns_info.get("parent", {}).get("ips", []))
            custom_ips = ", ".join(dns_info.get("custom", {}).get("ips", []))
            lines = [
                field("DNS Mode", dns_info.get("mode")),
                field_bool("DNS Caching", dns_info.get("caching", False)),
                field("Parent DNS", parent_ips or "None"),
                field("Custom DNS", custom_ips or "None"),
            ]
            console.print(build_panel(lines, "DNS Configuration", "cyan"))

    # Settings panel (always shown)
    console.print(_network_settings_panel(network))

    # Guest network (extensive only)
    if extensive:
        guest_password = "[dim]********[/dim]" if network.guest_network_password else "N/A"
        lines = [
            field_bool("Guest Network", network.guest_network_enabled),
            field("Guest Network Name", network.guest_network_name, "N/A"),
            field("Guest Network Password", guest_password),
        ]
        console.print(build_panel(lines, "Guest Network", "magenta"))

    # Speed test results
    speed_panel = _network_speed_panel(network)
    if speed_panel:
        console.print(speed_panel)

    # Health info (extensive only)
    if extensive:
        health_info = getattr(network, "health", {})
        if health_info:
            lines = [
                field("Internet Status", health_info.get("internet", {}).get("status")),
                field_bool("ISP Up", health_info.get("internet", {}).get("isp_up", False)),
                field("Eero Network Status", health_info.get("eero_network", {}).get("status")),
            ]
            console.print(build_panel(lines, "Network Health", "green"))

    # Organization (extensive only)
    if extensive:
        org_info = getattr(network, "organization", {})
        if org_info:
            lines = [
                field("Organization ID", org_info.get("id")),
                field("Organization Name", org_info.get("name")),
                field("Organization Brand", org_info.get("brand")),
                field("Organization Type", org_info.get("type")),
            ]
            console.print(build_panel(lines, "Organization", "blue"))

    # Premium details (extensive only)
    if extensive:
        premium_info = getattr(network, "premium_details", {})
        if premium_info:
            lines = [
                field("Tier", premium_info.get("tier")),
                field("Payment Method", premium_info.get("payment_method")),
                field("Interval", premium_info.get("interval")),
                field("Next Billing", premium_info.get("next_billing_event_date")),
                field_bool("My Subscription", premium_info.get("is_my_subscription", False)),
                field_bool("Has Payment Info", premium_info.get("has_payment_info", False)),
            ]
            console.print(build_panel(lines, "Premium Details", "magenta"))

    # Updates (extensive only)
    if extensive:
        updates_info = getattr(network, "updates", {})
        if updates_info:
            lines = [
                field_bool("Update Required", updates_info.get("update_required", False)),
                field_bool("Can Update Now", updates_info.get("can_update_now", False)),
                field_bool("Has Update", updates_info.get("has_update", False)),
                field("Target Firmware", updates_info.get("target_firmware")),
                field("Preferred Update Hour", updates_info.get("preferred_update_hour")),
            ]
            console.print(build_panel(lines, "Updates", "yellow"))

    # DDNS (extensive only)
    if extensive:
        ddns_info = getattr(network, "ddns", {})
        if ddns_info:
            lines = [
                field_bool("DDNS Enabled", ddns_info.get("enabled", False)),
                field("Subdomain", ddns_info.get("subdomain")),
            ]
            console.print(build_panel(lines, "DDNS", "cyan"))

    # HomeKit (extensive only)
    if extensive:
        homekit_info = getattr(network, "homekit", {})
        if homekit_info:
            lines = [
                field_bool("HomeKit Enabled", homekit_info.get("enabled", False)),
                field_bool("Managed Network", homekit_info.get("managedNetworkEnabled", False)),
            ]
            console.print(build_panel(lines, "HomeKit", "green"))

    # Amazon Integration (extensive only)
    if extensive:
        lines = [
            field_bool("Amazon Account Linked", getattr(network, "amazon_account_linked", False)),
            field_bool("FFS", getattr(network, "ffs", False)),
            field_bool("Alexa Skill", getattr(network, "alexa_skill", False)),
        ]
        console.print(build_panel(lines, "Amazon Integration", "blue"))

    # IP Settings (extensive only)
    if extensive:
        ip_settings = getattr(network, "ip_settings", {})
        if ip_settings:
            lines = [
                field_bool("Double NAT", ip_settings.get("double_nat", False)),
                field("Public IP", ip_settings.get("public_ip")),
            ]
            console.print(build_panel(lines, "IP Settings", "yellow"))

    # Premium DNS (extensive only)
    if extensive:
        premium_dns = getattr(network, "premium_dns", {})
        if premium_dns:
            dns_policies = premium_dns.get("dns_policies", {})
            lines = [
                field_bool("DNS Policies Enabled", premium_dns.get("dns_policies_enabled", False)),
                field("DNS Provider", premium_dns.get("dns_provider")),
                field_bool("Block Malware", dns_policies.get("block_malware", False)),
                field_bool("Ad Block", dns_policies.get("ad_block", False)),
            ]
            console.print(build_panel(lines, "Premium DNS", "magenta"))

    # Last reboot (extensive only)
    if extensive:
        last_reboot = getattr(network, "last_reboot", None)
        if last_reboot:
            console.print(build_panel([field("Last Reboot", last_reboot)], "Last Reboot", "red"))

    # Resources
    resources_panel = _network_resources_panel(network)
    if resources_panel:
        console.print(resources_panel)


# Backward compatibility aliases
def print_network_details_extensive(network: Network) -> None:
    """Print extensive network details (deprecated, use print_network_details with detail_level='full')."""
    print_network_details(network, detail_level="full")


# ==================== Eero Device Formatting ====================


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


def print_eero_details(eero: Eero, detail_level: DetailLevel = "brief") -> None:
    """Print Eero device information with configurable detail level.

    Args:
        eero: Eero object
        detail_level: "brief" or "full"
    """
    extensive = detail_level == "full"

    eero_id = eero.eero_id if hasattr(eero, "eero_id") else "Unknown"
    eero_name = str(eero.location) if eero.location else ""
    role = "Gateway" if eero.gateway else "Leaf"
    device_type = "Primary" if eero.is_primary_node else "Secondary"
    _, status_style = format_eero_status(eero.status)

    # Basic info panel
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
    if extensive:
        lines.append(field("State", getattr(eero, "state", None)))
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
        lines.extend(
            [
                field("Connected Clients", eero.connected_clients_count),
                field("Firmware", eero.os),
                field("Uptime", f"{eero.uptime or 0} days"),
            ]
        )

    console.print(build_panel(lines, f"Eero: {eero_name}", "blue"))

    # Network info (extensive only)
    if extensive:
        network_info = getattr(eero, "network", {})
        if network_info:
            lines = [
                field("Network Name", network_info.get("name")),
                field("Network URL", network_info.get("url")),
                field("Network Created", network_info.get("created")),
            ]
            console.print(build_panel(lines, "Network Information", "green"))

    # Timing info (extensive only)
    if extensive:
        lines = [
            field("Joined", getattr(eero, "joined", None)),
            field("Last Reboot", getattr(eero, "last_reboot", None)),
            field("Last Heartbeat", getattr(eero, "last_heartbeat", None)),
            field_bool("Heartbeat OK", getattr(eero, "heartbeat_ok", False)),
        ]
        console.print(build_panel(lines, "Timing Information", "yellow"))

    # Firmware info (extensive only)
    if extensive:
        lines = [
            field("OS", eero.os),
            field("OS Version", getattr(eero, "os_version", None)),
            field_bool("Update Available", getattr(eero, "update_available", False)),
        ]
        console.print(build_panel(lines, "Firmware Information", "cyan"))

    # Update status (extensive only)
    if extensive:
        update_status = getattr(eero, "update_status", None)
        if update_status:
            lines = [
                field_bool("Support Expired", getattr(update_status, "support_expired", False)),
                field(
                    "Support Expiration",
                    getattr(update_status, "support_expiration_string", None),
                    "N/A",
                ),
            ]
            console.print(build_panel(lines, "Update Status", "magenta"))

    # Client info (extensive only)
    if extensive:
        lines = [
            field("Connected Clients", eero.connected_clients_count),
            field("Wired Clients", getattr(eero, "connected_wired_clients_count", 0)),
            field("Wireless Clients", getattr(eero, "connected_wireless_clients_count", 0)),
        ]
        console.print(build_panel(lines, "Client Information", "blue"))

    # LED info (extensive only)
    if extensive:
        lines = [
            field_bool("LED On", getattr(eero, "led_on", False)),
            field("LED Brightness", f"{getattr(eero, 'led_brightness', 0)}%"),
        ]
        console.print(build_panel(lines, "LED Information", "green"))

    # Mesh info (extensive only)
    if extensive:
        lines = [
            field("Mesh Quality", f"{getattr(eero, 'mesh_quality_bars', 0)}/5"),
            field_bool("Auto Provisioned", getattr(eero, "auto_provisioned", False)),
            field_bool("Provides WiFi", getattr(eero, "provides_wifi", False)),
        ]
        console.print(build_panel(lines, "Mesh Information", "cyan"))

    # WiFi BSSIDs (extensive only)
    if extensive:
        wifi_bssids = getattr(eero, "wifi_bssids", [])
        if wifi_bssids:
            lines = ["[bold]WiFi BSSIDs:[/bold]"] + [f"  • {bssid}" for bssid in wifi_bssids]
            console.print(build_panel(lines, "WiFi BSSIDs", "magenta"))

    # Bands (extensive only)
    if extensive:
        bands = getattr(eero, "bands", [])
        if bands:
            lines = ["[bold]Supported Bands:[/bold]"] + [f"  • {band}" for band in bands]
            console.print(build_panel(lines, "Supported Bands", "blue"))

    # Ethernet addresses (extensive only)
    if extensive:
        ethernet_addresses = getattr(eero, "ethernet_addresses", [])
        if ethernet_addresses:
            lines = ["[bold]Ethernet Addresses:[/bold]"] + [
                f"  • {addr}" for addr in ethernet_addresses
            ]
            console.print(build_panel(lines, "Ethernet Addresses", "yellow"))

    # Port details (extensive only)
    if extensive:
        port_details = getattr(eero, "port_details", [])
        if port_details:
            lines = ["[bold]Port Details:[/bold]"] + [
                f"  • Port {getattr(item, 'port_name', 'Unknown')} ({getattr(item, 'position', 'Unknown')}): {getattr(item, 'ethernet_address', 'Unknown')}"
                for item in port_details
            ]
            console.print(build_panel(lines, "Port Details", "cyan"))

    # Resources (extensive only)
    if extensive:
        resources = getattr(eero, "resources", {})
        if resources:
            lines = ["[bold]Available Resources:[/bold]"] + [
                f"  • {key}: {value}" for key, value in resources.items()
            ]
            console.print(build_panel(lines, "Available Resources", "blue"))

    # Messages (extensive only)
    if extensive:
        messages = getattr(eero, "messages", [])
        if messages:
            lines = ["[bold]Messages:[/bold]"] + [f"  • {msg}" for msg in messages]
            console.print(build_panel(lines, "Messages", "red"))

    # Health issues (always shown if present)
    if eero.health and eero.health.issues:
        lines = [
            f"[bold]{issue.get('type', 'Issue')}:[/bold] {issue.get('description', 'No description')}"
            for issue in eero.health.issues
        ]
        console.print(build_panel(lines, "Health Issues", "red"))

    # Location info (brief only, as panel)
    if not extensive and eero.location:
        if isinstance(eero.location, str):
            console.print(build_panel([eero.location], "Location", "yellow"))
        elif hasattr(eero.location, "address") and (eero.location.address or eero.location.city):
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
            console.print(build_panel(location_parts, "Location", "yellow"))


# Backward compatibility alias
def print_eero_details_extensive(eero: Eero) -> None:
    """Print extensive Eero details (deprecated, use print_eero_details with detail_level='full')."""
    print_eero_details(eero, detail_level="full")


# ==================== Device Formatting ====================


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


def print_device_details(device: Device, detail_level: DetailLevel = "brief") -> None:
    """Print device information with configurable detail level.

    Args:
        device: Device object
        detail_level: "brief" or "full"
    """
    extensive = detail_level == "full"

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

    # Basic info panel
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

    console.print(build_panel(lines, f"Device: {device_name}", "blue"))

    # Connectivity info (extensive only)
    if extensive and device.connectivity:
        channel_width = "N/A"
        if device.connectivity.rx_rate_info and "channel_width" in device.connectivity.rx_rate_info:
            channel_width = device.connectivity.rx_rate_info["channel_width"]

        lines = [
            field("Signal", device.connectivity.signal, "N/A"),
            field("Score", device.connectivity.score, "N/A"),
            field("Score Bars", device.connectivity.score_bars, "N/A"),
            field("Frequency", f"{device.connectivity.frequency or 'N/A'} MHz"),
            field("RX Bitrate", device.connectivity.rx_bitrate, "N/A"),
            field("Channel Width", channel_width),
        ]
        console.print(build_panel(lines, "Connectivity", "green"))

    # Interface info (extensive only)
    if extensive and device.interface:
        lines = [
            field(
                "Frequency",
                f"{device.interface.frequency or 'N/A'} {device.interface.frequency_unit or ''}",
            ),
            field("Channel", device.channel, "N/A"),
            field("Authentication", device.auth, "N/A"),
        ]
        console.print(build_panel(lines, "Interface", "cyan"))

    # Connection details (brief only)
    if not extensive and device.connection:
        lines = [
            field("Type", device.connection.type),
            field("Connected To", device.connection.connected_to),
            field("Connected Via", device.connection.connected_via),
        ]
        if device.connection.frequency:
            lines.append(field("Frequency", device.connection.frequency))
        if device.connection.signal_strength is not None:
            lines.append(field("Signal Strength", device.connection.signal_strength))
        if device.connection.tx_rate is not None:
            lines.append(field("TX Rate", f"{device.connection.tx_rate} Mbps"))
        if device.connection.rx_rate is not None:
            lines.append(field("RX Rate", f"{device.connection.rx_rate} Mbps"))
        console.print(build_panel(lines, "Connection Details", "green"))

    # Tags (brief only)
    if not extensive and device.tags:
        lines = [f"[bold]{tag.name}:[/bold] {tag.color or 'No color'}" for tag in device.tags]
        console.print(build_panel(lines, "Tags", "yellow"))


# Backward compatibility alias
def print_device_details_extensive(device: Device) -> None:
    """Print extensive device details (deprecated, use print_device_details with detail_level='full')."""
    print_device_details(device, detail_level="full")


# ==================== Profile Formatting ====================


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


def print_profile_details(profile: Profile, detail_level: DetailLevel = "brief") -> None:
    """Print profile information with configurable detail level.

    Args:
        profile: Profile object
        detail_level: "brief" or "full"
    """
    paused_style = "red" if profile.paused else "green"

    # Basic info panel
    lines = [
        field("Name", profile.name),
    ]
    if detail_level == "full":
        lines.extend(
            [
                field("Devices", profile.device_count),
                field("Connected Devices", profile.connected_device_count),
            ]
        )
    else:
        lines.append(field("State", profile.state.value if profile.state else "Unknown"))

    lines.extend(
        [
            f"[bold]Paused:[/bold] [{paused_style}]{'Yes' if profile.paused else 'No'}[/{paused_style}]",
        ]
    )

    if detail_level == "full":
        lines.extend(
            [
                field_bool("Premium Enabled", profile.premium_enabled),
                field_bool("Schedule Enabled", profile.schedule_enabled),
            ]
        )
    else:
        lines.extend(
            [
                field_bool("Schedule", profile.schedule_enabled),
            ]
        )
        filter_enabled = bool(profile.content_filter and any(vars(profile.content_filter).values()))
        lines.append(field_bool("Content Filter", filter_enabled))

    console.print(build_panel(lines, f"Profile: {profile.name}", "blue"))

    # Schedule (full only)
    if detail_level == "full" and profile.schedule_enabled and profile.schedule_blocks:
        lines = [
            f"[bold]{', '.join(block.days)}:[/bold] {block.start_time} - {block.end_time}"
            for block in profile.schedule_blocks
        ]
        console.print(build_panel(lines, "Schedule", "green"))

    # Content filter (full only)
    if detail_level == "full" and profile.content_filter:
        filter_enabled = any(vars(profile.content_filter).values())
        if filter_enabled:
            filter_settings = []
            for name, value in vars(profile.content_filter).items():
                if value:
                    display_name = " ".join(word.capitalize() for word in name.split("_"))
                    filter_settings.append(f"[bold]{display_name}:[/bold] Enabled")
            console.print(build_panel(filter_settings, "Content Filtering", "yellow"))

    # Block/Allow lists (full only)
    if detail_level == "full":
        if profile.custom_block_list:
            console.print(build_panel(profile.custom_block_list, "Blocked Domains", "red"))
        if profile.custom_allow_list:
            console.print(build_panel(profile.custom_allow_list, "Allowed Domains", "green"))

    # Devices table (brief shows devices)
    if detail_level == "brief" and profile.devices:
        console.print(create_profile_devices_table(profile.devices))
    elif detail_level == "brief":
        console.print("[bold yellow]No devices in this profile[/bold yellow]")


# Backward compatibility alias
def print_profile_details_brief(profile: Profile) -> None:
    """Print brief profile details (deprecated, use print_profile_details with detail_level='brief')."""
    print_profile_details(profile, detail_level="brief")


# ==================== Miscellaneous Formatting ====================


def print_speedtest_results(result: dict) -> None:
    """Print speed test results.

    Args:
        result: Speed test result dictionary
    """
    download = result.get("down", {}).get("value", 0)
    upload = result.get("up", {}).get("value", 0)
    latency = result.get("latency", {}).get("value", 0)

    lines = [
        field("Download", f"{download} Mbps"),
        field("Upload", f"{upload} Mbps"),
        field("Latency", f"{latency} ms"),
    ]
    console.print(build_panel(lines, "Speed Test Results", "green"))


def create_blacklist_table(blacklist_data: List[Dict[str, Any]]) -> Table:
    """Create a table displaying blacklisted devices.

    Args:
        blacklist_data: List of blacklisted device dictionaries

    Returns:
        Rich Table object
    """
    table = Table(title="Blacklisted Devices")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Nickname", style="blue")
    table.add_column("IP", style="green")
    table.add_column("MAC", style="yellow")
    table.add_column("Type", style="cyan")
    table.add_column("Manufacturer", style="green")
    table.add_column("Connection Type", style="blue")
    table.add_column("Eero Location", style="yellow")
    table.add_column("Last Active", style="magenta")

    for device in blacklist_data:
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
        source = device.get("source", {})
        eero_location = source.get("location") if source else "Unknown"

        table.add_row(
            device_id,
            device_name,
            device.get("nickname") or "",
            device.get("ip") or "Unknown",
            device.get("mac") or "Unknown",
            device.get("device_type") or "Unknown",
            device.get("manufacturer") or "Unknown",
            device.get("connection_type") or "Unknown",
            eero_location,
            str(device.get("last_active") or "Unknown"),
        )

    return table
