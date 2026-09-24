"""Transformers for the eero-api 8.0.1 transfer-stats read.

Facade method (`eero.EeroClient`, eero-api 8.0.1 `client.py`):
    get_transfer_stats(network_id=None, device_id=None) -> Dict[str, Any]
        -- client.py:1569

Response shape is undocumented beyond the envelope.
"""

from typing import Any, Dict

from .base import extract_data


def extract_transfer_stats(raw: Dict[str, Any]) -> Any:
    """Unwrap the `data` field of a `get_transfer_stats` envelope."""
    return extract_data(raw)
