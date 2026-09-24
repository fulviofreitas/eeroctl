"""Transformers for the eero-api 8.0.1 entitlements/capabilities family.

Facade methods (`eero.EeroClient`, eero-api 8.0.1 `client.py`):
    get_entitlement_features(network_id=None) -> Dict[str, Any]  -- client.py:2292
    get_upsell_features(network_id=None)       -> Dict[str, Any]  -- client.py:2300
    get_model_capabilities(network_id=None)    -> Dict[str, Any]  -- client.py:2305

All three are plain GETs returning `{"meta": {...}, "data": {...}}`; the shape of
`data` is undocumented (migration plan §4, `network entitlements *` row), so phase A
only unwraps the envelope and defers to the generic key/value renderer
(`formatting/generic.py`) rather than shipping a bespoke table.
"""

from typing import Any, Dict

from .base import extract_data


def extract_entitlements(raw: Dict[str, Any]) -> Any:
    """Unwrap the `data` field of an entitlements-family envelope.

    Shared by `network entitlements show|upsell|capabilities` -- all three
    facade methods above return the same `{"meta": ..., "data": ...}` shape.

    Args:
        raw: The raw envelope returned by `get_entitlement_features`,
            `get_upsell_features`, or `get_model_capabilities`.

    Returns:
        The `data` payload (typically a dict; passed straight through
        whatever eero-api actually returns).
    """
    return extract_data(raw)
