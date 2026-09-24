"""Transformers for the eero-api 8.0.1 power-saving schedules read.

Facade method (`eero.EeroClient`, eero-api 8.0.1 `client.py`):
    get_power_saving_schedules(network_id=None) -> Dict[str, Any]  -- client.py:2830

Verified read (`eero/api/power_saving.py:108`); response shape beyond the
envelope is undocumented.
"""

from typing import Any, Dict

from .base import extract_data


def extract_power_saving_schedules(raw: Dict[str, Any]) -> Any:
    """Unwrap the `data` field of a `get_power_saving_schedules` envelope."""
    return extract_data(raw)
