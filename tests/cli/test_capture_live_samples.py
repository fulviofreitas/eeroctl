"""Unit tests for `scripts/capture-live-samples.py`'s redaction helper.

Covers only `redact_payload` (and the small helpers it composes) on a
synthetic, in-memory payload -- no subprocess, no real `eero` CLI
invocation, no network access. The script's filename contains a hyphen so
it isn't importable as a normal module; it's loaded via
`importlib.util.spec_from_file_location` instead (see `_load_module`
below).

Per the eero-api 8.0.1 migration plan §5.3, the live-sample capture script
exists so a maintainer can run the full phase-A read checklist against a
real network and commit redacted samples to `tests/fixtures/live/` -- this
test exists to keep that redaction logic itself under CI, independent of
ever actually running the script.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "capture-live-samples.py"


def _load_module() -> ModuleType:
    """Load `scripts/capture-live-samples.py` as an importable module.

    Registers the module in `sys.modules` before `exec_module` -- required
    on Python 3.14 for a module defining `@dataclass`-decorated classes to
    be loaded this way (`dataclasses` looks the defining module up via
    `sys.modules[cls.__module__]` while processing type annotations).
    """
    spec = importlib.util.spec_from_file_location("capture_live_samples", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def capture_module() -> ModuleType:
    return _load_module()


class TestRedactPayload:
    """`redact_payload` combines key-based and value-pattern redaction."""

    def test_redacts_sensitive_keys_via_eeroctl_redact_sensitive(self, capture_module):
        payload = {"session_id": "abc123", "password": "hunter2", "name": "Living Room"}

        result = capture_module.redact_payload(payload)

        assert result["session_id"] == "<redacted>"
        assert result["password"] == "<redacted>"
        assert result["name"] == "Living Room"

    def test_redacts_email_addresses_regardless_of_key(self, capture_module):
        payload = {"detail": "sent invite to someone@example.com yesterday"}

        result = capture_module.redact_payload(payload)

        assert "someone@example.com" not in result["detail"]
        assert "<email-redacted>" in result["detail"]

    def test_redacts_mac_addresses_colon_and_bare(self, capture_module):
        payload = {"mac": "aa:bb:cc:dd:ee:ff", "bare": "aabbccddeeff"}

        result = capture_module.redact_payload(payload)

        assert result["mac"] == "<mac-redacted>"
        assert result["bare"] == "<mac-redacted>"

    def test_redacts_ipv4_and_compressed_ipv6(self, capture_module):
        payload = {
            "ip": "192.168.1.1",
            "link_local": "fe80::1ff:fe23:4567:890a",
            "full": "2001:0db8:0000:0042:0000:8a2e:0370:7334",
        }

        result = capture_module.redact_payload(payload)

        assert result["ip"] == "<ipv4-redacted>"
        # The whole compressed address is masked -- not just the tail after
        # "::" (a known failure mode of naive IPv6 regexes, see the
        # script's `_mask_ipv6` docstring).
        assert result["link_local"] == "<ipv6-redacted>"
        assert result["full"] == "<ipv6-redacted>"

    def test_redacts_phone_numbers(self, capture_module):
        payload = {"contact": "+1 555-123-4567"}

        result = capture_module.redact_payload(payload)

        assert result["contact"] == "<phone-redacted>"

    def test_redacts_serial_shaped_tokens(self, capture_module):
        payload = {"serial": "SN1234567890XY"}

        result = capture_module.redact_payload(payload)

        assert result["serial"] == "<serial-redacted>"

    def test_recurses_into_nested_dicts_and_lists(self, capture_module):
        payload = {
            "devices": [
                {"mac": "aa:bb:cc:dd:ee:ff", "nickname": "Laptop"},
                {"mac": "11:22:33:44:55:66", "nickname": "Phone"},
            ]
        }

        result = capture_module.redact_payload(payload)

        assert result["devices"][0]["mac"] == "<mac-redacted>"
        assert result["devices"][0]["nickname"] == "Laptop"
        assert result["devices"][1]["mac"] == "<mac-redacted>"

    def test_leaves_ordinary_values_untouched(self, capture_module):
        payload = {"name": "Kid's iPad", "count": 3, "enabled": True, "note": None}

        result = capture_module.redact_payload(payload)

        assert result == payload

    def test_never_mutates_the_input(self, capture_module):
        payload = {"password": "hunter2", "nested": {"email": "a@b.com"}}
        original = {"password": "hunter2", "nested": {"email": "a@b.com"}}

        capture_module.redact_payload(payload)

        assert payload == original


class TestFirstId:
    """`_first_id` extracts the first list item's "id" from list-command JSON."""

    def test_extracts_id_from_bare_list(self, capture_module):
        assert capture_module._first_id([{"id": "42"}, {"id": "43"}]) == "42"

    def test_extracts_id_from_data_envelope(self, capture_module):
        assert capture_module._first_id({"data": [{"id": "7"}]}) == "7"

    def test_returns_none_for_empty_list(self, capture_module):
        assert capture_module._first_id([]) is None

    def test_returns_none_for_non_list_payload(self, capture_module):
        assert capture_module._first_id("not a list") is None

    def test_returns_none_when_first_item_has_no_id(self, capture_module):
        assert capture_module._first_id([{"name": "no id here"}]) is None


class TestDefaultChannelsWindow:
    """`_default_channels_window` returns a 24h ISO-8601 UTC 'Z' pair."""

    def test_window_is_24_hours_wide_and_iso8601_z_formatted(self, capture_module):
        start, end = capture_module._default_channels_window()

        assert start.endswith("Z")
        assert end.endswith("Z")

        from datetime import datetime, timezone

        start_dt = datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(end, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

        assert (end_dt - start_dt).total_seconds() == 24 * 60 * 60
