"""Formatting utilities for the Eero CLI.

This module provides reusable formatting functions for displaying
Eero network data using Rich panels and tables.

This __init__.py re-exports all public functions from submodules
for backward compatibility with existing imports.
"""

# Account formatting
from .account import print_account_premium

# Backup access-points formatting
from .backup_access_points import print_backup_access_points, print_backup_ssid_discovery

# Base utilities
from .base import (
    DetailLevel,
    build_panel,
    console,
    field,
    field_bool,
    field_status,
    format_bool,
    format_datetime,
    format_device_status,
    format_eero_status,
    format_enabled,
    format_network_status,
    get_network_status_value,
)

# Device formatting
from .device import (
    create_devices_table,
    print_device_details,
)

# DNS policy formatting
from .dns_policy import print_dns_policy

# Eero device formatting
from .eero import (
    create_eeros_table,
    print_eero_details,
)

# Entitlements formatting
from .entitlements import (
    print_entitlements_capabilities,
    print_entitlements_show,
    print_entitlements_upsell,
)

# Events formatting
from .events import print_channels, print_events, print_scan

# Generic key/value renderer (undocumented response shapes)
from .generic import render_generic

# Members formatting
from .members import print_invites, print_members

# Miscellaneous formatting
from .misc import (
    create_blacklist_table,
    print_speedtest_results,
)

# Network formatting
from .network import (
    create_network_table,
    print_network_details,
    print_network_dhcp_view,
)

# Notifications formatting
from .notifications import print_notification_history, print_notification_settings, print_unread

# Permissions formatting
from .permissions import print_permissions

# Power-saving formatting
from .power_saving import print_power_saving_schedules

# Profile formatting
from .profile import (
    create_profile_devices_table,
    create_profiles_table,
    print_profile_details,
)

# WPA3 / fast-transition formatting
from .wpa3 import print_fast_transition, print_wpa3_per_band

# Re-export all public names
__all__ = [
    # Base
    "console",
    "DetailLevel",
    "get_network_status_value",
    "format_network_status",
    "format_device_status",
    "format_eero_status",
    "format_bool",
    "format_enabled",
    "build_panel",
    "field",
    "field_bool",
    "field_status",
    "format_datetime",
    # Network
    "create_network_table",
    "print_network_details",
    "print_network_dhcp_view",
    # Eero
    "create_eeros_table",
    "print_eero_details",
    # Device
    "create_devices_table",
    "print_device_details",
    # Profile
    "create_profiles_table",
    "create_profile_devices_table",
    "print_profile_details",
    # Misc
    "print_speedtest_results",
    "create_blacklist_table",
    # Generic
    "render_generic",
    # Entitlements
    "print_entitlements_show",
    "print_entitlements_upsell",
    "print_entitlements_capabilities",
    # Account
    "print_account_premium",
    # Events
    "print_events",
    "print_scan",
    "print_channels",
    # Permissions
    "print_permissions",
    # Notifications
    "print_notification_settings",
    "print_unread",
    "print_notification_history",
    # DNS policy
    "print_dns_policy",
    # Members
    "print_members",
    "print_invites",
    # WPA3 / fast transition
    "print_wpa3_per_band",
    "print_fast_transition",
    # Power saving
    "print_power_saving_schedules",
    # Backup access points
    "print_backup_access_points",
    "print_backup_ssid_discovery",
]
