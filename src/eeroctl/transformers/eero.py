"""Eero transformer for raw API responses."""

from datetime import datetime
from typing import Any, Dict, List

from .base import extract_data, extract_id_from_url, extract_list


def extract_eeros(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract eero list from raw API response.

    Args:
        raw: Raw API response from get_eeros()

    Returns:
        List of eero data dicts
    """
    return extract_list(raw, "eeros")


def extract_eero(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Extract single eero from raw API response.

    Args:
        raw: Raw API response from get_eero()

    Returns:
        Eero data dict
    """
    return extract_data(raw)


def normalize_eero(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize eero data for consistent access.

    Args:
        data: Raw eero data dict

    Returns:
        Normalized eero data dict
    """
    if not data:
        return {}

    # Extract ID from URL
    eero_id = extract_id_from_url(data.get("url"))

    # Location can be string or dict
    location = data.get("location")
    if isinstance(location, dict):
        location_str = location.get("address") or location.get("city")
    else:
        location_str = location

    # Parse timestamps
    last_heartbeat = None
    joined = None
    if data.get("last_heartbeat"):
        try:
            last_heartbeat = datetime.fromisoformat(
                str(data["last_heartbeat"]).replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            pass
    if data.get("joined"):
        try:
            joined = datetime.fromisoformat(data["joined"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    # Extract nightlight info
    nightlight = data.get("nightlight", {}) or {}
    nightlight_enabled = nightlight.get("enabled", False) if isinstance(nightlight, dict) else False

    return {
        # Core identification
        "id": eero_id,
        "url": data.get("url"),
        "serial": data.get("serial"),
        "mac_address": data.get("mac_address"),
        "model": data.get("model"),
        "model_number": data.get("model_number"),
        # Names and location
        "name": data.get("name") or location_str,
        "location": location_str,
        # Status
        "status": data.get("status", "unknown"),
        "connected": data.get("connected", False),
        "heartbeat_ok": data.get("heartbeat_ok", False),
        "state": data.get("state"),
        # Role
        "is_gateway": data.get("gateway", False) or data.get("is_gateway", False),
        "is_primary": data.get("is_primary_node", False) or data.get("is_primary", False),
        "wired": data.get("wired", False),
        "using_wan": data.get("using_wan", False),
        # Firmware
        "os_version": data.get("os_version") or data.get("os"),
        "firmware_version": data.get("firmware_version"),
        "update_available": data.get("update_available", False),
        # Clients
        "connected_clients_count": data.get("connected_clients_count", 0),
        "connected_wired_clients_count": data.get("connected_wired_clients_count", 0),
        "connected_wireless_clients_count": data.get("connected_wireless_clients_count", 0),
        # LED and nightlight
        "led_on": data.get("led_on"),
        "led_brightness": data.get("led_brightness"),
        "nightlight_enabled": nightlight_enabled,
        "nightlight": nightlight,
        # Performance
        "mesh_quality_bars": data.get("mesh_quality_bars"),
        "uptime": data.get("uptime"),
        "memory_usage": data.get("memory_usage"),
        "cpu_usage": data.get("cpu_usage"),
        "temperature": data.get("temperature"),
        # Network info
        "ip_address": data.get("ip_address"),
        "ethernet_addresses": data.get("ethernet_addresses", []),
        "ethernet_status": data.get("ethernet_status"),
        "bands": data.get("bands", []),
        "provides_wifi": data.get("provides_wifi", True),
        # Timestamps
        "last_heartbeat": last_heartbeat,
        "joined": joined,
        "last_reboot": data.get("last_reboot"),
        # Additional
        "connection_type": data.get("connection_type"),
        "backup_connection": data.get("backup_connection", False),
        "cellular_backup": data.get("cellular_backup"),
        "resources": data.get("resources"),
        "update_status": data.get("update_status"),
        "messages": data.get("messages"),
        # Keep raw data
        "_raw": data,
    }
