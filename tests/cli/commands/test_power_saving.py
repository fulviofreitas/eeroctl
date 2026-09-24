"""Unit tests for eeroctl.commands.network.power_saving.

Tests cover:
- network power-saving schedules list (get_power_saving_schedules, verified)
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

SCHEDULES_RESPONSE = {
    "meta": {"code": 200},
    "data": {"schedules": [{"id": "1", "start_time": "22:00", "end_time": "06:00"}]},
}
EMPTY_RESPONSE = {"meta": {"code": 200}, "data": {}}


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI runner."""
    return CliRunner()


class TestPowerSavingGroup:
    """Tests for the `network power-saving` command group."""

    def test_power_saving_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "power-saving", "--help"])

        assert result.exit_code == 0
        assert "schedules" in result.output

    def test_schedules_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "power-saving", "schedules", "--help"])

        assert result.exit_code == 0
        assert "list" in result.output


class TestPowerSavingSchedulesList:
    """Tests for `network power-saving schedules list`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "power-saving", "schedules", "list", "--help"])

        assert result.exit_code == 0
        assert "--output" in result.output
        assert "--network-id" in result.output

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_power_saving_schedules=SCHEDULES_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["--output", output_format, "network", "power-saving", "schedules", "list"],
            )

        assert result.exit_code == 0
        mock_client.get_power_saving_schedules.assert_awaited_once()

    def test_json_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(get_power_saving_schedules=SCHEDULES_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", "json", "network", "power-saving", "schedules", "list"]
            )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["data"] == SCHEDULES_RESPONSE["data"]
        assert parsed["schema"] == "eero.network.power_saving.schedules.list/v1"

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_power_saving_schedules=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "power-saving", "schedules", "list"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_power_saving_schedules", EeroPremiumRequiredException("Power saving")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "power-saving", "schedules", "list"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        # commit 6 maps EeroAccessDeniedException directly; until then it falls
        # through the generic EeroAPIException branch's status_code == 403 check.
        mock_client = _mock_client_raising(
            "get_power_saving_schedules", EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "power-saving", "schedules", "list"])

        assert result.exit_code == ExitCode.FORBIDDEN
