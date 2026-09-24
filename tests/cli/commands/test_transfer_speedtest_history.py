"""Unit tests for commit 23's phase-A reads.

Tests cover:
- network transfer [--device]           (get_transfer_stats)
- network speedtest history [--limit --start --end] (get_speed_tests)
- network speedtest show still renders the latest entry from the same
  get_speed_tests/transformers.speedtest code path
"""

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from eero.exceptions import EeroAccessDeniedException, EeroPremiumRequiredException

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli
from eeroctl.transformers.speedtest import extract_latest_speed_test, extract_speed_test_history

# Reuse the mock-client helpers defined in test_events.py rather than
# redefining them per module (standing rule from the batch-1 test audit); a
# shared conftest fixture lands after the group-1 stack is pushed.
from .test_events import _mock_client, _mock_client_raising

TRANSFER_RESPONSE = {"meta": {"code": 200}, "data": {"total_bytes": 12345}}
EMPTY_RESPONSE = {"meta": {"code": 200}, "data": {}}
SPEED_TEST_ENTRY = {
    "down": {"value": 250},
    "up": {"value": 20},
    "latency": {"value": 12},
    "date": "2026-09-20T00:00:00Z",
}
SPEED_TESTS_LIST_RESPONSE = {
    "meta": {"code": 200},
    "data": [SPEED_TEST_ENTRY, {**SPEED_TEST_ENTRY, "date": "2026-09-19T00:00:00Z"}],
}
SPEED_TESTS_SINGLE_RESPONSE = {"meta": {"code": 200}, "data": SPEED_TEST_ENTRY}
EMPTY_LIST_RESPONSE = {"meta": {"code": 200}, "data": []}


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI runner."""
    return CliRunner()


class TestNetworkTransfer:
    """Tests for `network transfer`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "transfer", "--help"])

        assert result.exit_code == 0
        assert "--device" in result.output

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_transfer_stats=TRANSFER_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", output_format, "network", "transfer"])

        assert result.exit_code == 0
        mock_client.get_transfer_stats.assert_awaited_once()

    def test_device_flag_forwarded(self, runner: CliRunner):
        mock_client = _mock_client(get_transfer_stats=TRANSFER_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            runner.invoke(cli, ["network", "transfer", "--device", "dev-123"])

        call_args = mock_client.get_transfer_stats.call_args[0]
        assert call_args[1] == "dev-123"

    def test_no_device_flag_passes_none(self, runner: CliRunner):
        mock_client = _mock_client(get_transfer_stats=TRANSFER_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            runner.invoke(cli, ["network", "transfer"])

        call_args = mock_client.get_transfer_stats.call_args[0]
        assert call_args[1] is None

    def test_json_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(get_transfer_stats=TRANSFER_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "network", "transfer"])

        parsed = json.loads(result.output)
        assert parsed["data"] == TRANSFER_RESPONSE["data"]
        assert parsed["schema"] == "eero.network.transfer/v1"

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_transfer_stats=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "transfer"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_transfer_stats", EeroPremiumRequiredException("Transfer")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "transfer"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_transfer_stats", EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "transfer"])

        assert result.exit_code == ExitCode.FORBIDDEN


class TestSpeedtestHistory:
    """Tests for `network speedtest history`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "speedtest", "history", "--help"])

        assert result.exit_code == 0
        assert "--limit" in result.output
        assert "--start" in result.output
        assert "--end" in result.output

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_speed_tests=SPEED_TESTS_LIST_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", output_format, "network", "speedtest", "history"]
            )

        assert result.exit_code == 0
        mock_client.get_speed_tests.assert_awaited_once()

    def test_limit_start_end_forwarded(self, runner: CliRunner):
        mock_client = _mock_client(get_speed_tests=SPEED_TESTS_LIST_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            runner.invoke(
                cli,
                [
                    "network",
                    "speedtest",
                    "history",
                    "--limit",
                    "5",
                    "--start",
                    "2026-09-01T00:00:00Z",
                    "--end",
                    "2026-09-21T00:00:00Z",
                ],
            )

        call_kwargs = mock_client.get_speed_tests.call_args[1]
        assert call_kwargs["limit"] == 5
        assert call_kwargs["start_time"] == "2026-09-01T00:00:00Z"
        assert call_kwargs["end_time"] == "2026-09-21T00:00:00Z"

    def test_rejects_malformed_start(self, runner: CliRunner):
        result = runner.invoke(
            cli, ["network", "speedtest", "history", "--start", "not-a-timestamp"]
        )

        assert result.exit_code == 2

    def test_json_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(get_speed_tests=SPEED_TESTS_LIST_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "network", "speedtest", "history"])

        parsed = json.loads(result.output)
        assert parsed["data"] == SPEED_TESTS_LIST_RESPONSE["data"]
        assert parsed["schema"] == "eero.network.speedtest.history/v1"

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_speed_tests=EMPTY_LIST_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "speedtest", "history"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_speed_tests", EeroPremiumRequiredException("Speedtest history")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "speedtest", "history"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED


class TestSpeedtestShowSharesHistoryCodePath:
    """`speedtest show` still works, reading through transformers.speedtest."""

    def test_show_renders_first_entry_of_the_history_list(self, runner: CliRunner):
        mock_client = _mock_client(get_speed_tests=SPEED_TESTS_LIST_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "speedtest", "show"])

        assert result.exit_code == 0
        assert "250" in result.output

    def test_show_calls_get_speed_tests_with_limit_1(self, runner: CliRunner):
        mock_client = _mock_client(get_speed_tests=SPEED_TESTS_SINGLE_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            runner.invoke(cli, ["network", "speedtest", "show"])

        mock_client.get_speed_tests.assert_awaited_once()
        call_kwargs = mock_client.get_speed_tests.call_args[1]
        assert call_kwargs == {"limit": 1}


class TestExtractSpeedTestHelpers:
    """Unit tests for the shared speedtest transformer accessors."""

    def test_extract_speed_test_history_tolerates_bare_list(self):
        expected = SPEED_TESTS_LIST_RESPONSE["data"]
        assert extract_speed_test_history(SPEED_TESTS_LIST_RESPONSE) == expected

    def test_extract_speed_test_history_tolerates_single_dict(self):
        assert extract_speed_test_history(SPEED_TESTS_SINGLE_RESPONSE) == [SPEED_TEST_ENTRY]

    def test_extract_speed_test_history_empty(self):
        assert extract_speed_test_history(EMPTY_LIST_RESPONSE) == []

    def test_extract_latest_speed_test_returns_first(self):
        assert extract_latest_speed_test(SPEED_TESTS_LIST_RESPONSE) == SPEED_TEST_ENTRY

    def test_extract_latest_speed_test_returns_none_when_empty(self):
        assert extract_latest_speed_test(EMPTY_LIST_RESPONSE) is None
