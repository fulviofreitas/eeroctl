"""Network formatting utilities for the Eero CLI.

This module provides formatting functions for displaying network data.
"""

from typing import List, Optional

from eero.models.network import Network
from rich.panel import Panel
from rich.table import Table

from .base import (
    DetailLevel,
    build_panel,
    console,
    field,
    field_bool,
    field_status,
    format_bool,
    format_network_status,
    get_network_status_value,
)

# ==================== Network Table ====================


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
        status_value = get_network_status_value(network)
        display_status, status_style = format_network_status(status_value)
        table.add_row(
            network.id,
            network.name,
            f"[{status_style}]{display_status}[/{status_style}]",
            network.public_ip or "Unknown",
            network.isp_name or "Unknown",
            network.created_at.strftime("%Y-%m-%d") if network.created_at else "Unknown",
        )

    return table


# ==================== Network Brief View Panels ====================


def _network_basic_panel(network: Network, extensive: bool = False) -> Panel:
    """Build the basic network info panel."""
    status_value = get_network_status_value(network)
    display_status, status_style = format_network_status(status_value)
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
        if network.owner:
            lines.append(field("Owner", network.owner))
        if network.network_customer_type:
            lines.append(field("Type", network.network_customer_type))

        lines.append(field_bool("Guest Network", network.guest_network_enabled))

        updates_info = getattr(network, "updates", {})
        if updates_info and updates_info.get("has_update", False):
            target_fw = updates_info.get("target_firmware", "")
            lines.append(f"[bold]Update:[/bold] [yellow]Available ({target_fw})[/yellow]")

    return build_panel(lines, f"Network: {network.name}", "blue")


def _network_health_panel(network: Network) -> Optional[Panel]:
    """Build the network health panel for brief view."""
    health_info = getattr(network, "health", {})
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


def _network_connection_panel(network: Network) -> Panel:
    """Build the connection info panel for brief view."""
    lines = [
        field("Gateway Type", network.gateway),
        field("WAN Type", network.wan_type),
        field("Gateway IP", network.gateway_ip),
    ]

    backup_enabled = getattr(network, "backup_internet_enabled", False)
    if backup_enabled:
        lines.append("[bold]Backup Internet:[/bold] [green]Enabled[/green]")

    ip_settings = getattr(network, "ip_settings", {})
    if ip_settings and ip_settings.get("double_nat", False):
        lines.append("[bold]Double NAT:[/bold] [yellow]Detected[/yellow]")

    return build_panel(lines, "Connection", "green")


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
    return build_panel(lines, "DHCP Configuration", "cyan")


def _network_dns_brief_panel(network: Network) -> Optional[Panel]:
    """Build the DNS info panel for brief view."""
    dns_info = getattr(network, "dns", {})
    premium_dns = getattr(network, "premium_dns", {})

    if not dns_info and not premium_dns:
        return None

    lines = []

    if dns_info:
        mode = dns_info.get("mode", "automatic")
        lines.append(field("DNS Mode", mode))

        caching = dns_info.get("caching", False)
        lines.append(field_bool("DNS Caching", caching))

        custom_ips = dns_info.get("custom", {}).get("ips", [])
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

    down_value = network.speed_test.get("down", {}).get("value", 0)
    up_value = network.speed_test.get("up", {}).get("value", 0)
    latency_value = network.speed_test.get("latency", {}).get("value", 0)
    test_date = network.speed_test.get("date", "Unknown")

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


def _network_ddns_panel(network: Network) -> Optional[Panel]:
    """Build the DDNS panel for brief view."""
    ddns_info = getattr(network, "ddns", {})
    if not ddns_info or not ddns_info.get("enabled", False):
        return None

    subdomain = ddns_info.get("subdomain", "")
    lines = [
        "[bold]DDNS:[/bold] [green]Enabled[/green]",
        field("Subdomain", subdomain),
    ]

    return build_panel(lines, "Dynamic DNS", "blue")


