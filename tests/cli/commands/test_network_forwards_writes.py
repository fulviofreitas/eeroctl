"""Unit tests for `network forwards create|update|delete`.

Migration plan §4 phase C row 32. Mocks at the SDK boundary
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


class TestForwardsCreate:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["network", "forwards", "create", "--help"])

        assert result.exit_code == 0
        assert "--config-json" in result.output

    def test_invalid_json_exits_usage_error(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["network", "forwards", "create", "--config-json", "not json", "--force"],
            )

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.create_forward.assert_not_called()

    def test_empty_object_exits_usage_error(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "forwards", "create", "--config-json", "{}", "--force"]
            )

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.create_forward.assert_not_called()

    def test_creates_forward(self, runner: CliRunner) -> None:
        mock_client = _client(create_forward={"meta": {"code": 201}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "forwards",
                    "create",
                    "--config-json",
                    '{"name": "SSH", "external_port": 22}',
                    "--force",
                ],
            )

        assert result.exit_code == 0
        mock_client.create_forward.assert_awaited_once()
        call_args = mock_client.create_forward.call_args
        assert call_args[0][0] == {"name": "SSH", "external_port": 22}

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--non-interactive",
                    "network",
                    "forwards",
                    "create",
                    "--config-json",
                    '{"name": "SSH"}',
                ],
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.create_forward.assert_not_called()


class TestForwardsUpdate:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_updates_forward(self, runner: CliRunner) -> None:
        mock_client = _client(update_forward={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "forwards",
                    "update",
                    "fwd1",
                    "--config-json",
                    '{"name": "SSH2"}',
                    "--force",
                ],
            )

        assert result.exit_code == 0
        mock_client.update_forward.assert_awaited_once_with(
            "fwd1", {"name": "SSH2"}, mock_client.update_forward.call_args[0][2]
        )

    def test_requires_config_json(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["network", "forwards", "update", "fwd1", "--force"])

        assert result.exit_code != 0


class TestForwardsDelete:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_deletes_forward(self, runner: CliRunner) -> None:
        mock_client = _client(delete_forward={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "forwards", "delete", "fwd1", "--force"])

        assert result.exit_code == 0
        mock_client.delete_forward.assert_awaited_once()
        call_args = mock_client.delete_forward.call_args
        assert call_args[0][0] == "fwd1"

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--non-interactive", "network", "forwards", "delete", "fwd1"]
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.delete_forward.assert_not_called()
