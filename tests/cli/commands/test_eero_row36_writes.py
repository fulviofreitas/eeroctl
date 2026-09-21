"""Unit tests for `eero location set`, `pppoe set`, `ports cycle`, `port`,
`led cycle`, and `nightlight override`.

Migration plan §4 phase C row 36. Mocks at the SDK boundary
(`patch("eeroctl.utils.EeroClient", ...)`).
"""

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli

_EERO_ENVELOPE = {
    "meta": {"code": 200},
    "data": {"url": "/2.2/networks/net1/eeros/123", "location": "Office", "serial": "SERIAL123"},
}


def _client(**method_return_values) -> AsyncMock:
    client = AsyncMock()
    for name, value in method_return_values.items():
        setattr(client, name, AsyncMock(return_value=value))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestLocationSet:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_sets_location(self, runner: CliRunner) -> None:
        mock_client = _client(get_eero=_EERO_ENVELOPE, set_location={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["eero", "location", "set", "123", "Kitchen", "--force"])

        assert result.exit_code == 0
        mock_client.set_location.assert_awaited_once_with("123", "Kitchen", None)

    def test_eero_not_found(self, runner: CliRunner) -> None:
        mock_client = _client(get_eero=None, get_eeros={"meta": {"code": 200}, "data": []})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["eero", "location", "set", "nosuch", "Kitchen", "--force"])

        assert result.exit_code == ExitCode.NOT_FOUND


class TestPppoeSet:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_password_flag_calls_set_pppoe(self, runner: CliRunner) -> None:
        mock_client = _client(get_eero=_EERO_ENVELOPE, set_pppoe={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "eero",
                    "pppoe",
                    "set",
                    "123",
                    "--username",
                    "isp-user",
                    "--password",
                    "isp-pass",
                    "--force",
                ],
            )

        assert result.exit_code == 0
        mock_client.set_pppoe.assert_awaited_once_with(
            "123", username="isp-user", password="isp-pass"
        )
        assert "isp-pass" not in result.output

    def test_non_interactive_without_password_exits_usage_error(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--non-interactive",
                    "eero",
                    "pppoe",
                    "set",
                    "123",
                    "--username",
                    "isp-user",
                ],
            )

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.set_pppoe.assert_not_called()


class TestPortsCycle:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_cycle_without_reboot(self, runner: CliRunner) -> None:
        mock_client = _client(get_eero=_EERO_ENVELOPE, node_action={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["eero", "ports", "cycle", "123", "--force"])

        assert result.exit_code == 0
        mock_client.node_action.assert_awaited_once_with("123", "POWER_CYCLE_ALL_PORTS", None)

    def test_cycle_with_reboot(self, runner: CliRunner) -> None:
        mock_client = _client(get_eero=_EERO_ENVELOPE, node_action={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["eero", "ports", "cycle", "123", "--reboot", "--force"])

        assert result.exit_code == 0
        mock_client.node_action.assert_awaited_once_with(
            "123", "POWER_CYCLE_ALL_PORTS_AND_REBOOT", None
        )

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client(get_eero=_EERO_ENVELOPE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--non-interactive", "eero", "ports", "cycle", "123"])

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.node_action.assert_not_called()


class TestPortAction:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_invalid_action_rejected(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["eero", "port", "123", "1", "BOGUS_ACTION"])

        assert result.exit_code != 0

    def test_applies_action(self, runner: CliRunner) -> None:
        mock_client = _client(get_eero=_EERO_ENVELOPE, port_action={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["eero", "port", "123", "1", "ENABLE_PORT", "--force"])

        assert result.exit_code == 0
        mock_client.port_action.assert_awaited_once_with("123", "1", "ENABLE_PORT", None)


class TestLedCycle:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_cycles_led_by_serial(self, runner: CliRunner) -> None:
        mock_client = _client(get_eero=_EERO_ENVELOPE, led_cycle={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "eero",
                    "led",
                    "cycle",
                    "123",
                    "--colors",
                    "red,blue",
                    "--duration",
                    "10s",
                    "--time-per-color",
                    "1s",
                ],
            )

        assert result.exit_code == 0
        mock_client.led_cycle.assert_awaited_once_with(
            "SERIAL123", colors=["red", "blue"], duration="10s", time_per_color="1s"
        )


class TestNightlightOverride:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_applies_override(self, runner: CliRunner) -> None:
        mock_client = _client(get_eero=_EERO_ENVELOPE, nightlight_override={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["eero", "nightlight", "override", "123", "--brightness", "50"]
            )

        assert result.exit_code == 0
        mock_client.nightlight_override.assert_awaited_once_with(
            "123", brightness_percentage=50, network_id=None
        )
