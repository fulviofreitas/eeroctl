"""Unit tests for the `eero device type set` command.

Migration plan §4 phase B row 25: `set_device_type` is on the SDK's
live-verified allowlist (LOW risk, VERIFIED, no reboot). Covers:

- happy path (write issued)
- skip-unchanged (read-first short-circuit via `write_if_changed`)
- --force writes anyway even when unchanged
- --non-interactive (LOW risk never prompts, so this exits 0)
- premium/access-denied mappings surfaced through `run_with_client`
"""

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner
from eero.exceptions import EeroAccessDeniedException, EeroPremiumRequiredException

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli

MOCK_DEVICE = {
    "url": "/2.2/networks/net1/devices/dev1",
    "mac": "AA:BB:CC:DD:EE:FF",
    "nickname": "MyPhone",
    "hostname": "myphone",
    "connected": True,
    "blacklisted": False,
    "paused": False,
    "device_type": "computer",
}


def _devices_response(device: dict) -> dict:
    return {"meta": {"code": 200}, "data": [device]}


class TestDeviceTypeGroup:
    """Tests for the `device type` command group."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_device_type_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["device", "type", "--help"])

        assert result.exit_code == 0
        assert "set" in result.output


class TestDeviceTypeSet:
    """Tests for `device type set`."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["device", "type", "set", "--help"])

        assert result.exit_code == 0
        assert "Set a device's type" in result.output
        assert "--force" in result.output

    def test_requires_arguments(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["device", "type", "set"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_device_not_found(self, runner: CliRunner) -> None:
        mock_client = AsyncMock()
        mock_client.get_devices = AsyncMock(return_value=_devices_response(MOCK_DEVICE))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["device", "type", "set", "NoSuchDevice", "router"])

        assert result.exit_code == ExitCode.NOT_FOUND
        mock_client.set_device_type.assert_not_called()

    def test_device_not_found_keeps_stdout_clean_under_json_output(self, runner: CliRunner) -> None:
        """The not-found error prints to stderr, not stdout, under --output
        json (security review: device.py:360 used to bind stdout for this
        path, corrupting `--output json | jq` on a write command)."""
        mock_client = AsyncMock()
        mock_client.get_devices = AsyncMock(return_value=_devices_response(MOCK_DEVICE))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", "json", "device", "type", "set", "NoSuchDevice", "router"]
            )

        assert result.exit_code == ExitCode.NOT_FOUND
        assert result.stdout == ""

    def test_happy_path_calls_set_device_type(self, runner: CliRunner) -> None:
        """A changed type is written via `set_device_type(id, type, network_id)`."""
        mock_client = AsyncMock()
        mock_client.get_devices = AsyncMock(return_value=_devices_response(MOCK_DEVICE))
        mock_client.set_device_type = AsyncMock(
            return_value={"meta": {"code": 200}, "data": {"device_type": "router"}}
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["device", "type", "set", "MyPhone", "router"])

        assert result.exit_code == 0
        assert "accepted" in result.output.lower()
        mock_client.set_device_type.assert_awaited_once()
        call_args = mock_client.set_device_type.call_args
        assert call_args[0][1] == "router"

    def test_skip_unchanged(self, runner: CliRunner) -> None:
        """No write happens when the device already has the requested type."""
        mock_client = AsyncMock()
        mock_client.get_devices = AsyncMock(return_value=_devices_response(MOCK_DEVICE))
        mock_client.set_device_type = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["device", "type", "set", "MyPhone", "computer"])

        assert result.exit_code == 0
        assert "already configured" in result.output.lower()
        mock_client.set_device_type.assert_not_called()

    def test_force_writes_even_when_unchanged(self, runner: CliRunner) -> None:
        """--force writes anyway, per write_if_changed's --force contract."""
        mock_client = AsyncMock()
        mock_client.get_devices = AsyncMock(return_value=_devices_response(MOCK_DEVICE))
        mock_client.set_device_type = AsyncMock(return_value={"meta": {"code": 200}, "data": {}})
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["device", "type", "set", "MyPhone", "computer", "--force"])

        assert result.exit_code == 0
        mock_client.set_device_type.assert_awaited_once()

    def test_non_interactive_low_risk_does_not_prompt(self, runner: CliRunner) -> None:
        """LOW risk never prompts, so --non-interactive still exits 0."""
        mock_client = AsyncMock()
        mock_client.get_devices = AsyncMock(return_value=_devices_response(MOCK_DEVICE))
        mock_client.set_device_type = AsyncMock(return_value={"meta": {"code": 200}, "data": {}})
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--non-interactive", "device", "type", "set", "MyPhone", "router"]
            )

        assert result.exit_code == 0
        mock_client.set_device_type.assert_awaited_once()

    def test_premium_required_maps_to_exit_code(self, runner: CliRunner) -> None:
        mock_client = AsyncMock()
        mock_client.get_devices = AsyncMock(
            side_effect=EeroPremiumRequiredException("premium plan required")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["device", "type", "set", "MyPhone", "router"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_code(self, runner: CliRunner, api_error) -> None:
        mock_client = AsyncMock()
        mock_client.get_devices = AsyncMock(
            side_effect=api_error(EeroAccessDeniedException, 403, "error.access.denied")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["device", "type", "set", "MyPhone", "router"])

        assert result.exit_code == ExitCode.FORBIDDEN