def _network_integrations_panel(network: Network) -> Optional[Panel]:
    """Build the integrations panel for brief view."""
    amazon_linked = getattr(network, "amazon_account_linked", False)
    alexa_skill = getattr(network, "alexa_skill", False)
    homekit_info = getattr(network, "homekit", {})
    homekit_enabled = homekit_info.get("enabled", False) if homekit_info else False

    if not (amazon_linked or alexa_skill or homekit_enabled):
        return None

    lines = []
    if amazon_linked:
        lines.append("[bold]Amazon:[/bold] [green]Linked[/green]")
    if alexa_skill:
        lines.append("[bold]Alexa:[/bold] [green]Enabled[/green]")
    if homekit_enabled:
        lines.append("[bold]HomeKit:[/bold] [green]Enabled[/green]")

    return build_panel(lines, "Integrations", "blue")


def _network_organization_panel(network: Network) -> Optional[Panel]:
    """Build the organization/ISP panel for brief view."""
    org_info = getattr(network, "organization", {})
    if not org_info:
        return None

    org_name = org_info.get("name")
    org_type = org_info.get("type")

    if not org_name:
        return None

    lines = [field("Organization", org_name)]
    if org_type:
        lines.append(field("Type", org_type))

    return build_panel(lines, "ISP Organization", "blue")


def _network_premium_brief_panel(network: Network) -> Optional[Panel]:
    """Build the premium status panel for brief view."""
    premium_info = getattr(network, "premium_details", {})
    premium_status = getattr(network, "premium_status", None)

    if not premium_info and not premium_status:
        return None

    lines = []

    if premium_status:
        status_style = "green" if premium_status == "active" else "yellow"
        lines.append(f"[bold]Status:[/bold] [{status_style}]{premium_status}[/{status_style}]")

    if premium_info:
        tier = premium_info.get("tier")
        if tier:
            lines.append(field("Tier", tier))

    return build_panel(lines, "Premium", "magenta") if lines else None


def _network_resources_panel(network: Network) -> Optional[Panel]:
    """Build the available resources panel."""
    resources = getattr(network, "resources", {})
    if not resources:
        return None

    lines = ["[bold]Available Resources:[/bold]"] + [
        f"  • {key}: {value}" for key, value in resources.items()
    ]
    return build_panel(lines, "Available Resources", "cyan")


# ==================== Network Extensive View Panels ====================


def _network_connection_extensive_panel(network: Network) -> Panel:
    """Build the connection info panel for extensive view."""
    lines = [
        field("Gateway Type", network.gateway),
        field("WAN Type", network.wan_type),
        field("Gateway IP", network.gateway_ip),
        field("Connection Mode", network.connection_mode),
        field("Auto Setup Mode", network.auto_setup_mode),
        field_bool("Backup Internet", network.backup_internet_enabled),
        field_bool("Power Saving", network.power_saving),
    ]
    return build_panel(lines, "Connection Information", "green")


def _network_geo_panel(network: Network) -> Optional[Panel]:
    """Build the geographic info panel for extensive view."""
    geo_info = getattr(network, "geo_ip", {})
    if not geo_info:
        return None

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
    return build_panel(lines, "Geographic Information", "yellow")


def _network_dns_extensive_panel(network: Network) -> Optional[Panel]:
    """Build the DNS configuration panel for extensive view."""
    dns_info = getattr(network, "dns", {})
    if not dns_info:
        return None

    parent_ips = ", ".join(dns_info.get("parent", {}).get("ips", []))
    custom_ips = ", ".join(dns_info.get("custom", {}).get("ips", []))

    lines = [
        field("DNS Mode", dns_info.get("mode")),
        field_bool("DNS Caching", dns_info.get("caching", False)),
        field("Parent DNS", parent_ips or "None"),
        field("Custom DNS", custom_ips or "None"),
    ]
    return build_panel(lines, "DNS Configuration", "cyan")


