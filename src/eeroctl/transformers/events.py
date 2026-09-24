"""Transformers for the eero-api 8.0.1 events/telemetry family.

Facade methods (`eero.EeroClient`, eero-api 8.0.1 `client.py`):
    get_app_events(network_id=None, *, page_size=None, timestamp=None)
        -> Dict[str, Any]  -- client.py:2316
    get_network_scan(network_id=None) -> Dict[str, Any]  -- client.py:2332
    get_channel_utilization(network_id=None, *, start, end, busy_threshold=None,
        eero_id=None, band=None, granularity=None, gap_data_placeholder=None)
        -> Dict[str, Any]  -- client.py:2339

All three are plain, live-verified GETs; shapes are undocumented (migration
plan §4, `network events`/`network scan`/`network channels` rows), so phase A
only unwraps the envelope.
"""

from typing import Any, Dict, Optional

from .base import extract_data

# Candidate keys for the app-events pagination cursor. The SDK docs (wiki
# Examples.md: "pass the cursor value from this page's data as timestamp=")
# confirm the cursor comes from `data`, but not its exact key; phase A tries
# the most likely candidates and falls back to None (no "next page" shown)
# until a live sample (§5.3) pins the real key down.
_CURSOR_KEY_CANDIDATES = ("next_timestamp", "next_cursor", "next", "cursor")


def extract_events(raw: Dict[str, Any]) -> Any:
    """Unwrap the `data` field of a `get_app_events` envelope."""
    return extract_data(raw)


def extract_next_cursor(events_data: Any) -> Optional[str]:
    """Best-effort extraction of the app-events pagination cursor.

    Args:
        events_data: The `data` payload already returned by `extract_events`.

    Returns:
        The cursor value for `--cursor` on the next call, or `None` if the
        payload isn't a dict or doesn't carry a recognised cursor key.
    """
    if not isinstance(events_data, dict):
        return None
    for key in _CURSOR_KEY_CANDIDATES:
        value = events_data.get(key)
        if value:
            return str(value)
    return None


def extract_scan(raw: Dict[str, Any]) -> Any:
    """Unwrap the `data` field of a `get_network_scan` envelope."""
    return extract_data(raw)


def extract_channel_utilization(raw: Dict[str, Any]) -> Any:
    """Unwrap the `data` field of a `get_channel_utilization` envelope."""
    return extract_data(raw)
