"""Network transformer for raw API responses."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import extract_data, extract_id_from_url, extract_list


def extract_networks(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract network list from raw API response.

    Args:
        raw: Raw API response from get_networks()

    Returns:
        List of network data dicts
    """
    return extract_list(raw, "networks")


def extract_network(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Extract single network from raw API response.

    Args:
        raw: Raw API response from get_network()

    Returns:
        Network data dict
    """
    return extract_data(raw)


def normalize_network_status(status: Optional[str]) -> str:
    """Normalize network status for display.

    Args:
        status: Raw status string from API

    Returns:
        Normalized status string
    """
    if not status:
        return "unknown"

    status_lower = status.lower()
    if status_lower == "connected":
        return "online"
    return status_lower


def normalize_network(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize network data for consistent access.

    Adds computed fields and normalizes status.

    Args:
        data: Raw network data dict

    Returns:
        Normalized network data dict
    """
    if not data:
        return {}

    # Extract ID from URL
    net_id = data.get("id") or extract_id_from_url(data.get("url"))

    # Extract public IP (try wan_ip first, then public_ip)
    public_ip = data.get("wan_ip") or data.get("public_ip")

    # Extract ISP name from geo_ip or isp fields
    geo_ip = data.get("geo_ip", {})
    isp_name = geo_ip.get("isp") if isinstance(geo_ip, dict) else None
    if not isp_name:
        isp_data = data.get("isp", {})
        isp_name = isp_data.get("name") if isinstance(isp_data, dict) else isp_data

    # Normalize status (can be string or {"status": "online"} dict)
    raw_status = data.get("status")
    if isinstance(raw_status, dict):
        raw_status = raw_status.get("status")
    status = normalize_network_status(raw_status)

    # Extract guest network info
    guest_network = data.get("guest_network", {})
    guest_enabled = guest_network.get("enabled", False) if guest_network else False
    guest_name = guest_network.get("name") if guest_network else None
    guest_password = guest_network.get("password") if guest_network else None

    # Extract speed test info
    speed_test = data.get("speed") or data.get("speed_test")

    # Extract DHCP info
    dhcp_data = data.get("dhcp", {})
    if isinstance(dhcp_data, dict):
        custom = dhcp_data.get("custom", {})
        dhcp = {
            "subnet_mask": custom.get("subnet_mask", "255.255.255.0"),
            "starting_address": custom.get("starting_address", ""),
            "ending_address": custom.get("ending_address", ""),
            "lease_time_seconds": custom.get("lease_time_seconds", 86400),
            "dns_server": custom.get("dns_server"),
        }
    else:
        dhcp = None

    # Parse timestamps
    created_at = None
    updated_at = None
    if data.get("created_at"):
        try:
            created_at = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    if data.get("updated_at"):
        try:
            updated_at = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    # Build normalized network dict
    return {
        # Core identification
        "id": net_id,
        "url": data.get("url"),
        "name": data.get("name", "Unknown"),
        "display_name": data.get("display_name"),
        "status": status,
        # Connection info
        "public_ip": public_ip,
        "isp_name": isp_name,
        "gateway": data.get("gateway"),
        "wan_type": data.get("wan_type"),
        "gateway_ip": data.get("gateway_ip"),
        # Settings
        "ipv6_upstream": data.get("ipv6_upstream", False),
        "band_steering": data.get("band_steering", False),
        "thread": data.get("thread", False),
        "upnp": data.get("upnp", False),
        "wpa3": data.get("wpa3", False),
        "sqm": data.get("sqm", False),
        "wireless_mode": data.get("wireless_mode"),
        "mlo_mode": data.get("mlo_mode"),
        # Guest network
        "guest_network_enabled": guest_enabled,
        "guest_network_name": guest_name,
        "guest_network_password": guest_password,
        # DHCP
        "dhcp": dhcp,
        # Speed test
        "speed_test": speed_test,
        # Timestamps
        "created_at": created_at,
        "updated_at": updated_at,
        # Additional data (preserve original)
        "owner": data.get("owner"),
        "network_customer_type": data.get("network_customer_type"),
        "premium_status": data.get("premium_status"),
        "connection_mode": data.get("connection_mode"),
        "auto_setup_mode": data.get("auto_setup_mode"),
        "backup_internet_enabled": data.get("backup_internet_enabled", False),
        "power_saving": data.get("power_saving", False),
        "health": data.get("health"),
        "dns": data.get("dns"),
        "geo_ip": geo_ip,
        "organization": data.get("organization"),
        "premium_details": data.get("premium_details"),
        "updates": data.get("updates"),
        "ddns": data.get("ddns"),
        "homekit": data.get("homekit"),
        "amazon_account_linked": data.get("amazon_account_linked", False),
        "ffs": data.get("ffs", False),
        "alexa_skill": data.get("alexa_skill", False),
        "ip_settings": data.get("ip_settings"),
        "premium_dns": data.get("premium_dns"),
        "last_reboot": data.get("last_reboot"),
        "settings": data.get("settings", {}),
        "resources": data.get("resources"),
        # Keep raw data for access
        "_raw": data,
    }
