"""Unit tests for `network usage report set`.

Migration plan §4 phase C row 43 (#48). Mocks at the SDK boundary
(`patch("eeroctl.utils.EeroClient", ...)`).
"""

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli

_REPORT_SETTINGS_ENVELOPE = {
    "meta": {"code": 200},
    "data": {"cadence": "daily", "notification_day": "monday"},
}


def _client(**method_return_values) -> AsyncMock:
    client = AsyncMock()
    for name, value in method_return_values.items():
        setattr(client, name, AsyncMock(return_value=value))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestUsageReportSet:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["network", "usage", "report", "set", "--help"])

        assert result.exit_code == 0
        assert "--cadence" in result.output
        assert "--notification-day" in result.output

    def test_invalid_cadence_rejected(self, runner: CliRunner) -> None:
        result = runner.invoke(
            cli,
            [
                "network",
                "usage",
                "report",
                "set",
                "--cadence",
                "weekly",
                "--notification-day",
                "monday",
            ],
        )

        assert result.exit_code != 0

    def test_sets_report_settings(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_data_usage_report_settings=_REPORT_SETTINGS_ENVELOPE,
            set_data_usage_report_settings={"meta": {"code": 200}, "data": {}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "usage",
                    "report",
                    "set",
                    "--cadence",
                    "hourly",
                    "--notification-day",
                    "tuesday",
                    "--force",
                ],
            )

        assert result.exit_code == 0
        mock_client.set_data_usage_report_settings.assert_awaited_once_with(
            cadence="hourly", notification_day="tuesday", network_id=None
        )

    def test_skips_write_when_already_configured(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_data_usage_report_settings=_REPORT_SETTINGS_ENVELOPE,
            set_data_usage_report_settings=AsyncMock(),
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "usage",
                    "report",
                    "set",
                    "--cadence",
                    "daily",
                    "--notification-day",
                    "monday",
                ],
            )

        assert result.exit_code == 0
        assert "already configured" in result.output.lower()
        mock_client.set_data_usage_report_settings.assert_not_called()

    def test_non_interactive_low_risk_writes_without_force(self, runner: CliRunner) -> None:
        """LOW risk (per WRITE_SPECS) proceeds even under --non-interactive
        without --force -- `require_confirmation` returns True for LOW
        before it ever checks `non_interactive` (safety.py:161-163)."""
        mock_client = _client(
            get_data_usage_report_settings=_REPORT_SETTINGS_ENVELOPE,
            set_data_usage_report_settings={"meta": {"code": 200}, "data": {}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--non-interactive",
                    "network",
                    "usage",
                    "report",
                    "set",
                    "--cadence",
                    "hourly",
                    "--notification-day",
                    "monday",
                ],
            )

        assert result.exit_code == 0
        mock_client.set_data_usage_report_settings.assert_awaited_once()

    def test_missing_required_option_exits_usage_error(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["network", "usage", "report", "set", "--cadence", "daily"])

        assert result.exit_code == ExitCode.USAGE_ERROR
