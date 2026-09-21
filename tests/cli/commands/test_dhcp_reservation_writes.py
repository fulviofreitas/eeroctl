"""Unit tests for `network dhcp reservation create|update|delete`.

Migration plan §4 phase C row 33. Mocks at the SDK boundary
(`patch("eeroctl.utils.EeroClient", ...)`).
"""

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli


def _client(**method_return_values) -> AsyncMock:
    client = AsyncMock()
    for name, value in method_return_values.items():
        setattr(client, name, AsyncMock(return_value=value))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestReservationCreate:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["network", "dhcp", "reservation", "create", "--help"])

        assert result.exit_code == 0
        assert "--config-json" in result.output

    def test_invalid_json_exits_usage_error(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "dhcp",
                    "reservation",
                    "create",
                    "--config-json",
                    "nope",
                    "--force",
                ],
            )

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.create_reservation.assert_not_called()

    def test_creates_reservation(self, runner: CliRunner) -> None:
        mock_client = _client(create_reservation={"meta": {"code": 201}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "dhcp",
                    "reservation",
                    "create",
                    "--config-json",
                    '{"mac": "AA:BB:CC:DD:EE:FF", "ip": "10.0.0.5"}',
                    "--force",
                ],
            )

        assert result.exit_code == 0
        mock_client.create_reservation.assert_awaited_once()
        call_args = mock_client.create_reservation.call_args
        assert call_args[0][0] == {"mac": "AA:BB:CC:DD:EE:FF", "ip": "10.0.0.5"}

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--non-interactive",
                    "network",
                    "dhcp",
                    "reservation",
                    "create",
                    "--config-json",
                    '{"mac": "x"}',
                ],
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.create_reservation.assert_not_called()


class TestReservationUpdate:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_updates_reservation(self, runner: CliRunner) -> None:
        mock_client = _client(update_reservation={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "dhcp",
                    "reservation",
                    "update",
                    "r1",
                    "--config-json",
                    '{"ip": "10.0.0.9"}',
                    "--force",
                ],
            )

        assert result.exit_code == 0
        mock_client.update_reservation.assert_awaited_once()
        call_args = mock_client.update_reservation.call_args
        assert call_args[0][0] == "r1"
        assert call_args[0][1] == {"ip": "10.0.0.9"}


class TestReservationDelete:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_deletes_reservation(self, runner: CliRunner) -> None:
        mock_client = _client(delete_reservation={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "dhcp", "reservation", "delete", "r1", "--force"]
            )

        assert result.exit_code == 0
        mock_client.delete_reservation.assert_awaited_once()
        call_args = mock_client.delete_reservation.call_args
        assert call_args[0][0] == "r1"

    def test_delete_forwards_flag_passed_through(self, runner: CliRunner) -> None:
        mock_client = _client(delete_reservation={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "dhcp",
                    "reservation",
                    "delete",
                    "r1",
                    "--delete-forwards",
                    "--force",
                ],
            )

        assert result.exit_code == 0
        call_args = mock_client.delete_reservation.call_args
        assert call_args.kwargs["delete_forwards"] is True

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--non-interactive", "network", "dhcp", "reservation", "delete", "r1"]
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.delete_reservation.assert_not_called()
