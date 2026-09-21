"""Unit tests for eeroctl.commands.network.usage (closes #46).

Tests cover:
- network usage summary|breakdown|devices|device|eeros|eero|profile|
  unprofiled|report show
"""

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from eero.exceptions import EeroAccessDeniedException, EeroPremiumRequiredException

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli

# Reuse the mock-client helpers defined in test_events.py rather than
# redefining them per module (standing rule from the batch-1 test audit); a
# shared conftest fixture lands after the group-1 stack is pushed.
from .test_events import _mock_client, _mock_client_raising

USAGE_RESPONSE = {"meta": {"code": 200}, "data": {"total_bytes": 1000}}
EMPTY_RESPONSE = {"meta": {"code": 200}, "data": {}}

WINDOW_ARGS = ["--start", "2026-09-01T00:00:00Z", "--end", "2026-09-21T00:00:00Z"]
WINDOW_ARGS_WITH_CADENCE = [*WINDOW_ARGS, "--cadence", "daily"]


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI runner."""
    return CliRunner()


class TestUsageGroup:
    """Tests for the `network usage` command group."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "usage", "--help"])

        assert result.exit_code == 0
        for name in (
            "summary",
            "breakdown",
            "devices",
            "device",
            "eeros",
            "eero",
            "profile",
            "unprofiled",
            "report",
        ):
            assert name in result.output


class TestUsageSummary:
    """Tests for `network usage summary` (cadence required)."""

    def test_requires_cadence(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "usage", "summary", *WINDOW_ARGS])

        assert result.exit_code == 2

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_data_usage=USAGE_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--output",
                    output_format,
                    "network",
                    "usage",
                    "summary",
                    *WINDOW_ARGS_WITH_CADENCE,
                ],
            )

        assert result.exit_code == 0
        mock_client.get_data_usage.assert_awaited_once()

    def test_timezone_forwarded(self, runner: CliRunner):
        mock_client = _mock_client(get_data_usage=USAGE_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            runner.invoke(
                cli,
                [
                    "network",
                    "usage",
                    "summary",
                    *WINDOW_ARGS_WITH_CADENCE,
                    "--timezone",
                    "Europe/Lisbon",
                ],
            )

        call_kwargs = mock_client.get_data_usage.call_args[1]
        assert call_kwargs["timezone"] == "Europe/Lisbon"

    def test_json_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(get_data_usage=USAGE_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["--output", "json", "network", "usage", "summary", *WINDOW_ARGS_WITH_CADENCE],
            )

        parsed = json.loads(result.output)
        assert parsed["data"] == USAGE_RESPONSE["data"]
        assert parsed["schema"] == "eero.network.usage.summary/v1"

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising("get_data_usage", EeroPremiumRequiredException("Usage"))

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "usage", "summary", *WINDOW_ARGS_WITH_CADENCE])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        # commit 6 maps EeroAccessDeniedException directly; until then it falls
        # through the generic EeroAPIException branch's status_code == 403 check.
        mock_client = _mock_client_raising(
            "get_data_usage", EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "usage", "summary", *WINDOW_ARGS_WITH_CADENCE])

        assert result.exit_code == ExitCode.FORBIDDEN


class TestUsageBreakdown:
    """Tests for `network usage breakdown` (cadence optional)."""

    def test_cadence_optional(self, runner: CliRunner):
        mock_client = _mock_client(get_data_usage_breakdown=USAGE_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "usage", "breakdown", *WINDOW_ARGS])

        assert result.exit_code == 0

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_data_usage_breakdown=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "usage", "breakdown", *WINDOW_ARGS])

        assert result.exit_code == 0

    def test_json_schema(self, runner: CliRunner):
        mock_client = _mock_client(get_data_usage_breakdown=USAGE_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", "json", "network", "usage", "breakdown", *WINDOW_ARGS]
            )

        parsed = json.loads(result.output)
        assert parsed["schema"] == "eero.network.usage.breakdown/v1"


class TestUsageDevices:
    """Tests for `network usage devices [--profile]` (cadence optional)."""

    def test_profile_flag_forwarded(self, runner: CliRunner):
        mock_client = _mock_client(get_devices_data_usage=USAGE_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            runner.invoke(cli, ["network", "usage", "devices", "--profile", "prof-1", *WINDOW_ARGS])

        call_kwargs = mock_client.get_devices_data_usage.call_args[1]
        assert call_kwargs["profile_id"] == "prof-1"

    def test_happy_path(self, runner: CliRunner):
        mock_client = _mock_client(get_devices_data_usage=USAGE_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "usage", "devices", *WINDOW_ARGS])

        assert result.exit_code == 0


