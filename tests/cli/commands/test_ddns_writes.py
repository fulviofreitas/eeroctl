"""Unit tests for `network ddns enable|disable`.

Migration plan §4 phase C row 42. Mocks at the SDK boundary
(`patch("eeroctl.utils.EeroClient", ...)`).
"""

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli

_NETWORK_ENVELOPE_DDNS_OFF = {
    "meta": {"code": 200},
    "data": {"url": "/2.2/networks/net1", "ddns": False},
}


def _client(**method_return_values) -> AsyncMock:
    client = AsyncMock()
    for name, value in method_return_values.items():
        setattr(client, name, AsyncMock(return_value=value))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestDdnsEnable:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_enables_ddns(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_network=_NETWORK_ENVELOPE_DDNS_OFF, enable_ddns={"meta": {"code": 200}}
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "ddns", "enable", "--force"])

        assert result.exit_code == 0
        mock_client.enable_ddns.assert_awaited_once_with(None)

    def test_skips_write_when_already_enabled(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_network={"meta": {"code": 200}, "data": {"ddns": True}},
            enable_ddns=AsyncMock(),
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "ddns", "enable"], input="y\n")

        assert result.exit_code == 0
        assert "already configured" in result.output.lower()
        mock_client.enable_ddns.assert_not_called()

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client(get_network=_NETWORK_ENVELOPE_DDNS_OFF)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--non-interactive", "network", "ddns", "enable"])

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.enable_ddns.assert_not_called()


class TestDdnsDisable:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_disables_ddns(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_network={"meta": {"code": 200}, "data": {"ddns": True}},
            disable_ddns={"meta": {"code": 200}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "ddns", "disable", "--force"])

        assert result.exit_code == 0
        mock_client.disable_ddns.assert_awaited_once_with(None)

    def test_skips_write_when_already_disabled(self, runner: CliRunner) -> None:
        # --force would also bypass write_if_changed's skip-unchanged
        # short-circuit, so answer the Y/N prompt instead.
        mock_client = _client(
            get_network=_NETWORK_ENVELOPE_DDNS_OFF,  # ddns: False
            disable_ddns=AsyncMock(),
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "ddns", "disable"], input="y\n")

        assert result.exit_code == 0
        assert "already configured" in result.output.lower()
        mock_client.disable_ddns.assert_not_called()

    def test_force_writes_even_when_already_disabled(self, runner: CliRunner) -> None:
        """--force writes anyway, per write_if_changed's --force contract."""
        mock_client = _client(
            get_network=_NETWORK_ENVELOPE_DDNS_OFF,  # ddns: False
            disable_ddns={"meta": {"code": 200}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "ddns", "disable", "--force"])

        assert result.exit_code == 0
        mock_client.disable_ddns.assert_awaited_once_with(None)

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_network={"meta": {"code": 200}, "data": {"ddns": True}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--non-interactive", "network", "ddns", "disable"])

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.disable_ddns.assert_not_called()
