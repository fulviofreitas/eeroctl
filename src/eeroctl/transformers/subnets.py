"""Transformers for the eero-api 8.0.1 subnet reads.

Facade methods (`eero.EeroClient`, eero-api 8.0.1 `client.py`):
    get_subnets_config(network_id=None) -> Dict[str, Any]  -- client.py:2991
    get_subnet_content_filters(subnet_id, network_id=None) -> Dict[str, Any]
        -- client.py:3023

Response shapes are undocumented beyond the envelope.
"""

from typing import Any, Dict

from .base import extract_data


def extract_subnets_config(raw: Dict[str, Any]) -> Any:
    """Unwrap the `data` field of a `get_subnets_config` envelope."""
    return extract_data(raw)


def extract_subnet_content_filters(raw: Dict[str, Any]) -> Any:
    """Unwrap the `data` field of a `get_subnet_content_filters` envelope."""
    return extract_data(raw)
