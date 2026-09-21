"""Unit tests for eeroctl.commands.network.wan.

Tests cover:
- network wan multistaticip show (get_multistaticip)
- Q7 semantics: error.network.multistaticip_not_found -> exit 0, "not
  configured" line, data: null in structured output; any other
  EeroNotFoundException (wrong network id) -> exit 5
"""

import json
from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner
from eero.exceptions import (
    EeroAccessDeniedException,
    EeroNotFoundException,
    EeroPremiumRequiredException,
)

from eeroctl.commands.network.wan import MULTISTATICIP_NOT_FOUND_ERROR_CODE
from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli

# Reuse the mock-client helpers defined in test_events.py rather than
# redefining them per module (standing rule from the batch-1 test audit); a
# shared conftest fixture lands after the group-1 stack is pushed.
from .test_events import _mock_client, _mock_client_raising

MULTISTATICIP_RESPONSE = {
    "meta": {"code": 200},
    "data": {"ips": ["203.0.113.10", "203.0.113.11"]},
}
EMPTY_RESPONSE = {"meta": {"code": 200}, "data": {}}


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI runner."""
    return CliRunner()


class TestWanGroup:
    """Tests for the `network wan` command group."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "wan", "--help"])

        assert result.exit_code == 0
        assert "multistaticip" in result.output


class TestMultistaticipShow:
    """Tests for `network wan multistaticip show`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "wan", "multistaticip", "show", "--help"])

        assert result.exit_code == 0
        assert "--output" in result.output
        assert "--network-id" in result.output

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_multistaticip=MULTISTATICIP_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", output_format, "network", "wan", "multistaticip", "show"]
            )

        assert result.exit_code == 0
        mock_client.get_multistaticip.assert_awaited_once()

    def test_json_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(get_multistaticip=MULTISTATICIP_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", "json", "network", "wan", "multistaticip", "show"]
            )

        parsed = json.loads(result.output)
        assert parsed["data"] == MULTISTATICIP_RESPONSE["data"]
        assert parsed["schema"] == "eero.network.wan.multistaticip.show/v1"

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_multistaticip=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "wan", "multistaticip", "show"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_multistaticip", EeroPremiumRequiredException("MSIP")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "wan", "multistaticip", "show"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        # commit 6 maps EeroAccessDeniedException directly; until then it falls
        # through the generic EeroAPIException branch's status_code == 403 check.
        mock_client = _mock_client_raising(
            "get_multistaticip", EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "wan", "multistaticip", "show"])

        assert result.exit_code == ExitCode.FORBIDDEN


class TestMultistaticipQ7Semantics:
    """Tests for the Q7 "absent feature" vs "wrong id" distinction."""

    def test_feature_absent_error_code_exits_0_not_configured(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_multistaticip",
            EeroNotFoundException.from_response(
                "multistaticip not found",
                error_code=MULTISTATICIP_NOT_FOUND_ERROR_CODE,
            ),
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "wan", "multistaticip", "show"])

        assert result.exit_code == 0
        assert "not configured" in result.output.lower()

    def test_feature_absent_json_output_is_data_null(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_multistaticip",
            EeroNotFoundException.from_response(
                "multistaticip not found",
                error_code=MULTISTATICIP_NOT_FOUND_ERROR_CODE,
            ),
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", "json", "network", "wan", "multistaticip", "show"]
            )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["data"] is None
        assert parsed["schema"] == "eero.network.wan.multistaticip.show/v1"

    def test_feature_absent_yaml_output_is_data_null(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_multistaticip",
            EeroNotFoundException.from_response(
                "multistaticip not found",
                error_code=MULTISTATICIP_NOT_FOUND_ERROR_CODE,
            ),
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", "yaml", "network", "wan", "multistaticip", "show"]
            )

        assert result.exit_code == 0
        parsed = yaml.safe_load(result.output)
        assert parsed["data"] is None

    def test_different_not_found_error_code_still_exits_5(self, runner: CliRunner):
        """A wrong network id (a different/absent error_code) is NOT treated
        as "not configured" -- it stays a plain 404, exit 5.
        """
        mock_client = _mock_client_raising(
            "get_multistaticip",
            EeroNotFoundException("network", "bad-network-id"),
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "wan", "multistaticip", "show"])

        assert result.exit_code == ExitCode.NOT_FOUND

    def test_not_found_with_no_error_code_still_exits_5(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_multistaticip",
            EeroNotFoundException.from_response("some other 404"),
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "wan", "multistaticip", "show"])

        assert result.exit_code == ExitCode.NOT_FOUND
