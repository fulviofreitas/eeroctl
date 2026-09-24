"""Unit tests for `device wan-access`.

Migration plan §4 phase C row 47 (#52). Mocks at the SDK boundary
(`patch("eeroctl.utils.EeroClient", ...)`).
"""

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli

_DEVICES_RESPONSE = {
    "meta": {"code": 200},
    "data": [
        {
            "url": "/2.2/networks/net1/devices/dev1",
            "mac": "AA:BB:CC:DD:EE:FF",
            "nickname": "MyPhone",
            "hostname": "myphone",
            "connected": True,
        }
    ],
}


def _client(**method_return_values) -> AsyncMock:
    client = AsyncMock()
    for name, value in method_return_values.items():
        setattr(client, name, AsyncMock(return_value=value))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestDeviceWanAccess:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_requires_exactly_one_of_deny_allow(self, runner: CliRunner) -> None:
        mock_client = _client(get_devices=_DEVICES_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["device", "wan-access", "MyPhone", "--force"])

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.set_device_secondary_wan_access.assert_not_called()

    def test_both_deny_and_allow_exits_usage_error(self, runner: CliRunner) -> None:
        mock_client = _client(get_devices=_DEVICES_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["device", "wan-access", "MyPhone", "--deny", "--allow", "--force"]
            )

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.set_device_secondary_wan_access.assert_not_called()

    def test_deny_requires_reboot_phrase(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_devices=_DEVICES_RESPONSE,
            set_device_secondary_wan_access={"meta": {"code": 200}, "data": {}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["device", "wan-access", "MyPhone", "--deny"], input="REBOOT\n"
            )

        assert result.exit_code == 0
        mock_client.set_device_secondary_wan_access.assert_awaited_once_with(
            "AA:BB:CC:DD:EE:FF", deny=True, network_id=None
        )

    def test_deny_wrong_phrase_is_safety_rail(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_devices=_DEVICES_RESPONSE,
            set_device_secondary_wan_access={"meta": {"code": 200}, "data": {}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["device", "wan-access", "MyPhone", "--deny"], input="nope\n"
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_device_secondary_wan_access.assert_not_called()

    def test_allow_requires_reboot_phrase(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_devices=_DEVICES_RESPONSE,
            set_device_secondary_wan_access={"meta": {"code": 200}, "data": {}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["device", "wan-access", "MyPhone", "--allow"], input="REBOOT\n"
            )

        assert result.exit_code == 0
        mock_client.set_device_secondary_wan_access.assert_awaited_once_with(
            "AA:BB:CC:DD:EE:FF", deny=False, network_id=None
        )

    def test_allow_wrong_phrase_is_safety_rail(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_devices=_DEVICES_RESPONSE,
            set_device_secondary_wan_access={"meta": {"code": 200}, "data": {}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["device", "wan-access", "MyPhone", "--allow"], input="nope\n"
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_device_secondary_wan_access.assert_not_called()

    def test_allow_with_force(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_devices=_DEVICES_RESPONSE,
            set_device_secondary_wan_access={"meta": {"code": 200}, "data": {}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["device", "wan-access", "MyPhone", "--allow", "--force"])

        assert result.exit_code == 0
        mock_client.set_device_secondary_wan_access.assert_awaited_once_with(
            "AA:BB:CC:DD:EE:FF", deny=False, network_id=None
        )

    def test_device_not_found_exits_not_found(self, runner: CliRunner) -> None:
        mock_client = _client(get_devices={"meta": {"code": 200}, "data": []})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["device", "wan-access", "NoSuchDevice", "--deny", "--force"]
            )

        assert result.exit_code == ExitCode.NOT_FOUND
        mock_client.set_device_secondary_wan_access.assert_not_called()

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client(get_devices=_DEVICES_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--non-interactive", "device", "wan-access", "MyPhone", "--deny"]
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_device_secondary_wan_access.assert_not_called()
