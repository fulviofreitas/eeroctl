"""Unit tests for `eero nightlight schedule`'s --on/--off/--disable/
--schedule-json rewire.

Migration plan §4 phase C row 37. Mocks at the SDK boundary
(`patch("eeroctl.utils.EeroClient", ...)`).
"""

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli

_EERO_ENVELOPE = {
    "meta": {"code": 200},
    "data": {"url": "/2.2/networks/net1/eeros/123", "location": "Office"},
}


def _client(**method_return_values) -> AsyncMock:
    client = AsyncMock()
    for name, value in method_return_values.items():
        setattr(client, name, AsyncMock(return_value=value))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestNightlightScheduleOnOff:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_on_off_builds_v7_shape(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_eero=_EERO_ENVELOPE, set_nightlight_schedule={"meta": {"code": 200}}
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--force",
                    "eero",
                    "nightlight",
                    "schedule",
                    "123",
                    "--on",
                    "20:00",
                    "--off",
                    "06:00",
                ],
            )

        assert result.exit_code == 0
        mock_client.set_nightlight_schedule.assert_awaited_once_with(
            "123", {"enabled": True, "on": "20:00", "off": "06:00"}, None
        )

    def test_on_without_off_exits_usage_error(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["--force", "eero", "nightlight", "schedule", "123", "--on", "20:00"],
            )

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.set_nightlight_schedule.assert_not_called()


class TestNightlightScheduleDisable:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_disable_sends_enabled_false(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_eero=_EERO_ENVELOPE, set_nightlight_schedule={"meta": {"code": 200}}
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["--force", "eero", "nightlight", "schedule", "123", "--disable"],
            )

        assert result.exit_code == 0
        mock_client.set_nightlight_schedule.assert_awaited_once_with(
            "123", {"enabled": False}, None
        )


class TestNightlightScheduleJson:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_schedule_json_passed_through_verbatim(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_eero=_EERO_ENVELOPE, set_nightlight_schedule={"meta": {"code": 200}}
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--force",
                    "eero",
                    "nightlight",
                    "schedule",
                    "123",
                    "--schedule-json",
                    '{"custom_field": true}',
                ],
            )

        assert result.exit_code == 0
        mock_client.set_nightlight_schedule.assert_awaited_once_with(
            "123", {"custom_field": True}, None
        )

    def test_invalid_json_exits_usage_error(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--force",
                    "eero",
                    "nightlight",
                    "schedule",
                    "123",
                    "--schedule-json",
                    "nope",
                ],
            )

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.set_nightlight_schedule.assert_not_called()


class TestNightlightScheduleMutualExclusion:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_no_mode_exits_usage_error(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--force", "eero", "nightlight", "schedule", "123"])

        assert result.exit_code == ExitCode.USAGE_ERROR

    def test_on_off_and_disable_together_exits_usage_error(self, runner: CliRunner) -> None:
        result = runner.invoke(
            cli,
            [
                "--force",
                "eero",
                "nightlight",
                "schedule",
                "123",
                "--on",
                "20:00",
                "--off",
                "06:00",
                "--disable",
            ],
        )

        assert result.exit_code == ExitCode.USAGE_ERROR

    def test_schedule_json_and_disable_together_exits_usage_error(self, runner: CliRunner) -> None:
        result = runner.invoke(
            cli,
            [
                "--force",
                "eero",
                "nightlight",
                "schedule",
                "123",
                "--schedule-json",
                "{}",
                "--disable",
            ],
        )

        assert result.exit_code == ExitCode.USAGE_ERROR
