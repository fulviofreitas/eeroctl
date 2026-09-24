"""Transformers for the eero-api 8.0.1 notifications family.

Facade methods (`eero.EeroClient`, eero-api 8.0.1 `client.py`):
    get_notification_settings(network_id=None) -> Dict[str, Any]  -- client.py:2378
    has_unread_notifications(network_id=None)   -> Dict[str, Any]  -- client.py:2399
    get_notification_history(network_id=None, *, timestamp=None)
        -> Dict[str, Any]  -- client.py:2413

`get_notification_settings`'s shape is documented at the SDK layer
(`eero/api/notifications.py:41-43`): "data carries one boolean per event key,
e.g. 'network.updated', 'device.new', 'permissions.updates'". `has_unread`'s
shape is also documented (`notifications.py:114-115`): "Returns a `has_unread`
boolean field in `data`". `get_history`'s shape is undocumented; it reuses the
same best-effort cursor heuristic as `network events` (also `timestamp`-cursor
paginated).
"""

from typing import Any, Dict, Optional

from .base import extract_data
from .events import extract_next_cursor as _extract_next_cursor


def extract_notification_settings(raw: Dict[str, Any]) -> Any:
    """Unwrap the `data` field of a `get_notification_settings` envelope."""
    return extract_data(raw)


def extract_unread(raw: Dict[str, Any]) -> Any:
    """Unwrap the `data` field of a `has_unread_notifications` envelope."""
    return extract_data(raw)


def extract_unread_flag(unread_data: Any) -> Optional[bool]:
    """Extract `data.has_unread` (`eero/api/notifications.py:115`)."""
    if isinstance(unread_data, dict) and "has_unread" in unread_data:
        return bool(unread_data["has_unread"])
    return None


def extract_notification_history(raw: Dict[str, Any]) -> Any:
    """Unwrap the `data` field of a `get_notification_history` envelope."""
    return extract_data(raw)


def extract_history_next_cursor(history_data: Any) -> Optional[str]:
    """Best-effort extraction of the notification-history pagination cursor.

    Shares the candidate-key heuristic with `transformers.events.extract_next_cursor`
    (both endpoints paginate via an opaque `timestamp` cursor of undocumented shape).
    """
    return _extract_next_cursor(history_data)
