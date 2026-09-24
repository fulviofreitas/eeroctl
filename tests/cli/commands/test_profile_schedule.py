"""Unit tests for `profile schedule set`'s read-first skip and `schedule delete`.

Migration plan §4 phase C row 29. Mocks at the SDK boundary
(`patch("eeroctl.utils.EeroClient", ...)`), not `run_with_client`.
"""

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli

_PROFILES_RESPONSE = {
    "meta": {"code": 200},
    "data": [{"url": "/2.2/networks/net1/profiles/p1", "name": "Kids"}],
}


def _client(**method_return_values) -> AsyncMock:
    client = AsyncMock()
    for name, value in method_return_values.items():
        setattr(client, name, AsyncMock(return_value=value))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestScheduleSetReadFirst:
    """`schedule set` now reads the current Bedtime schedule before writing."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_skips_write_when_identical_bedtime_exists(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_profiles=_PROFILES_RESPONSE,
            get_schedules={
                "meta": {"code": 200},
                "data": [
                    {
                        "url": "/2.2/networks/net1/profiles/p1/schedules/s1",
                        "name": "Bedtime",
                        "start": "21:00",
                        "end": "07:00",
                        "days": ["monday", "tuesday"],
                    }
                ],
            },
            enable_bedtime=None,
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "profile",
                    "schedule",
                    "set",
                    "Kids",
                    "--start",
                    "21:00",
                    "--end",
                    "07:00",
                    "--days",
                    "tuesday,monday",
                ],
                input="y\n",
            )

        assert result.exit_code == 0
        assert "already configured" in result.output.lower()
        mock_client.enable_bedtime.assert_not_called()

    def test_writes_when_bedtime_differs(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_profiles=_PROFILES_RESPONSE,
            get_schedules={"meta": {"code": 200}, "data": []},
            enable_bedtime={"meta": {"code": 200}, "data": {}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "profile",
                    "schedule",
                    "set",
                    "Kids",
                    "--start",
                    "21:00",
                    "--end",
                    "07:00",
                    "--force",
                ],
            )

        assert result.exit_code == 0
        mock_client.enable_bedtime.assert_awaited_once()


class TestScheduleDelete:
    """Tests for `profile schedule delete`."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["profile", "schedule", "delete", "--help"])

        assert result.exit_code == 0
        assert "SCHEDULE_ID" in result.output

    def test_profile_not_found(self, runner: CliRunner) -> None:
        mock_client = _client(get_profiles={"meta": {"code": 200}, "data": []})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["profile", "schedule", "delete", "NoSuchProfile", "s1", "--force"]
            )

        assert result.exit_code == ExitCode.NOT_FOUND

    def test_schedule_not_found(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_profiles=_PROFILES_RESPONSE,
            get_schedules={"meta": {"code": 200}, "data": []},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["profile", "schedule", "delete", "Kids", "s1", "--force"])

        assert result.exit_code == ExitCode.NOT_FOUND
        mock_client.delete_schedule.assert_not_called()

    def test_deletes_by_id_field(self, runner: CliRunner) -> None:
        entry = {
            "id": "s1",
            "url": "/2.2/networks/net1/profiles/p1/schedules/s1",
            "name": "Bedtime",
        }
        mock_client = _client(
            get_profiles=_PROFILES_RESPONSE,
            get_schedules={"meta": {"code": 200}, "data": [entry]},
            delete_schedule={"meta": {"code": 200}, "data": {}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["profile", "schedule", "delete", "Kids", "s1", "--force"])

        assert result.exit_code == 0
        mock_client.delete_schedule.assert_awaited_once_with(entry)

    def test_deletes_by_url_tail(self, runner: CliRunner) -> None:
        entry = {
            "url": "/2.2/networks/net1/profiles/p1/schedules/s2",
            "name": "Bedtime",
        }
        mock_client = _client(
            get_profiles=_PROFILES_RESPONSE,
            get_schedules={"meta": {"code": 200}, "data": [entry]},
            delete_schedule={"meta": {"code": 200}, "data": {}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["profile", "schedule", "delete", "Kids", "s2", "--force"])

        assert result.exit_code == 0
        mock_client.delete_schedule.assert_awaited_once_with(entry)

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        entry = {"id": "s1", "name": "Bedtime"}
        mock_client = _client(
            get_profiles=_PROFILES_RESPONSE,
            get_schedules={"meta": {"code": 200}, "data": [entry]},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--non-interactive", "profile", "schedule", "delete", "Kids", "s1"]
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.delete_schedule.assert_not_called()