def _network_guest_panel(network: Network) -> Panel:
    """Build the guest network panel for extensive view."""
    guest_password = "[dim]********[/dim]" if network.guest_network_password else "N/A"
    lines = [
        field_bool("Guest Network", network.guest_network_enabled),
        field("Guest Network Name", network.guest_network_name, "N/A"),
        field("Guest Network Password", guest_password),
    ]
    return build_panel(lines, "Guest Network", "magenta")


def _network_health_extensive_panel(network: Network) -> Optional[Panel]:
    """Build the network health panel for extensive view."""
    health_info = getattr(network, "health", {})
    if not health_info:
        return None

    lines = [
        field("Internet Status", health_info.get("internet", {}).get("status")),
        field_bool("ISP Up", health_info.get("internet", {}).get("isp_up", False)),
        field("Eero Network Status", health_info.get("eero_network", {}).get("status")),
    ]
    return build_panel(lines, "Network Health", "green")


def _network_organization_extensive_panel(network: Network) -> Optional[Panel]:
    """Build the organization panel for extensive view."""
    org_info = getattr(network, "organization", {})
    if not org_info:
        return None

    lines = [
        field("Organization ID", org_info.get("id")),
        field("Organization Name", org_info.get("name")),
        field("Organization Brand", org_info.get("brand")),
        field("Organization Type", org_info.get("type")),
    ]
    return build_panel(lines, "Organization", "blue")


def _network_premium_panel(network: Network) -> Optional[Panel]:
    """Build the premium details panel for extensive view."""
    premium_info = getattr(network, "premium_details", {})
    if not premium_info:
        return None

    lines = [
        field("Tier", premium_info.get("tier")),
        field("Payment Method", premium_info.get("payment_method")),
        field("Interval", premium_info.get("interval")),
        field("Next Billing", premium_info.get("next_billing_event_date")),
        field_bool("My Subscription", premium_info.get("is_my_subscription", False)),
        field_bool("Has Payment Info", premium_info.get("has_payment_info", False)),
    ]
    return build_panel(lines, "Premium Details", "magenta")


def _network_updates_panel(network: Network) -> Optional[Panel]:
    """Build the updates panel for extensive view."""
    updates_info = getattr(network, "updates", {})
    if not updates_info:
        return None

    lines = [
        field_bool("Update Required", updates_info.get("update_required", False)),
        field_bool("Can Update Now", updates_info.get("can_update_now", False)),
        field_bool("Has Update", updates_info.get("has_update", False)),
        field("Target Firmware", updates_info.get("target_firmware")),
        field("Preferred Update Hour", updates_info.get("preferred_update_hour")),
    ]
    return build_panel(lines, "Updates", "yellow")


def _network_ddns_extensive_panel(network: Network) -> Optional[Panel]:
    """Build the DDNS panel for extensive view."""
    ddns_info = getattr(network, "ddns", {})
    if not ddns_info:
        return None

    lines = [
        field_bool("DDNS Enabled", ddns_info.get("enabled", False)),
        field("Subdomain", ddns_info.get("subdomain")),
    ]
    return build_panel(lines, "DDNS", "cyan")


def _network_homekit_panel(network: Network) -> Optional[Panel]:
    """Build the HomeKit panel for extensive view."""
    homekit_info = getattr(network, "homekit", {})
    if not homekit_info:
        return None

    lines = [
        field_bool("HomeKit Enabled", homekit_info.get("enabled", False)),
        field_bool("Managed Network", homekit_info.get("managedNetworkEnabled", False)),
    ]
    return build_panel(lines, "HomeKit", "green")


def _network_amazon_panel(network: Network) -> Panel:
    """Build the Amazon integration panel for extensive view."""
    lines = [
        field_bool("Amazon Account Linked", getattr(network, "amazon_account_linked", False)),
        field_bool("FFS", getattr(network, "ffs", False)),
        field_bool("Alexa Skill", getattr(network, "alexa_skill", False)),
    ]
    return build_panel(lines, "Amazon Integration", "blue")


