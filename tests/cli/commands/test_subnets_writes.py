"""Unit tests for `network subnets set|delete` and `network subnets filters set`.

Migration plan §4 phase C row 46 (#51). Mocks at the SDK boundary
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


class TestSubnetsSet:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_invalid_json_exits_usage_error(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "subnets", "set", "--config-json", "not json", "--force"]
            )

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.set_subnets_config.assert_not_called()

    def test_requires_reboot_phrase(self, runner: CliRunner) -> None:
        mock_client = _client(set_subnets_config={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["network", "subnets", "set", "--config-json", '{"subnet_type": "guest"}'],
                input="REBOOT\n",
            )

        assert result.exit_code == 0
        mock_client.set_subnets_config.assert_awaited_once_with({"subnet_type": "guest"}, None)

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--non-interactive",
                    "network",
                    "subnets",
                    "set",
                    "--config-json",
                    '{"subnet_type": "guest"}',
                ],
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_subnets_config.assert_not_called()


class TestSubnetsDelete:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_requires_reboot_phrase(self, runner: CliRunner) -> None:
        mock_client = _client(delete_subnet={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "subnets", "delete", "guest"], input="REBOOT\n")

        assert result.exit_code == 0
        mock_client.delete_subnet.assert_awaited_once_with("guest", None)

    def test_force_skips_prompt(self, runner: CliRunner) -> None:
        mock_client = _client(delete_subnet={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "subnets", "delete", "guest", "--force"])

        assert result.exit_code == 0
        mock_client.delete_subnet.assert_awaited_once_with("guest", None)


class TestSubnetFiltersSet:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_invalid_json_exits_usage_error(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "subnets",
                    "filters",
                    "set",
                    "sub1",
                    "--config-json",
                    "not json",
                    "--force",
                ],
            )

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.set_subnet_content_filters.assert_not_called()

    def test_sets_filters(self, runner: CliRunner) -> None:
        mock_client = _client(set_subnet_content_filters={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "subnets",
                    "filters",
                    "set",
                    "sub1",
                    "--config-json",
                    '{"content_filters": {}, "subnets": ["sub1"]}',
                    "--force",
                ],
            )

        assert result.exit_code == 0
        mock_client.set_subnet_content_filters.assert_awaited_once_with(
            {"content_filters": {}, "subnets": ["sub1"]}, None
        )

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--non-interactive",
                    "network",
                    "subnets",
                    "filters",
                    "set",
                    "sub1",
                    "--config-json",
                    '{"content_filters": {}}',
                ],
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_subnet_content_filters.assert_not_called()
