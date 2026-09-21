"""Transformers for converting raw API responses to usable data structures.

This package provides utilities to transform raw JSON responses from the
eero-api library into structured data for display and processing.
"""

from .account import extract_premium_customer
from .base import extract_data, extract_id_from_url, extract_list, safe_get
from .device import extract_device, extract_devices, normalize_device
from .dns_policy import extract_dns_policy
from .eero import extract_eero, extract_eeros, normalize_eero
from .entitlements import extract_entitlements
from .events import (
    extract_channel_utilization,
    extract_events,
    extract_next_cursor,
    extract_scan,
)
from .members import extract_invites, extract_members, extract_members_list
from .network import extract_network, extract_networks, normalize_network, normalize_network_status
from .notifications import (
    extract_history_next_cursor,
    extract_notification_history,
    extract_notification_settings,
    extract_unread,
    extract_unread_flag,
)
from .permissions import extract_capability_map, extract_permissions, extract_role
from .profile import extract_profile, extract_profiles, normalize_profile

__all__ = [
    # Base utilities
    "extract_data",
    "extract_list",
    "extract_id_from_url",
    "safe_get",
    # Network
    "extract_networks",
    "extract_network",
    "normalize_network",
    "normalize_network_status",
    # Device
    "extract_devices",
    "extract_device",
    "normalize_device",
    # Eero
    "extract_eeros",
    "extract_eero",
    "normalize_eero",
    # Profile
    "extract_profiles",
    "extract_profile",
    "normalize_profile",
    # Entitlements
    "extract_entitlements",
    # Account
    "extract_premium_customer",
    # Events
    "extract_events",
    "extract_next_cursor",
    "extract_scan",
    "extract_channel_utilization",
    # Permissions
    "extract_permissions",
    "extract_role",
    "extract_capability_map",
    # Notifications
    "extract_notification_settings",
    "extract_unread",
    "extract_unread_flag",
    "extract_notification_history",
    "extract_history_next_cursor",
    # DNS policy
    "extract_dns_policy",
    # Members
    "extract_members",
    "extract_members_list",
    "extract_invites",
]