def _network_ip_settings_panel(network: Network) -> Optional[Panel]:
    """Build the IP settings panel for extensive view."""
    ip_settings = getattr(network, "ip_settings", {})
    if not ip_settings:
        return None

    lines = [
        field_bool("Double NAT", ip_settings.get("double_nat", False)),
        field("Public IP", ip_settings.get("public_ip")),
    ]
    return build_panel(lines, "IP Settings", "yellow")


def _network_premium_dns_panel(network: Network) -> Optional[Panel]:
    """Build the premium DNS panel for extensive view."""
    premium_dns = getattr(network, "premium_dns", {})
    if not premium_dns:
        return None

    dns_policies = premium_dns.get("dns_policies", {})
    lines = [
        field_bool("DNS Policies Enabled", premium_dns.get("dns_policies_enabled", False)),
        field("DNS Provider", premium_dns.get("dns_provider")),
        field_bool("Block Malware", dns_policies.get("block_malware", False)),
        field_bool("Ad Block", dns_policies.get("ad_block", False)),
    ]
    return build_panel(lines, "Premium DNS", "magenta")


def _network_last_reboot_panel(network: Network) -> Optional[Panel]:
    """Build the last reboot panel for extensive view."""
    last_reboot = getattr(network, "last_reboot", None)
    if not last_reboot:
        return None

    return build_panel([field("Last Reboot", last_reboot)], "Last Reboot", "red")


# ==================== Main Network Details Function ====================


def print_network_details(network: Network, detail_level: DetailLevel = "brief") -> None:
    """Print network information with configurable detail level.

    Args:
        network: Network object
        detail_level: "brief" or "full"
    """
    extensive = detail_level == "full"

    # Basic info panel (always shown)
    console.print(_network_basic_panel(network, extensive))

    if not extensive:
        # Brief view panels

        # Health status
        health_panel = _network_health_panel(network)
        if health_panel:
            console.print(health_panel)

        # Connection info
        console.print(_network_connection_panel(network))

        # DHCP info
        dhcp_panel = _network_dhcp_panel(network)
        if dhcp_panel:
            console.print(dhcp_panel)

        # DNS & Security
        dns_panel = _network_dns_brief_panel(network)
        if dns_panel:
            console.print(dns_panel)

        # Network settings
        console.print(_network_settings_panel(network))

        # Speed test
        speed_panel = _network_speed_panel(network)
        if speed_panel:
            console.print(speed_panel)

        # Optional brief panels
        for panel_func in [
            _network_ddns_panel,
            _network_integrations_panel,
            _network_organization_panel,
            _network_premium_brief_panel,
        ]:
            panel = panel_func(network)
            if panel:
                console.print(panel)

    else:
        # Extensive view panels
        console.print(_network_connection_extensive_panel(network))

        # Optional extensive panels (first group)
        for panel_func in [
            _network_geo_panel,
        ]:
            panel = panel_func(network)
            if panel:
                console.print(panel)

        # DHCP
        dhcp_panel = _network_dhcp_panel(network)
        if dhcp_panel:
            console.print(dhcp_panel)

        # DNS config
        dns_panel = _network_dns_extensive_panel(network)
        if dns_panel:
            console.print(dns_panel)

        # Settings
        console.print(_network_settings_panel(network))

        # Guest network
        console.print(_network_guest_panel(network))

        # Speed test
        speed_panel = _network_speed_panel(network)
        if speed_panel:
            console.print(speed_panel)

        # Optional extensive panels
        for panel_func in [
            _network_health_extensive_panel,
            _network_organization_extensive_panel,
            _network_premium_panel,
            _network_updates_panel,
            _network_ddns_extensive_panel,
            _network_homekit_panel,
        ]:
            panel = panel_func(network)
            if panel:
                console.print(panel)

        # Amazon integration (always shown in extensive)
        console.print(_network_amazon_panel(network))

        # Optional extensive panels (final group)
        for panel_func in [
            _network_ip_settings_panel,
            _network_premium_dns_panel,
            _network_last_reboot_panel,
            _network_resources_panel,
        ]:
            panel = panel_func(network)
            if panel:
                console.print(panel)
