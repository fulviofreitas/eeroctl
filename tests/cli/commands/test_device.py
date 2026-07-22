"""Unit tests for eero.cli.commands.device module.

Tests cover:
- device list command
- device show command
- device rename command
- device block/unblock commands
- device pause/unpause commands
- device transformer regression (blacklisted field)
"""

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.main import cli


class TestDeviceGroup:
    """Tests for the device command group."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_device_help(self, runner):
        """Test device group shows help."""
        result = runner.invoke(cli, ["device", "--help"])

        assert result.exit_code == 0
        assert "Manage connected devices" in result.output
        assert "list" in result.output
        assert "show" in result.output
        assert "rename" in result.output
        assert "block" in result.output
        assert "unblock" in result.output
        assert "pause" in result.output
        assert "unpause" in result.output

    def test_device_help_no_priority(self, runner):
        """Test device group help does not mention priority."""
        result = runner.invoke(cli, ["device", "--help"])

        assert result.exit_code == 0
        assert "priority" not in result.output


class TestDeviceList:
    """Tests for device list command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_device_list_help(self, runner):
        """Test device list shows help."""
        result = runner.invoke(cli, ["device", "list", "--help"])

        assert result.exit_code == 0
        assert "List all connected devices" in result.output


class TestDeviceShow:
    """Tests for device show command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_device_show_help(self, runner):
        """Test device show shows help."""
        result = runner.invoke(cli, ["device", "show", "--help"])

        assert result.exit_code == 0
        assert "Show details of a specific device" in result.output
        assert "DEVICE_ID" in result.output

    def test_device_show_requires_argument(self, runner):
        """Test device show requires device ID argument."""
        result = runner.invoke(cli, ["device", "show"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output


class TestDeviceRename:
    """Tests for device rename command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_device_rename_help(self, runner):
        """Test device rename shows help."""
        result = runner.invoke(cli, ["device", "rename", "--help"])

        assert result.exit_code == 0
        assert "Rename a device" in result.output
        assert "--name" in result.output

    def test_device_rename_requires_argument(self, runner):
        """Test device rename requires device ID argument."""
        result = runner.invoke(cli, ["device", "rename", "--name", "New Name"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_device_rename_requires_name_option(self, runner):
        """Test device rename requires --name option."""
        result = runner.invoke(cli, ["device", "rename", "device_id"])

        assert result.exit_code != 0
        assert "Missing option" in result.output or "--name" in result.output


class TestDeviceBlock:
    """Tests for device block command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_device_block_help(self, runner):
        """Test device block shows help."""
        result = runner.invoke(cli, ["device", "block", "--help"])

        assert result.exit_code == 0
        assert "Block a device" in result.output
        assert "--force" in result.output

    def test_device_block_requires_argument(self, runner):
        """Test device block requires device ID argument."""
        result = runner.invoke(cli, ["device", "block"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_device_block_calls_block_device(self, runner):
        """Test device block calls client.block_device with correct args."""
        mock_devices_response = {
            "meta": {"code": 200},
            "data": [
                {
                    "url": "/2.2/networks/net1/devices/dev1",
                    "mac": "AA:BB:CC:DD:EE:FF",
                    "nickname": "MyPhone",
                    "hostname": "myphone",
                    "connected": True,
                    "blacklisted": False,
                    "paused": False,
                }
            ],
        }
        mock_block_response = {"meta": {"code": 200}, "data": {}}

        mock_client = AsyncMock()
        mock_client.get_devices = AsyncMock(return_value=mock_devices_response)
        mock_client.block_device = AsyncMock(return_value=mock_block_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["device", "block", "MyPhone", "--force"])

        assert result.exit_code == 0
        assert "blocked" in result.output.lower()
        mock_client.block_device.assert_awaited_once()
        call_args = mock_client.block_device.call_args
        assert call_args[0][1] is True  # blocked=True


class TestDeviceUnblock:
    """Tests for device unblock command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_device_unblock_help(self, runner):
        """Test device unblock shows help."""
        result = runner.invoke(cli, ["device", "unblock", "--help"])

        assert result.exit_code == 0
        assert "Unblock a device" in result.output
        assert "--force" in result.output

    def test_device_unblock_requires_argument(self, runner):
        """Test device unblock requires device ID argument."""
        result = runner.invoke(cli, ["device", "unblock"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output


class TestDevicePause:
    """Tests for device pause command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_device_pause_help(self, runner):
        """Test device pause shows help."""
        result = runner.invoke(cli, ["device", "pause", "--help"])

        assert result.exit_code == 0
        assert "Pause a device" in result.output
        assert "--force" in result.output

    def test_device_pause_requires_argument(self, runner):
        """Test device pause requires device ID argument."""
        result = runner.invoke(cli, ["device", "pause"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_device_pause_calls_pause_device(self, runner):
        """Test device pause calls client.pause_device with paused=True."""
        mock_devices_response = {
            "meta": {"code": 200},
            "data": [
                {
                    "url": "/2.2/networks/net1/devices/dev1",
                    "mac": "AA:BB:CC:DD:EE:FF",
                    "nickname": "MyPhone",
                    "hostname": "myphone",
                    "connected": True,
                    "blacklisted": False,
                    "paused": False,
                }
            ],
        }
        mock_pause_response = {"meta": {"code": 200}, "data": {}}

        mock_client = AsyncMock()
        mock_client.get_devices = AsyncMock(return_value=mock_devices_response)
        mock_client.pause_device = AsyncMock(return_value=mock_pause_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["device", "pause", "MyPhone", "--force"])

        assert result.exit_code == 0
        assert "paused" in result.output.lower()
        mock_client.pause_device.assert_awaited_once()
        call_args = mock_client.pause_device.call_args
        assert call_args[0][1] is True  # paused=True

    def test_device_pause_passes_network_id(self, runner):
        """Test device pause passes network_id to pause_device."""
        mock_devices_response = {
            "meta": {"code": 200},
            "data": [
                {
                    "url": "/2.2/networks/net1/devices/dev1",
                    "mac": "AA:BB:CC:DD:EE:FF",
                    "nickname": "Tablet",
                    "hostname": "tablet",
                    "connected": True,
                    "blacklisted": False,
                    "paused": False,
                }
            ],
        }
        mock_pause_response = {"meta": {"code": 200}, "data": {}}

        mock_client = AsyncMock()
        mock_client.get_devices = AsyncMock(return_value=mock_devices_response)
        mock_client.pause_device = AsyncMock(return_value=mock_pause_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["device", "pause", "Tablet", "--force", "--network-id", "mynet123"]
            )

        assert result.exit_code == 0
        call_args = mock_client.pause_device.call_args
        # Third positional arg is network_id
        assert call_args[0][2] == "mynet123"


class TestDeviceUnpause:
    """Tests for device unpause command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_device_unpause_help(self, runner):
        """Test device unpause shows help."""
        result = runner.invoke(cli, ["device", "unpause", "--help"])

        assert result.exit_code == 0
        assert "Unpause a device" in result.output
        assert "--force" in result.output

    def test_device_unpause_requires_argument(self, runner):
        """Test device unpause requires device ID argument."""
        result = runner.invoke(cli, ["device", "unpause"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_device_unpause_calls_pause_device_false(self, runner):
        """Test device unpause calls client.pause_device with paused=False."""
        mock_devices_response = {
            "meta": {"code": 200},
            "data": [
                {
                    "url": "/2.2/networks/net1/devices/dev1",
                    "mac": "AA:BB:CC:DD:EE:FF",
                    "nickname": "MyLaptop",
                    "hostname": "mylaptop",
                    "connected": True,
                    "blacklisted": False,
                    "paused": True,
                }
            ],
        }
        mock_unpause_response = {"meta": {"code": 200}, "data": {}}

        mock_client = AsyncMock()
        mock_client.get_devices = AsyncMock(return_value=mock_devices_response)
        mock_client.pause_device = AsyncMock(return_value=mock_unpause_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["device", "unpause", "MyLaptop", "--force"])

        assert result.exit_code == 0
        assert "unpaused" in result.output.lower()
        mock_client.pause_device.assert_awaited_once()
        call_args = mock_client.pause_device.call_args
        assert call_args[0][1] is False  # paused=False


class TestDeviceTransformerRegression:
    """Regression tests for #106 — blacklisted field in transformer."""

    def test_blacklisted_true_maps_to_blocked_true(self):
        """Raw dict with blacklisted=True must yield blocked=True and blacklisted=True."""
        from eeroctl.transformers.device import normalize_device

        raw = {
            "url": "/2.2/networks/net1/devices/dev1",
            "mac": "AA:BB:CC:DD:EE:FF",
            "blacklisted": True,
            "paused": False,
            "connected": True,
        }
        result = normalize_device(raw)

        assert result["blocked"] is True
        assert result["blacklisted"] is True

    def test_blacklisted_false_maps_to_blocked_false(self):
        """Raw dict with blacklisted=False must yield blocked=False."""
        from eeroctl.transformers.device import normalize_device

        raw = {
            "url": "/2.2/networks/net1/devices/dev1",
            "mac": "AA:BB:CC:DD:EE:FF",
            "blacklisted": False,
            "paused": False,
            "connected": True,
        }
        result = normalize_device(raw)

        assert result["blocked"] is False
        assert result["blacklisted"] is False

    def test_missing_blacklisted_defaults_to_false(self):
        """Raw dict with no blacklisted key must default blocked/blacklisted to False."""
        from eeroctl.transformers.device import normalize_device

        raw = {
            "url": "/2.2/networks/net1/devices/dev1",
            "mac": "AA:BB:CC:DD:EE:FF",
            "paused": False,
            "connected": True,
        }
        result = normalize_device(raw)

        assert result["blocked"] is False
        assert result["blacklisted"] is False

    def test_no_spurious_blocked_field_is_not_used(self):
        """A raw dict with only 'blocked' (wrong field) must NOT propagate as blocked=True."""
        from eeroctl.transformers.device import normalize_device

        raw = {
            "url": "/2.2/networks/net1/devices/dev1",
            "mac": "AA:BB:CC:DD:EE:FF",
            "blocked": True,  # wrong SDK field; SDK uses 'blacklisted'
            "paused": False,
            "connected": True,
        }
        result = normalize_device(raw)

        # 'blacklisted' key absent → blocked and blacklisted should both be False
        assert result["blocked"] is False
        assert result["blacklisted"] is False