class TestUsageDevice:
    """Tests for `network usage device <mac>` (cadence required)."""

    def test_requires_cadence(self, runner: CliRunner):
        result = runner.invoke(
            cli, ["network", "usage", "device", "AA:BB:CC:DD:EE:FF", *WINDOW_ARGS]
        )

        assert result.exit_code == 2

    def test_happy_path(self, runner: CliRunner):
        mock_client = _mock_client(get_device_data_usage=USAGE_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "usage",
                    "device",
                    "AA:BB:CC:DD:EE:FF",
                    *WINDOW_ARGS_WITH_CADENCE,
                ],
            )

        assert result.exit_code == 0
        call_args = mock_client.get_device_data_usage.call_args[0]
        assert call_args[0] == "AA:BB:CC:DD:EE:FF"


class TestUsageEeros:
    """Tests for `network usage eeros` (cadence required)."""

    def test_requires_cadence(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "usage", "eeros", *WINDOW_ARGS])

        assert result.exit_code == 2

    def test_happy_path(self, runner: CliRunner):
        mock_client = _mock_client(get_eeros_data_usage_summary=USAGE_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "usage", "eeros", *WINDOW_ARGS_WITH_CADENCE])

        assert result.exit_code == 0


class TestUsageEero:
    """Tests for `network usage eero <id>` (cadence required)."""

    def test_happy_path(self, runner: CliRunner):
        mock_client = _mock_client(get_eero_data_usage=USAGE_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "usage", "eero", "eero-1", *WINDOW_ARGS_WITH_CADENCE]
            )

        assert result.exit_code == 0
        call_args = mock_client.get_eero_data_usage.call_args[0]
        assert call_args[0] == "eero-1"


class TestUsageProfile:
    """Tests for `network usage profile <id>` (cadence required)."""

    def test_happy_path(self, runner: CliRunner):
        mock_client = _mock_client(get_profile_data_usage=USAGE_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "usage", "profile", "prof-1", *WINDOW_ARGS_WITH_CADENCE]
            )

        assert result.exit_code == 0
        call_args = mock_client.get_profile_data_usage.call_args[0]
        assert call_args[0] == "prof-1"


class TestUsageUnprofiled:
    """Tests for `network usage unprofiled [--summary]` (cadence required by the CLI)."""

    def test_devices_variant(self, runner: CliRunner):
        mock_client = _mock_client(get_unprofiled_devices_data_usage=USAGE_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "usage", "unprofiled", *WINDOW_ARGS_WITH_CADENCE]
            )

        assert result.exit_code == 0
        mock_client.get_unprofiled_devices_data_usage.assert_awaited_once()

    def test_summary_flag_calls_summary_endpoint(self, runner: CliRunner):
        mock_client = _mock_client(get_unprofiled_data_usage_summary=USAGE_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["network", "usage", "unprofiled", "--summary", *WINDOW_ARGS_WITH_CADENCE],
            )

        assert result.exit_code == 0
        mock_client.get_unprofiled_data_usage_summary.assert_awaited_once()

    def test_summary_flag_json_schema(self, runner: CliRunner):
        mock_client = _mock_client(get_unprofiled_data_usage_summary=USAGE_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--output",
                    "json",
                    "network",
                    "usage",
                    "unprofiled",
                    "--summary",
                    *WINDOW_ARGS_WITH_CADENCE,
                ],
            )

        parsed = json.loads(result.output)
        assert parsed["schema"] == "eero.network.usage.unprofiled.summary/v1"


class TestUsageReportShow:
    """Tests for `network usage report show` (no time window)."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "usage", "report", "show", "--help"])

        assert result.exit_code == 0

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_data_usage_report_settings=USAGE_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", output_format, "network", "usage", "report", "show"]
            )

        assert result.exit_code == 0
        mock_client.get_data_usage_report_settings.assert_awaited_once()

    def test_json_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(get_data_usage_report_settings=USAGE_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "network", "usage", "report", "show"])

        parsed = json.loads(result.output)
        assert parsed["data"] == USAGE_RESPONSE["data"]
        assert parsed["schema"] == "eero.network.usage.report.show/v1"

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_data_usage_report_settings=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "usage", "report", "show"])

        assert result.exit_code == 0
