"""Device transformer for raw API responses."""

from datetime import datetime
from typing import Any, Dict, List

from .base import extract_data, extract_id_from_url, extract_list


def extract_devices(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract device list from raw API response.

    Args:
        raw: Raw API response from get_devices()

    Returns:
        List of device data dicts
    """
    return extract_list(raw, "devices")


def extract_device(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Extract single device from raw API response.

    Args:
        raw: Raw API response from get_device()

    Returns:
        Device data dict
    """
    return extract_data(raw)


def normalize_device(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize device data for consistent access.

    Args:
        data: Raw device data dict

    Returns:
        Normalized device data dict
    """
    if not data:
        return {}

    # Extract ID from URL
    device_id = extract_id_from_url(data.get("url"))

    # Extract network ID from URL
    url = data.get("url", "")
    parts = url.split("/")
    network_id = parts[-3] if len(parts) >= 4 else None

    # Get display name (prefer nickname, then hostname, then model)
    display_name = data.get("nickname") or data.get("hostname") or data.get("display_name")

    # Extract source info
    source = data.get("source", {}) or {}
    source_location = source.get("location") if isinstance(source, dict) else None
    is_gateway = source.get("is_gateway", False) if isinstance(source, dict) else False

    # Extract connectivity info
    connectivity = data.get("connectivity", {}) or {}
    signal = connectivity.get("signal") if isinstance(connectivity, dict) else None
    frequency = connectivity.get("frequency") if isinstance(connectivity, dict) else None

    # Extract profile info
    profile = data.get("profile", {}) or {}
    profile_url = profile.get("url") if isinstance(profile, dict) else None
    profile_id = extract_id_from_url(profile_url) if profile_url else None
    profile_name = profile.get("name") if isinstance(profile, dict) else None

    # Parse timestamps
    last_active = None
    first_active = None
    if data.get("last_active"):
        try:
            last_active = datetime.fromisoformat(data["last_active"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    if data.get("first_active"):
        try:
            first_active = datetime.fromisoformat(data["first_active"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    return {
        # Core identification
        "id": device_id,
        "url": data.get("url"),
        "mac": data.get("mac"),
        "eui64": data.get("eui64"),
        "manufacturer": data.get("manufacturer"),
        # Names
        "nickname": data.get("nickname"),
        "hostname": data.get("hostname"),
        "display_name": display_name,
        "model_name": data.get("model_name"),
        # IP addresses
        "ip": data.get("ip"),
        "ips": data.get("ips", []),
        "ipv4": data.get("ipv4"),
        "ipv6_addresses": data.get("ipv6_addresses", []),
        # Connection status
        "connected": data.get("connected", False),
        "wireless": data.get("wireless", False),
        "connection_type": data.get("connection_type"),
        # Source info
        "source_location": source_location,
        "is_gateway": is_gateway,
        "source": source,
        # Connectivity
        "signal": signal,
        "frequency": frequency,
        "connectivity": connectivity,
        # Profile
        "profile_id": profile_id,
        "profile_name": profile_name,
        "profile": profile,
        # Status flags
        "blocked": data.get("blocked", False),
        "blacklisted": data.get("blocked", False),  # Alias
        "paused": data.get("paused", False),
        "is_guest": data.get("is_guest", False),
        "is_private": data.get("is_private", False),
        "prioritized": data.get("prioritized", False),
        # Timestamps
        "last_active": last_active,
        "first_active": first_active,
        # Additional
        "network_id": network_id,
        "device_type": data.get("device_type"),
        "usage": data.get("usage"),
        "interface": data.get("interface"),
        "ssid": data.get("ssid"),
        "channel": data.get("channel"),
        # Keep raw data
        "_raw": data,
    }
