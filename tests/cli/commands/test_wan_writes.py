"""Unit tests for `network wan multistaticip set` and `network wan secondary set`.

Migration plan §4 phase C row 47 (#52). Mocks at the SDK boundary
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


class TestMultiStaticIpSet:
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
                    "wan",
                    "multistaticip",
                    "set",
                    "--config-json",
                    "not json",
                    "--force",
                ],
            )

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.set_multistaticip.assert_not_called()

    def test_requires_reboot_phrase(self, runner: CliRunner) -> None:
        mock_client = _client(set_multistaticip={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "wan",
                    "multistaticip",
                    "set",
                    "--config-json",
                    '{"enabled": true}',
                ],
                input="REBOOT\n",
            )

        assert result.exit_code == 0
        mock_client.set_multistaticip.assert_awaited_once_with({"enabled": True}, None)

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--non-interactive",
                    "network",
                    "wan",
                    "multistaticip",
                    "set",
                    "--config-json",
                    '{"enabled": true}',
                ],
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_multistaticip.assert_not_called()


class TestSecondaryWanSet:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_requires_reboot_phrase(self, runner: CliRunner) -> None:
        mock_client = _client(set_secondary_wan_config={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "wan",
                    "secondary",
                    "set",
                    "--config-json",
                    '{"enabled": true}',
                ],
                input="REBOOT\n",
            )

        assert result.exit_code == 0
        mock_client.set_secondary_wan_config.assert_awaited_once_with({"enabled": True}, None)

    def test_force_skips_prompt(self, runner: CliRunner) -> None:
        mock_client = _client(set_secondary_wan_config={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "wan",
                    "secondary",
                    "set",
                    "--config-json",
                    '{"enabled": false}',
                    "--force",
                ],
            )

        assert result.exit_code == 0
        mock_client.set_secondary_wan_config.assert_awaited_once_with({"enabled": False}, None)
