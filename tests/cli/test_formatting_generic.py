"""Unit tests for eeroctl.formatting.generic.

Tests cover:
- redact_sensitive(): recursive key-based redaction for undocumented payloads
- render_generic(): table/list/text redact, json/yaml pass the raw data through
"""

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from eeroctl.const import GENERIC_RENDER_SENSITIVE_KEY_PATTERNS
from eeroctl.formatting.generic import _REDACTED, redact_sensitive
from eeroctl.main import cli

from .commands.test_events import _mock_client

SENSITIVE_RESPONSE = {
    "meta": {"code": 200},
    "data": {
        "is_premium_customer": True,
        "user_token": "TOKENVALUE123",
        "billing": {
            "email": "victim@example.com",
            "phone": "+1-555-0100",
        },
        "sessions": [
            {"cookie": "abc123", "authorization": "Bearer xyz"},
        ],
        "api_key": "sk_live_abcdef",
        "apikey": "sk_live_ghijkl",
        "secret": "shh",
        "password": "hunter2",
        "sms_code": "000000",
        "serial": "EERO123456",
        "mac": "AA:BB:CC:DD:EE:FF",
        "url": "https://example.com/networks/1",
    },
}


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI runner."""
    return CliRunner()


class TestRedactSensitive:
    """Unit tests for the recursive redaction helper."""

    @pytest.mark.parametrize("pattern", GENERIC_RENDER_SENSITIVE_KEY_PATTERNS)
    def test_redacts_every_configured_pattern(self, pattern: str):
        data = {f"some_{pattern}_field": "secret-value"}
        result = redact_sensitive(data)
        assert result[f"some_{pattern}_field"] == _REDACTED

    def test_case_insensitive(self):
        assert redact_sensitive({"User_Token": "abc"})["User_Token"] == _REDACTED
        assert redact_sensitive({"EMAIL": "a@b.com"})["EMAIL"] == _REDACTED

    def test_redacts_at_any_nesting_level(self):
        data = {"outer": {"inner": {"password": "hunter2"}}}
        result = redact_sensitive(data)
        assert result["outer"]["inner"]["password"] == _REDACTED

    def test_redacts_within_lists_of_dicts(self):
        data = {"sessions": [{"cookie": "abc"}, {"cookie": "def"}]}
        result = redact_sensitive(data)
        assert all(item["cookie"] == _REDACTED for item in result["sessions"])

    def test_redacts_nested_structure_under_sensitive_key_wholesale(self):
        """A dict/list value under a sensitive key is hidden entirely, not
        recursed into -- so no partial leakage of its own children.
        """
        data = {"secret": {"still": "hidden"}}
        result = redact_sensitive(data)
        assert result["secret"] == _REDACTED

    def test_serial_mac_url_are_not_redacted(self):
        data = {"serial": "EERO123456", "mac": "AA:BB:CC", "url": "https://example.com/x"}
        result = redact_sensitive(data)
        assert result == data

    def test_non_sensitive_values_pass_through(self):
        data = {"id": "1", "name": "Home", "count": 3}
        assert redact_sensitive(data) == data

    def test_tolerates_non_dict_top_level(self):
        assert redact_sensitive([{"password": "x"}]) == [{"password": _REDACTED}]
        assert redact_sensitive("plain string") == "plain string"
        assert redact_sensitive(None) is None

    def test_does_not_mutate_input(self):
        data = {"password": "hunter2"}
        redact_sensitive(data)
        assert data["password"] == "hunter2"


class TestRenderGenericRedaction:
    """End-to-end tests: table/list/text redact, json/yaml pass raw data through."""

    @pytest.mark.parametrize("output_format", ["table", "list", "text"])
    def test_sensitive_values_redacted(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_premium_customer=SENSITIVE_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", output_format, "account", "premium"])

        assert result.exit_code == 0
        assert "TOKENVALUE123" not in result.output
        assert "victim@example.com" not in result.output
        assert "+1-555-0100" not in result.output
        assert "hunter2" not in result.output
        assert "sk_live_abcdef" not in result.output
        assert "sk_live_ghijkl" not in result.output

    @pytest.mark.parametrize("output_format", ["json", "yaml"])
    def test_json_yaml_keep_raw_passthrough(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_premium_customer=SENSITIVE_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", output_format, "account", "premium"])

        assert result.exit_code == 0
        assert "TOKENVALUE123" in result.output
        assert "victim@example.com" in result.output

    def test_json_output_is_still_valid_json_and_unredacted(self, runner: CliRunner):
        mock_client = _mock_client(get_premium_customer=SENSITIVE_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "account", "premium"])

        parsed = json.loads(result.output)
        assert parsed["data"]["user_token"] == "TOKENVALUE123"

    def test_non_sensitive_values_still_shown_in_table(self, runner: CliRunner):
        mock_client = _mock_client(get_premium_customer=SENSITIVE_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["account", "premium"])

        assert result.exit_code == 0
        assert "EERO123456" in result.output or "is_premium_customer" in result.output.lower()
