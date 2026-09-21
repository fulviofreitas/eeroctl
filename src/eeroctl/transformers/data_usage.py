"""Transformers for the eero-api 8.0.1 data-usage family (closes #46).

Facade methods (`eero.EeroClient`, eero-api 8.0.1 `client.py`), all
keyword-only `start`/`end` (+ `cadence`, required except where noted, +
optional `timezone`):
    get_data_usage(..., cadence required daily|hourly) -- client.py:1578
    get_data_usage_breakdown(..., cadence optional)     -- client.py:1605
    get_devices_data_usage(..., cadence optional, profile_id optional)
        -- client.py:1624
    get_device_data_usage(device_mac, ..., cadence required) -- client.py:1649
    get_eeros_data_usage_summary(..., cadence required) -- client.py:1669
    get_eero_data_usage(eero_id, ..., cadence required) -- client.py:1688
    get_profile_data_usage(profile_id, ..., cadence required) -- client.py:1708
    get_unprofiled_devices_data_usage(..., cadence optional) -- client.py:1728
    get_unprofiled_data_usage_summary(..., cadence required) -- client.py:1747
    get_data_usage_report_settings(network_id=None) -- client.py:1766 (no window)

Response shapes are undocumented beyond the envelope, so phase A only
unwraps it; one accessor covers the whole family.
"""

from typing import Any, Dict

from .base import extract_data


def extract_data_usage(raw: Dict[str, Any]) -> Any:
    """Unwrap the `data` field of any data-usage-family envelope."""
    return extract_data(raw)
