"""Formatting utilities for the Eero CLI.

This module provides reusable formatting functions for displaying
Eero network data using Rich panels and tables.

This __init__.py re-exports all public functions from submodules
for backward compatibility with existing imports.
"""

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

# Eero device formatting
from .eero import (
    create_eeros_table,
    print_eero_details,
)

# Miscellaneous formatting
from .misc import (
    create_blacklist_table,
    print_speedtest_results,
)

# Network formatting
from .network import (
    create_network_table,
    print_network_details,
)

# Profile formatting
from .profile import (
    create_profile_devices_table,
    create_profiles_table,
    print_profile_details,
)

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
]
