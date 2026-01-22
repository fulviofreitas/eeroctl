"""Transformers for converting raw API responses to usable data structures.

This package provides utilities to transform raw JSON responses from the
eero-api library into structured data for display and processing.
"""

from .base import extract_data, extract_id_from_url, extract_list
from .device import extract_device, extract_devices, normalize_device
from .eero import extract_eero, extract_eeros, normalize_eero
from .network import extract_network, extract_networks, normalize_network_status
from .profile import extract_profile, extract_profiles, normalize_profile

__all__ = [
    # Base utilities
    "extract_data",
    "extract_list",
    "extract_id_from_url",
    # Network
    "extract_networks",
    "extract_network",
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
]
