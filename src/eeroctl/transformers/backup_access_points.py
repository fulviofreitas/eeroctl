"""Transformers for the eero-api 8.0.1 backup-access-point reads.

Facade methods (`eero.EeroClient`, eero-api 8.0.1 `client.py`):
    list_backup_access_points(network_id=None) -> Dict[str, Any]  -- client.py:2910
    discover_backup_ssids(network_id=None) -> Dict[str, Any]  -- client.py:2974 (GET, verified)

`backup show`/`backup status` were already rewired in commit 5 onto
`get_backup_internet`/`get_cellular_backup_usage`/`get_cellular_backup_events`;
this module only covers the access-point family, which commit 5 left alone.
Response shapes are undocumented beyond the envelope.
"""

from typing import Any, Dict

from .base import extract_data


def extract_backup_access_points(raw: Dict[str, Any]) -> Any:
    """Unwrap the `data` field of a `list_backup_access_points` envelope."""
    return extract_data(raw)


def extract_backup_ssid_discovery(raw: Dict[str, Any]) -> Any:
    """Unwrap the `data` field of a `discover_backup_ssids` envelope."""
    return extract_data(raw)
