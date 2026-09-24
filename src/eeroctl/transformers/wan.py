"""Transformers for the eero-api 8.0.1 multi-static-IP read.

Facade method (`eero.EeroClient`, eero-api 8.0.1 `client.py`):
    get_multistaticip(network_id=None) -> Dict[str, Any]  -- client.py:3032

Response shape is undocumented beyond the envelope. On a network without the
multi-static-IP feature, the SDK has observed the API return HTTP 404 with
error code `error.network.multistaticip_not_found`
(`eero/api/wan.py:49-51`) -- see `commands/network/wan.py` for how that is
turned into a "not configured" read per the migration plan's Q7 decision.
"""

from typing import Any, Dict

from .base import extract_data


def extract_multistaticip(raw: Dict[str, Any]) -> Any:
    """Unwrap the `data` field of a `get_multistaticip` envelope."""
    return extract_data(raw)
