"""Network formatting utilities for the Eero CLI.

This module provides formatting functions for displaying network data.
Updated to work with raw dict data from transformers.
"""

from typing import Any, Dict, List, Optional, Tuple, Union

from rich.panel import Panel
from rich.table import Table

from ..context import EeroCliContext
from ..transformers.network import normalize_network
from .base import (
    DetailLevel,
    build_panel,
    console,
    field,
    field_bool,
    field_status,
    format_bool,
    format_datetime,
    format_network_status,
)
from .generic import render_generic

# ==================== Network Table ====================


def create_network_table(networks: List[Dict[str, Any]]) -> Table:
    """Create a table displaying networks.

    Args:
        networks: List of network dicts (already transformed)

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
        net = normalize_network(network) if "_raw" not in network else network
        status_value = net.get("status", "unknown")
        display_status, status_style = format_network_status(status_value)
        created_at = net.get("created_at")
        created_str = format_datetime(created_at, include_time=False) if created_at else "Unknown"

        table.add_row(
            net.get("id", ""),
            net.get("name", ""),
            f"[{status_style}]{display_status}[/{status_style}]",
            net.get("public_ip") or "Unknown",
            net.get("isp_name") or "Unknown",
            created_str,
        )

    return table


# ==================== Network Brief View Panels ====================


def _network_basic_panel(network: Dict[str, Any], extensive: bool = False) -> Panel:
    """Build the basic network info panel."""
    status_value = network.get("status", "unknown")
    display_status, status_style = format_network_status(status_value)
    updated = format_datetime(network.get("updated_at"))
    created = format_datetime(network.get("created_at"))

    lines = [
        field("Name", network.get("name")),
    ]

    if extensive:
        lines.append(field("Display Name", network.get("display_name"), "N/A"))

    lines.extend(
        [
            field_status("Status", display_status, status_style),
            field("Public IP", network.get("public_ip")),
            field("ISP", network.get("isp_name")),
            field("Created", created),
            field("Updated", updated),
        ]
    )

    if extensive:
        lines.extend(
            [
                field("Owner", network.get("owner")),
                field("Network Type", network.get("network_customer_type")),
                field("Premium Status", network.get("premium_status")),
            ]
        )
    else:
        if network.get("owner"):
            lines.append(field("Owner", network.get("owner")))
        if network.get("network_customer_type"):
            lines.append(field("Type", network.get("network_customer_type")))

        lines.append(field_bool("Guest Network", network.get("guest_network_enabled")))

        updates_info = network.get("updates", {})
        if updates_info and updates_info.get("has_update", False):
            target_fw = updates_info.get("target_firmware", "")
            lines.append(f"[bold]Update:[/bold] [yellow]Available ({target_fw})[/yellow]")

    return build_panel(lines, f"Network: {network.get('name', 'Unknown')}", "blue")


def _network_health_panel(network: Dict[str, Any]) -> Optional[Panel]:
    """Build the network health panel for brief view."""
    health_info = network.get("health", {})
    if not health_info:
        return None

    internet_info = health_info.get("internet", {})
    eero_info = health_info.get("eero_network", {})

    internet_status = internet_info.get("status", "unknown")
    isp_up = internet_info.get("isp_up", False)
    eero_status = eero_info.get("status", "unknown")

    internet_style = "green" if internet_status == "connected" else "red"
    eero_style = "green" if eero_status == "connected" else "red"

    lines = [
        f"[bold]Internet:[/bold] [{internet_style}]{internet_status}[/{internet_style}]",
        f"[bold]ISP Up:[/bold] {format_bool(isp_up)}",
        f"[bold]Eero Network:[/bold] [{eero_style}]{eero_status}[/{eero_style}]",
    ]

    return build_panel(lines, "Network Health", "green")


def _network_connection_panel(network: Dict[str, Any]) -> Panel:
    """Build the connection info panel for brief view."""
    lines = [
        field("Gateway Type", network.get("gateway")),
        field("WAN Type", network.get("wan_type")),
        field("Gateway IP", network.get("gateway_ip")),
    ]

    backup_enabled = network.get("backup_internet_enabled", False)
    if backup_enabled:
        lines.append("[bold]Backup Internet:[/bold] [green]Enabled[/green]")

    ip_settings = network.get("ip_settings", {})
    if ip_settings and ip_settings.get("double_nat", False):
        lines.append("[bold]Double NAT:[/bold] [yellow]Detected[/yellow]")

    return build_panel(lines, "Connection", "green")


def _network_dhcp_panel(network: Dict[str, Any]) -> Optional[Panel]:
    """Build the DHCP configuration panel."""
    dhcp = network.get("dhcp")
    if not dhcp:
        return None

    lease_time = dhcp.get("lease_time_seconds", 86400)

    # Use "Automatic" for empty DHCP range values since eero manages it
    starting = dhcp.get("starting_address")
    ending = dhcp.get("ending_address")

    lines = [
        field("Subnet Mask", dhcp.get("subnet_mask")),
        field("Starting Address", starting, "Automatic"),
        field("Ending Address", ending, "Automatic"),
        field("Lease Time", f"{lease_time // 3600} hours"),
        field("DNS Server", dhcp.get("dns_server"), "Default"),
    ]
    return build_panel(lines, "DHCP Configuration", "cyan")


def _network_dns_brief_panel(network: Dict[str, Any]) -> Optional[Panel]:
    """Build the DNS info panel for brief view."""
    dns_info = network.get("dns", {})
    premium_dns = network.get("premium_dns", {})

    if not dns_info and not premium_dns:
        return None

    lines = []

    if dns_info:
        mode = dns_info.get("mode", "automatic")
        lines.append(field("DNS Mode", mode))

        caching = dns_info.get("caching", False)
        lines.append(field_bool("DNS Caching", caching))

        # Show upstream/parent DNS servers
        parent = dns_info.get("parent", {})
        parent_ips = parent.get("ips", []) if isinstance(parent, dict) else []
        if parent_ips:
            lines.append(field("Upstream DNS", ", ".join(parent_ips)))

        # Show custom DNS servers
        custom = dns_info.get("custom", {})
        custom_ips = custom.get("ips", []) if isinstance(custom, dict) else []
        if custom_ips:
            lines.append(field("Custom DNS", ", ".join(custom_ips)))

    if premium_dns:
        dns_policies = premium_dns.get("dns_policies", {})
        malware_block = dns_policies.get("block_malware", False)
        ad_block = dns_policies.get("ad_block", False)

        if malware_block:
            lines.append("[bold]Malware Block:[/bold] [green]Enabled[/green]")
        if ad_block:
            lines.append("[bold]Ad Block:[/bold] [green]Enabled[/green]")

    return build_panel(lines, "DNS & Security", "magenta") if lines else None


def _network_location_panel(network: Dict[str, Any]) -> Optional[Panel]:
    """Build the location/geo info panel."""
    geo_ip = network.get("geo_ip", {})
    if not geo_ip or not isinstance(geo_ip, dict):
        return None

    # Build location string (city, region, country)
    city = geo_ip.get("city")
    region = geo_ip.get("region") or geo_ip.get("regionName")
    country = geo_ip.get("countryName") or geo_ip.get("countryCode")

    location_parts = [p for p in [city, region, country] if p]
    location = ", ".join(location_parts) if location_parts else None

    lines = []

    if location:
        lines.append(field("Location", location))

    timezone = geo_ip.get("timezone")
    if timezone:
        lines.append(field("Timezone", timezone))

    org = geo_ip.get("org")
    if org:
        lines.append(field("Organization", org))

    asn = geo_ip.get("asn")
    if asn:
        lines.append(field("ASN", f"AS{asn}"))

    return build_panel(lines, "Location", "cyan") if lines else None


def _network_settings_panel(network: Dict[str, Any]) -> Panel:
    """Build the network settings panel."""
    dns_info = network.get("dns", {})
    dns_caching = dns_info.get("caching", False) if dns_info else False

    settings = network.get("settings", {})
    ipv6_downstream = settings.get("ipv6_downstream", False) if settings else False
    wpa3_transition = settings.get("wpa3_transition", False) if settings else False

    lines = [
        field_bool("IPv6 Upstream", network.get("ipv6_upstream")),
        field_bool("IPv6 Downstream", ipv6_downstream),
        field_bool("Band Steering", network.get("band_steering")),
        field_bool("Thread", network.get("thread")),
        field_bool("UPnP", network.get("upnp")),
        field_bool("WPA3 Transition", wpa3_transition),
        field_bool("DNS Caching", dns_caching),
        field("Wireless Mode", network.get("wireless_mode")),
        field("MLO Mode", network.get("mlo_mode")),
        field_bool("SQM", network.get("sqm")),
    ]
    return build_panel(lines, "Network Settings", "yellow")


def _network_speed_panel(network: Dict[str, Any]) -> Optional[Panel]:
    """Build the speed test results panel."""
    speed_test = network.get("speed_test")
    if not speed_test:
        return None

    down_info = speed_test.get("down", {})
    up_info = speed_test.get("up", {})
    latency_info = speed_test.get("latency", {})

    down_value = down_info.get("value", 0) if isinstance(down_info, dict) else 0
    up_value = up_info.get("value", 0) if isinstance(up_info, dict) else 0
    latency_value = latency_info.get("value", 0) if isinstance(latency_info, dict) else 0
    test_date = speed_test.get("date", "Unknown")

    down_str = f"{down_value:.1f}" if isinstance(down_value, float) else str(down_value)
    up_str = f"{up_value:.1f}" if isinstance(up_value, float) else str(up_value)

    lines = [
        field("Download", f"{down_str} Mbps"),
        field("Upload", f"{up_str} Mbps"),
    ]

    if latency_value:
        lines.append(field("Latency", f"{latency_value} ms"))

    if test_date and test_date != "Unknown":
        if "T" in str(test_date):
            test_date = str(test_date)[:19].replace("T", " ")
        lines.append(field("Tested", test_date))

    return build_panel(lines, "Speed Test Results", "cyan")


def _network_guest_panel(network: Dict[str, Any]) -> Panel:
    """Build the guest network panel for extensive view."""
    guest_password = "[dim]********[/dim]" if network.get("guest_network_password") else "N/A"
    lines = [
        field_bool("Guest Network", network.get("guest_network_enabled")),
        field("Guest Network Name", network.get("guest_network_name"), "N/A"),
        field("Guest Network Password", guest_password),
    ]
    return build_panel(lines, "Guest Network", "magenta")


# ==================== List Output Data ====================


def _normalize_network_data(network: Union[Dict[str, Any], Any]) -> Dict[str, Any]:
    """Normalize network data to a consistent dict format."""
    if isinstance(network, dict):
        return normalize_network(network) if "_raw" not in network else network
    if hasattr(network, "model_dump"):
        return normalize_network(network.model_dump())
    return normalize_network(vars(network))


def _format_enabled(value: Any) -> str:
    """Format a boolean value as Enabled/Disabled to match table output."""
    return "Enabled" if value else "Disabled"


def get_network_show_fields(network: Union[Dict[str, Any], Any]) -> List[tuple]:
    """Get the canonical list of fields to display for network show.

    This is the SINGLE SOURCE OF TRUTH for network show output fields.
    Both table (rich panels) and list (text) output use this.
    Field labels and value formatting match the table panel output.

    Args:
        network: Network dict or model object

    Returns:
        List of (label, value) tuples
    """
    net = _normalize_network_data(network)

    fields = _show_basic_fields(net)
    fields.extend(_show_dhcp_fields(net.get("dhcp", {})))
    fields.extend(_show_dns_fields(net.get("dns", {})))
    fields.extend(_show_location_fields(net.get("geo_ip", {})))
    fields.extend(_show_speed_fields(net.get("speed_test", {})))
    return fields


def _show_basic_fields(net: Dict[str, Any]) -> List[Tuple[str, Any]]:
    """Basic and connection rows (matches _network_basic_panel/_network_connection_panel)."""
    fields: List[Tuple[str, Any]] = [
        ("Name", net.get("name")),
        ("Status", net.get("status")),
        ("Public IP", net.get("public_ip")),
        ("ISP", net.get("isp_name")),
        ("Created", format_datetime(net.get("created_at"))),
        ("Updated", format_datetime(net.get("updated_at"))),
        ("Owner", net.get("owner")),
        ("Type", net.get("network_customer_type")),
        ("Guest Network", _format_enabled(net.get("guest_network_enabled"))),
        ("Gateway Type", net.get("gateway")),
        ("WAN Type", net.get("wan_type")),
        ("Gateway IP", net.get("gateway_ip")),
    ]
    if net.get("backup_internet_enabled", False):
        fields.append(("Backup Internet", "Enabled"))
    return fields


def _show_dhcp_fields(dhcp: Any) -> List[Tuple[str, Any]]:
    """DHCP rows (matches _network_dhcp_panel)."""
    if not dhcp:
        return []
    lease_hours = dhcp.get("lease_time_seconds", 86400) // 3600
    return [
        ("Subnet Mask", dhcp.get("subnet_mask")),
        ("Starting Address", dhcp.get("starting_address") or "Automatic"),
        ("Ending Address", dhcp.get("ending_address") or "Automatic"),
        ("Lease Time", f"{lease_hours} hours"),
        ("DNS Server", dhcp.get("dns_server") or "Default"),
    ]


def _show_dns_fields(dns: Any) -> List[Tuple[str, Any]]:
    """DNS rows (matches _network_dns_brief_panel)."""
    if not dns:
        return []
    fields: List[Tuple[str, Any]] = [
        ("DNS Mode", dns.get("mode")),
        ("DNS Caching", _format_enabled(dns.get("caching", False))),
    ]
    parent = dns.get("parent", {})
    parent_ips = parent.get("ips", []) if isinstance(parent, dict) else []
    if parent_ips:
        fields.append(("Upstream DNS", ", ".join(parent_ips)))
    custom = dns.get("custom", {})
    custom_ips = custom.get("ips", []) if isinstance(custom, dict) else []
    if custom_ips:
        fields.append(("Custom DNS", ", ".join(custom_ips)))
    return fields


def _show_location_fields(geo_ip: Any) -> List[Tuple[str, Any]]:
    """Location rows (matches _network_location_panel)."""
    if not geo_ip or not isinstance(geo_ip, dict):
        return []
    fields: List[Tuple[str, Any]] = []
    city = geo_ip.get("city")
    region = geo_ip.get("region") or geo_ip.get("regionName")
    country = geo_ip.get("countryName") or geo_ip.get("countryCode")
    location_parts = [p for p in [city, region, country] if p]
    if location_parts:
        fields.append(("Location", ", ".join(location_parts)))
    if geo_ip.get("timezone"):
        fields.append(("Timezone", geo_ip.get("timezone")))
    if geo_ip.get("org"):
        fields.append(("Organization", geo_ip.get("org")))
    if geo_ip.get("asn"):
        fields.append(("ASN", f"AS{geo_ip.get('asn')}"))
    return fields


def _speed_value(info: Any) -> Any:
    """Extract the numeric value of a speed test sub-result, defaulting to 0."""
    return info.get("value", 0) if isinstance(info, dict) else 0


def _format_mbps(value: Any) -> str:
    """Format a throughput value as Mbps, one decimal for floats."""
    value_str = f"{value:.1f}" if isinstance(value, float) else str(value)
    return f"{value_str} Mbps"


def _show_speed_fields(speed: Any) -> List[Tuple[str, Any]]:
    """Speed test rows (matches _network_speed_panel)."""
    if not speed:
        return []
    fields: List[Tuple[str, Any]] = []
    down_value = _speed_value(speed.get("down", {}))
    up_value = _speed_value(speed.get("up", {}))
    latency_value = _speed_value(speed.get("latency", {}))
    if down_value:
        fields.append(("Download", _format_mbps(down_value)))
    if up_value:
        fields.append(("Upload", _format_mbps(up_value)))
    if latency_value:
        fields.append(("Latency", f"{latency_value} ms"))
    test_date = speed.get("date")
    if test_date and test_date != "Unknown":
        if "T" in str(test_date):
            test_date = str(test_date)[:19].replace("T", " ")
        fields.append(("Tested", test_date))
    return fields


def get_network_list_data(network: Union[Dict[str, Any], Any]) -> Dict[str, Any]:
    """Get curated network data for list output.

    Uses get_network_show_fields() as the single source of truth.

    Args:
        network: Network dict or model object

    Returns:
        Dictionary with curated fields for list output
    """
    return {label: value for label, value in get_network_show_fields(network)}


# ==================== Main Network Details Function ====================


def print_network_details(
    network: Union[Dict[str, Any], Any], detail_level: DetailLevel = "brief"
) -> None:
    """Print network information with configurable detail level.

    Args:
        network: Network dict or model object
        detail_level: "brief" or "full"
    """
    # Normalize to dict if needed
    if isinstance(network, dict):
        net = normalize_network(network) if "_raw" not in network else network
    else:
        # Legacy model support - convert to dict
        if hasattr(network, "model_dump"):
            net = normalize_network(network.model_dump())
        else:
            net = normalize_network(vars(network))

    extensive = detail_level == "full"

    # Basic info panel (always shown)
    console.print(_network_basic_panel(net, extensive))

    if not extensive:
        # Brief view panels
        health_panel = _network_health_panel(net)
        if health_panel:
            console.print(health_panel)

        console.print(_network_connection_panel(net))

        location_panel = _network_location_panel(net)
        if location_panel:
            console.print(location_panel)

        dhcp_panel = _network_dhcp_panel(net)
        if dhcp_panel:
            console.print(dhcp_panel)

        dns_panel = _network_dns_brief_panel(net)
        if dns_panel:
            console.print(dns_panel)

        console.print(_network_settings_panel(net))

        speed_panel = _network_speed_panel(net)
        if speed_panel:
            console.print(speed_panel)
    else:
        # Extensive view - show all panels
        console.print(_network_connection_panel(net))

        location_panel = _network_location_panel(net)
        if location_panel:
            console.print(location_panel)

        dhcp_panel = _network_dhcp_panel(net)
        if dhcp_panel:
            console.print(dhcp_panel)

        dns_panel = _network_dns_brief_panel(net)
        if dns_panel:
            console.print(dns_panel)

        console.print(_network_settings_panel(net))
        console.print(_network_guest_panel(net))

        speed_panel = _network_speed_panel(net)
        if speed_panel:
            console.print(speed_panel)

        health_panel = _network_health_panel(net)
        if health_panel:
            console.print(health_panel)


def print_network_dhcp_view(cli_ctx: EeroCliContext, data: Dict[str, Any]) -> None:
    """Render `network dhcp show` (dhcp/lease/connection/ip_settings/wan_type).

    Read straight from the `get_network` envelope (migration plan §4,
    `network dhcp show` row); each sub-object's shape beyond the key name is
    undocumented, so this goes through the generic key/value renderer.
    """
    render_generic(cli_ctx, data, "eero.network.dhcp.show/v1")
