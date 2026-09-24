"""Transformers for the eero-api 8.0.1 devices/profiles insights family.

Facade methods (`eero.EeroClient`, eero-api 8.0.1 `client.py`), all premium,
all `start`/`end`/`cadence`/`insight_type` required keyword-only:
    get_devices_insights(network_id=None, *, start, end, cadence, insight_type)
        -- client.py:1308
    get_device_insights(device_id, network_id=None, *, start, end, cadence,
        insight_type) -- client.py:1328
    get_profiles_insights(network_id=None, *, start, end, cadence, insight_type)
        -- client.py:1349
    get_profile_insights(profile_id, network_id=None, *, start, end, cadence,
        insight_type) -- client.py:1369
    get_profile_devices_insights(profile_id, network_id=None, *, start, end,
        cadence, insight_type) -- client.py:1390

<!-- unverified shape --> `get_insights` (the network-level sibling these
five share the `_insights_params` validation with) documents its envelope as
`data.series: [{insight_type, sum, values}]` (`eero/api/insights.py:99-103`),
already relied on by `activity history`/`activity categories`
(`activity.py:91-97`), but the per-device/per-profile breakdown shape these
five return is not independently confirmed, so phase A only unwraps the
envelope.
"""

from typing import Any, Dict

from .base import extract_data


def extract_insights(raw: Dict[str, Any]) -> Any:
    """Unwrap the `data` field of any of the five insights-family envelopes."""
    return extract_data(raw)
