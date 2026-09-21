"""Transformers for the eero-api 8.0.1 members/invites family.

Facade methods (`eero.EeroClient`, eero-api 8.0.1 `client.py`):
    get_members(network_id=None) -> Dict[str, Any]  -- client.py:2572 (verified)
    get_invites(network_id=None) -> Dict[str, Any]   -- client.py:2579 (unverified)

`get_members`'s shape is documented at the SDK layer
(`eero/api/members.py:62`): "Raw API response: {"meta": ..., "data":
{"members": [...]}}". `get_invites`'s shape is undocumented.
"""

from typing import Any, Dict, List

from .base import extract_data


def extract_members(raw: Dict[str, Any]) -> Any:
    """Unwrap the `data` field of a `get_members` envelope."""
    return extract_data(raw)


def extract_members_list(members_data: Any) -> List[Dict[str, Any]]:
    """Extract `data.members` (`eero/api/members.py:62`), tolerating a bare list."""
    if isinstance(members_data, dict):
        members = members_data.get("members")
        if isinstance(members, list):
            return members
        return []
    if isinstance(members_data, list):
        return members_data
    return []


def extract_invites(raw: Dict[str, Any]) -> Any:
    """Unwrap the `data` field of a `get_invites` envelope."""
    return extract_data(raw)
