"""Unit tests for `network dhcp set|connection-mode set|nat-randomization`.

Migration plan §4 phase C row 35 -- all three are HIGH mesh-reboot writes.
Mocks at the SDK boundary (`patch("eeroctl.utils.EeroClient", ...)`).
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


class TestDhcpSet:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_no_options_exits_usage_error(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "dhcp", "set", "--force"])

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.set_dhcp.assert_not_called()

    def test_mode_requires_reboot_phrase(self, runner: CliRunner) -> None:
        mock_client = _client(set_dhcp={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "dhcp", "set", "--mode", "manual"], input="REBOOT\n"
            )

        assert result.exit_code == 0
        mock_client.set_dhcp.assert_awaited_once_with(
            None, mode="manual", custom=None, custom_v2=None
        )

    def test_custom_fields_build_custom_dict(self, runner: CliRunner) -> None:
        mock_client = _client(set_dhcp={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "dhcp",
                    "set",
                    "--start-ip",
                    "10.0.0.10",
                    "--end-ip",
                    "10.0.0.99",
                    "--force",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_client.set_dhcp.call_args.kwargs
        assert call_kwargs["custom"] == {"start_ip": "10.0.0.10", "end_ip": "10.0.0.99"}

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--non-interactive", "network", "dhcp", "set", "--mode", "automatic"]
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_dhcp.assert_not_called()


class TestConnectionModeSet:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_invalid_mode_rejected(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["network", "dhcp", "connection-mode", "set", "bogus"])

        assert result.exit_code != 0

    def test_sets_mode_with_reboot_phrase(self, runner: CliRunner) -> None:
        mock_client = _client(set_connection_mode={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["network", "dhcp", "connection-mode", "set", "BRIDGE"],
                input="REBOOT\n",
            )

        assert result.exit_code == 0
        mock_client.set_connection_mode.assert_awaited_once_with("BRIDGE", None)


class TestNatRandomization:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_enable_requires_reboot_phrase(self, runner: CliRunner) -> None:
        mock_client = _client(set_nat_port_randomization={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["network", "dhcp", "nat-randomization", "enable"],
                input="REBOOT\n",
            )

        assert result.exit_code == 0
        mock_client.set_nat_port_randomization.assert_awaited_once_with(True, None)

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--non-interactive", "network", "dhcp", "nat-randomization", "disable"]
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_nat_port_randomization.assert_not_called()
