"""Unit tests for `network power-saving enable|disable` and
`network power-saving schedules create|update|delete`.

Migration plan §4 phase C row 44 (#49). Mocks at the SDK boundary
(`patch("eeroctl.utils.EeroClient", ...)`).
"""

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli

_NETWORK_ENVELOPE = {
    "meta": {"code": 200},
    "data": {
        "url": "/2.2/networks/net1",
        "power_saving": {"enable": False, "power_saving_schedule_enabled": False},
    },
}


def _client(**method_return_values) -> AsyncMock:
    client = AsyncMock()
    for name, value in method_return_values.items():
        setattr(client, name, AsyncMock(return_value=value))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestPowerSavingToggle:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_enable_requires_reboot_phrase(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_network=_NETWORK_ENVELOPE, set_power_saving={"meta": {"code": 200}}
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "power-saving", "enable"], input="REBOOT\n")

        assert result.exit_code == 0
        mock_client.set_power_saving.assert_awaited_once_with(
            None, enable=True, power_saving_schedule_enabled=None
        )

    def test_phrase_mismatch_exits_safety_rail(self, runner: CliRunner) -> None:
        mock_client = _client(get_network=_NETWORK_ENVELOPE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "power-saving", "enable"], input="NOPE\n")

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_power_saving.assert_not_called()

    def test_force_skips_prompt(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_network=_NETWORK_ENVELOPE, set_power_saving={"meta": {"code": 200}}
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "power-saving", "disable", "--force"])

        assert result.exit_code == 0
        mock_client.set_power_saving.assert_awaited_once_with(
            None, enable=False, power_saving_schedule_enabled=None
        )

    def test_skips_write_when_already_configured(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_network=_NETWORK_ENVELOPE,  # enable: False
            set_power_saving=AsyncMock(),
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "power-saving", "disable"], input="REBOOT\n")

        assert result.exit_code == 0
        assert "already configured" in result.output.lower()
        mock_client.set_power_saving.assert_not_called()

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client(get_network=_NETWORK_ENVELOPE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--non-interactive", "network", "power-saving", "enable"])

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_power_saving.assert_not_called()


class TestPowerSavingSchedulesCreate:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_creates_schedule(self, runner: CliRunner) -> None:
        mock_client = _client(create_power_saving_schedule={"meta": {"code": 201}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "power-saving",
                    "schedules",
                    "create",
                    "--name",
                    "Night",
                    "--day",
                    "monday",
                    "--day",
                    "tuesday",
                    "--start-time",
                    "23:00",
                    "--end-time",
                    "06:00",
                    "--force",
                ],
            )

        assert result.exit_code == 0
        mock_client.create_power_saving_schedule.assert_awaited_once_with(
            None,
            name="Night",
            days=["monday", "tuesday"],
            start_time="23:00",
            end_time="06:00",
            enabled=True,
        )

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--non-interactive",
                    "network",
                    "power-saving",
                    "schedules",
                    "create",
                    "--name",
                    "Night",
                    "--day",
                    "monday",
                    "--start-time",
                    "23:00",
                    "--end-time",
                    "06:00",
                ],
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.create_power_saving_schedule.assert_not_called()


class TestPowerSavingSchedulesUpdate:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_no_fields_exits_usage_error_before_prompt(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "power-saving", "schedules", "update", "sched1"]
            )

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.update_power_saving_schedule.assert_not_called()

    def test_updates_one_field(self, runner: CliRunner) -> None:
        mock_client = _client(update_power_saving_schedule={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "power-saving",
                    "schedules",
                    "update",
                    "sched1",
                    "--end-time",
                    "07:00",
                    "--force",
                ],
            )

        assert result.exit_code == 0
        mock_client.update_power_saving_schedule.assert_awaited_once_with(
            "sched1",
            None,
            name=None,
            days=None,
            start_time=None,
            end_time="07:00",
            enabled=None,
        )


class TestPowerSavingSchedulesDelete:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_deletes_schedule(self, runner: CliRunner) -> None:
        mock_client = _client(delete_power_saving_schedule={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "power-saving", "schedules", "delete", "sched1", "--force"]
            )

        assert result.exit_code == 0
        mock_client.delete_power_saving_schedule.assert_awaited_once_with("sched1", None)

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--non-interactive",
                    "network",
                    "power-saving",
                    "schedules",
                    "delete",
                    "sched1",
                ],
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.delete_power_saving_schedule.assert_not_called()
