"""Profile transformer for raw API responses."""

from typing import Any, Dict, List

from .base import extract_data, extract_id_from_url, extract_list


def extract_profiles(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract profile list from raw API response.

    Args:
        raw: Raw API response from get_profiles()

    Returns:
        List of profile data dicts
    """
    return extract_list(raw, "profiles")


def extract_profile(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Extract single profile from raw API response.

    Args:
        raw: Raw API response from get_profile()

    Returns:
        Profile data dict
    """
    return extract_data(raw)


def normalize_profile(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize profile data for consistent access.

    Args:
        data: Raw profile data dict

    Returns:
        Normalized profile data dict
    """
    if not data:
        return {}

    # Extract ID from URL
    profile_id = extract_id_from_url(data.get("url"))

    # Extract network ID from URL
    url = data.get("url", "")
    parts = url.split("/")
    network_id = parts[-3] if len(parts) >= 4 else None

    # Get devices info
    devices = data.get("devices", [])
    device_count = len(devices)
    device_ids = []
    connected_count = 0
    for device in devices:
        device_url = device.get("url", "")
        if device_url:
            device_ids.append(extract_id_from_url(device_url))
        if device.get("connected", False):
            connected_count += 1

    # Schedule info
    schedule = data.get("schedule", [])
    schedule_enabled = len(schedule) > 0 if schedule else False

    # State info
    state = data.get("state", {})
    state_value = state.get("value", "") if isinstance(state, dict) else ""

    # Premium DNS and content filters
    premium_dns = data.get("premium_dns", {}) or {}
    unified_filters = data.get("unified_content_filters", {}) or {}
    dns_policies = unified_filters.get("dns_policies", {}) or {}

    # Content filter settings
    content_filter = {
        "safe_search": dns_policies.get("safe_search_enabled", False),
        "youtube_restricted": dns_policies.get("youtube_restricted", False),
        "block_adult": dns_policies.get("block_pornographic_content", False),
        "block_illegal": dns_policies.get("block_illegal_content", False),
        "block_violent": dns_policies.get("block_violent_content", False),
    }

    # Custom block/allow lists
    advanced_filters = premium_dns.get("advanced_content_filters", {}) or {}
    custom_block_list = advanced_filters.get("blocked_list", [])
    custom_allow_list = advanced_filters.get("allowed_list", [])

    return {
        # Core identification
        "id": profile_id,
        "url": data.get("url"),
        "network_id": network_id,
        "name": data.get("name", "Unknown"),
        "default": data.get("default", False),
        # Status
        "paused": data.get("paused", False),
        "state": state_value,
        # Devices
        "devices": devices,
        "device_count": device_count,
        "connected_device_count": connected_count,
        "device_ids": device_ids,
        # Schedule
        "schedule": schedule,
        "schedule_enabled": schedule_enabled,
        # Content filtering
        "content_filter": content_filter,
        "custom_block_list": custom_block_list,
        "custom_allow_list": custom_allow_list,
        # Premium features
        "premium_dns": premium_dns,
        "unified_content_filters": unified_filters,
        # Additional
        "resources": data.get("resources"),
        "proxied_nodes": data.get("proxied_nodes", []),
        "usage": data.get("usage"),
        # Keep raw data
        "_raw": data,
    }
