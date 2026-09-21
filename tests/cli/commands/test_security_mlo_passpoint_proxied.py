"""Unit tests for `network security mlo/passpoint/proxied-nodes`.

Migration plan §4 phase C row 34. Mocks at the SDK boundary
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
        "mlo_mode": "disabled",
        "passpoint": False,
        "proxied_nodes": False,
    },
}


def _client(**method_return_values) -> AsyncMock:
    client = AsyncMock()
    for name, value in method_return_values.items():
        setattr(client, name, AsyncMock(return_value=value))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestMloSet:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["network", "security", "mlo", "set", "--help"])

        assert result.exit_code == 0

    def test_invalid_mode_rejected(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["network", "security", "mlo", "set", "bogus"])

        assert result.exit_code != 0

    def test_requires_reboot_phrase(self, runner: CliRunner) -> None:
        mock_client = _client(get_network=_NETWORK_ENVELOPE, set_mlo_mode={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "security", "mlo", "set", "single"], input="REBOOT\n"
            )

        assert result.exit_code == 0
        mock_client.set_mlo_mode.assert_awaited_once_with("single", None)

    def test_skips_write_when_already_set(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_network=_NETWORK_ENVELOPE,  # mlo_mode: disabled
            set_mlo_mode=AsyncMock(),
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "security", "mlo", "set", "disabled"], input="REBOOT\n"
            )

        assert result.exit_code == 0
        assert "already configured" in result.output.lower()
        mock_client.set_mlo_mode.assert_not_called()

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client(get_network=_NETWORK_ENVELOPE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--non-interactive", "network", "security", "mlo", "set", "single"]
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_mlo_mode.assert_not_called()


class TestPasspointToggle:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_enable_calls_set_passpoint_enabled(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_network=_NETWORK_ENVELOPE,  # passpoint: False
            set_passpoint_enabled={"meta": {"code": 200}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "security", "passpoint", "enable", "--force"])

        assert result.exit_code == 0
        mock_client.set_passpoint_enabled.assert_awaited_once_with(True, None)

    def test_skips_write_when_unchanged(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_network=_NETWORK_ENVELOPE,  # passpoint: False
            set_passpoint_enabled=AsyncMock(),
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "security", "passpoint", "disable"], input="y\n"
            )

        assert result.exit_code == 0
        assert "already configured" in result.output.lower()
        mock_client.set_passpoint_enabled.assert_not_called()


class TestProxiedNodesToggle:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_enable_calls_set_proxied_nodes(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_network=_NETWORK_ENVELOPE,  # proxied_nodes: False
            set_proxied_nodes={"meta": {"code": 200}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "security", "proxied-nodes", "enable", "--force"]
            )

        assert result.exit_code == 0
        mock_client.set_proxied_nodes.assert_awaited_once_with(True, None)

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client(get_network=_NETWORK_ENVELOPE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--non-interactive", "network", "security", "proxied-nodes", "enable"]
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_proxied_nodes.assert_not_called()
