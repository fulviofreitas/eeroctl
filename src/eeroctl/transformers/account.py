"""Transformers for account-scoped eero-api 8.0.1 endpoints.

Facade method (`eero.EeroClient`, eero-api 8.0.1 `client.py`):
    get_premium_customer() -> Dict[str, Any]  -- client.py:2310

Unlike every other phase-A facade method, `get_premium_customer` takes no
`network_id` at all -- it is account-scoped, not network-scoped (migration
plan §4, `account premium` row). The response shape is undocumented, so
phase A only unwraps the envelope.
"""

from typing import Any, Dict

from .base import extract_data


def extract_premium_customer(raw: Dict[str, Any]) -> Any:
    """Unwrap the `data` field of a `get_premium_customer` envelope.

    Args:
        raw: The raw envelope returned by `get_premium_customer`.

    Returns:
        The `data` payload (passed straight through).
    """
    return extract_data(raw)
