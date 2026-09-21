"""Transformers for the eero-api 8.0.1 speed-test-history reads.

Facade method (`eero.EeroClient`, eero-api 8.0.1 `client.py`):
    get_speed_tests(network_id=None, *, limit=None, start_time=None,
        end_time=None) -> Dict[str, Any]  -- client.py:1206

`network speedtest show` and `network speedtest history` share this one
facade call (`show` is `history --limit 1`, taking the newest entry) so both
commands go through `extract_speed_test_history`/`extract_latest_speed_test`
here rather than duplicating the list/dict-tolerant unwrap logic twice.
"""

from typing import Any, Dict, List, Optional

from .base import extract_data


def extract_speed_test_history(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract the speed-test history list from a `get_speed_tests` envelope.

    Tolerates both a bare list and a single dict (as a one-item list), since
    the exact shape isn't pinned down beyond "a speed test has `down`/`up`/
    `latency`/`date` fields" (pre-existing `speedtest show` code).
    """
    data = extract_data(raw) if isinstance(raw, dict) else None
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return []


def extract_latest_speed_test(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract the newest speed test from a `get_speed_tests(limit=1)` envelope.

    Shared by `network speedtest show` (which calls `get_speed_tests` with
    `limit=1`) so both commands read the history list the same way.
    """
    history = extract_speed_test_history(raw)
    return history[0] if history else None
