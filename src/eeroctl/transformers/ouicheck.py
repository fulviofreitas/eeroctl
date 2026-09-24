"""Transformers for the eero-api 8.0.1 OUI-check read.

Facade method (`eero.EeroClient`, eero-api 8.0.1 `client.py`):
    get_ouicheck(network_id=None, *, serial, version) -> Dict[str, Any]
        -- client.py:1805; both `serial`/`version` required keyword-only.

Response shape is undocumented beyond the envelope.
"""

from typing import Any, Dict

from .base import extract_data


def extract_ouicheck(raw: Dict[str, Any]) -> Any:
    """Unwrap the `data` field of a `get_ouicheck` envelope."""
    return extract_data(raw)
