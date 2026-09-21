"""Transformers for the eero-api 8.0.1 WPA3-per-band and fast-transition reads.

Facade methods (`eero.EeroClient`, eero-api 8.0.1 `client.py`):
    get_wpa3_per_band(network_id=None) -> Dict[str, Any]  -- client.py:2736
    get_fast_transition(network_id=None) -> Dict[str, Any]  -- client.py:2770

Only the corresponding *setters'* kwarg names are documented
(`set_wpa3_per_band(*, band_2_4_ghz=None, band_5_ghz=None)` -- `wpa3.py:149`;
`set_fast_transition(enabled: bool, ...)`); the GET response shapes are not,
so phase A only unwraps the envelope.
"""

from typing import Any, Dict

from .base import extract_data


def extract_wpa3_per_band(raw: Dict[str, Any]) -> Any:
    """Unwrap the `data` field of a `get_wpa3_per_band` envelope."""
    return extract_data(raw)


def extract_fast_transition(raw: Dict[str, Any]) -> Any:
    """Unwrap the `data` field of a `get_fast_transition` envelope."""
    return extract_data(raw)
