"""Unit tests for `profile devices set`.

Migration plan §4 phase C row 30. Mocks at the SDK boundary
(`patch("eeroctl.utils.EeroClient", ...)`).
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

_DEVICES_RESPONSE = {
    "meta": {"code": 200},
    "data": [
        {
            "url": "/2.2/networks/net1/devices/dev1",
            "mac": "AA:BB:CC:DD:EE:FF",
            "nickname": "iPad",
        },
        {
            "url": "/2.2/networks/net1/devices/dev2",
            "mac": "11:22:33:44:55:66",
            "nickname": "Switch",
        },
    ],
}


def _client(**method_return_values) -> AsyncMock:
    client = AsyncMock()
    for name, value in method_return_values.items():
        setattr(client, name, AsyncMock(return_value=value))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestProfileDevicesSet:
    """Tests for `profile devices set`."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["profile", "devices", "set", "--help"])

        assert result.exit_code == 0
        assert "DEVICES" in result.output

    def test_profile_not_found(self, runner: CliRunner) -> None:
        mock_client = _client(get_profiles={"meta": {"code": 200}, "data": []})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["profile", "devices", "set", "NoSuchProfile", "iPad", "--force"]
            )

        assert result.exit_code == ExitCode.NOT_FOUND

    def test_device_not_found(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_profiles=_PROFILES_RESPONSE,
            get_devices=_DEVICES_RESPONSE,
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["profile", "devices", "set", "Kids", "NoSuchDevice", "--force"]
            )

        assert result.exit_code == ExitCode.NOT_FOUND
        mock_client.set_profile_devices.assert_not_called()

    def test_resolves_and_writes(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_profiles=_PROFILES_RESPONSE,
            get_devices=_DEVICES_RESPONSE,
            get_profile_devices={"meta": {"code": 200}, "data": {"devices": []}},
            set_profile_devices={"meta": {"code": 200}, "data": {}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["profile", "devices", "set", "Kids", "iPad", "11:22:33:44:55:66", "--force"],
            )

        assert result.exit_code == 0
        mock_client.set_profile_devices.assert_awaited_once()
        call_args = mock_client.set_profile_devices.call_args
        assert set(call_args[0][1]) == {
            "/2.2/networks/net1/devices/dev1",
            "/2.2/networks/net1/devices/dev2",
        }

    def test_skips_write_when_assignment_unchanged(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_profiles=_PROFILES_RESPONSE,
            get_devices=_DEVICES_RESPONSE,
            get_profile_devices={
                "meta": {"code": 200},
                "data": {"devices": [{"url": "/2.2/networks/net1/devices/dev1"}]},
            },
            set_profile_devices=AsyncMock(),
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["profile", "devices", "set", "Kids", "iPad"], input="y\n")

        assert result.exit_code == 0
        assert "already configured" in result.output.lower()
        mock_client.set_profile_devices.assert_not_called()

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_profiles=_PROFILES_RESPONSE,
            get_devices=_DEVICES_RESPONSE,
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--non-interactive", "profile", "devices", "set", "Kids", "iPad"]
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_profile_devices.assert_not_called()
