"""Transformers for the eero-api 8.0.1 DNS content-filtering policy read.

Facade method (`eero.EeroClient`, eero-api 8.0.1 `client.py`):
    get_advanced_content_filter(network_id=None) -> Dict[str, Any]  -- client.py:2428

Premium feature; migration plan §4 (`network dns policy show` row) documents
the shape as `data.allowed_list/blocked_list`.
"""

from typing import Any, Dict

from .base import extract_data


def extract_dns_policy(raw: Dict[str, Any]) -> Any:
    """Unwrap the `data` field of a `get_advanced_content_filter` envelope."""
    return extract_data(raw)
