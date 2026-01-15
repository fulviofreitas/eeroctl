"""Unit tests for eero.cli.commands.device module.

Tests cover:
- device list command
- device show command
- device rename command
- device block/unblock commands
- device priority subcommands
"""

import pytest
from click.testing import CliRunner

from eero_cli.main import cli


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
        assert "priority" in result.output


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


class TestDevicePriority:
    """Tests for device priority subcommands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_priority_group_help(self, runner):
        """Test priority group shows help."""
        result = runner.invoke(cli, ["device", "priority", "--help"])

        assert result.exit_code == 0
        assert "Manage device bandwidth priority" in result.output
        assert "show" in result.output
        assert "on" in result.output
        assert "off" in result.output

    def test_priority_show_help(self, runner):
        """Test priority show shows help."""
        result = runner.invoke(cli, ["device", "priority", "show", "--help"])

        assert result.exit_code == 0
        assert "Show priority status" in result.output

    def test_priority_show_requires_argument(self, runner):
        """Test priority show requires device ID argument."""
        result = runner.invoke(cli, ["device", "priority", "show"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_priority_on_help(self, runner):
        """Test priority on shows help."""
        result = runner.invoke(cli, ["device", "priority", "on", "--help"])

        assert result.exit_code == 0
        assert "Enable priority" in result.output
        assert "--minutes" in result.output

    def test_priority_off_help(self, runner):
        """Test priority off shows help."""
        result = runner.invoke(cli, ["device", "priority", "off", "--help"])

        assert result.exit_code == 0
        assert "Remove priority" in result.output
