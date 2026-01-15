"""Unit tests for eero.cli.commands.client module.

Tests cover:
- client list command
- client show command
- client rename command
- client block/unblock commands
- client priority subcommands
"""

import pytest
from click.testing import CliRunner

from eero_cli.main import cli


class TestClientGroup:
    """Tests for the client command group."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_client_help(self, runner):
        """Test client group shows help."""
        result = runner.invoke(cli, ["client", "--help"])

        assert result.exit_code == 0
        assert "Manage connected devices" in result.output
        assert "list" in result.output
        assert "show" in result.output
        assert "rename" in result.output
        assert "block" in result.output
        assert "unblock" in result.output
        assert "priority" in result.output


class TestClientList:
    """Tests for client list command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_client_list_help(self, runner):
        """Test client list shows help."""
        result = runner.invoke(cli, ["client", "list", "--help"])

        assert result.exit_code == 0
        assert "List all connected devices" in result.output


class TestClientShow:
    """Tests for client show command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_client_show_help(self, runner):
        """Test client show shows help."""
        result = runner.invoke(cli, ["client", "show", "--help"])

        assert result.exit_code == 0
        assert "Show details of a specific device" in result.output
        assert "CLIENT_ID" in result.output

    def test_client_show_requires_argument(self, runner):
        """Test client show requires device ID argument."""
        result = runner.invoke(cli, ["client", "show"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output


class TestClientRename:
    """Tests for client rename command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_client_rename_help(self, runner):
        """Test client rename shows help."""
        result = runner.invoke(cli, ["client", "rename", "--help"])

        assert result.exit_code == 0
        assert "Rename a device" in result.output
        assert "--name" in result.output

    def test_client_rename_requires_argument(self, runner):
        """Test client rename requires device ID argument."""
        result = runner.invoke(cli, ["client", "rename", "--name", "New Name"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_client_rename_requires_name_option(self, runner):
        """Test client rename requires --name option."""
        result = runner.invoke(cli, ["client", "rename", "device_id"])

        assert result.exit_code != 0
        assert "Missing option" in result.output or "--name" in result.output


class TestClientBlock:
    """Tests for client block command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_client_block_help(self, runner):
        """Test client block shows help."""
        result = runner.invoke(cli, ["client", "block", "--help"])

        assert result.exit_code == 0
        assert "Block a device" in result.output
        assert "--force" in result.output

    def test_client_block_requires_argument(self, runner):
        """Test client block requires device ID argument."""
        result = runner.invoke(cli, ["client", "block"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output


class TestClientUnblock:
    """Tests for client unblock command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_client_unblock_help(self, runner):
        """Test client unblock shows help."""
        result = runner.invoke(cli, ["client", "unblock", "--help"])

        assert result.exit_code == 0
        assert "Unblock a device" in result.output
        assert "--force" in result.output

    def test_client_unblock_requires_argument(self, runner):
        """Test client unblock requires device ID argument."""
        result = runner.invoke(cli, ["client", "unblock"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output


class TestClientPriority:
    """Tests for client priority subcommands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_priority_group_help(self, runner):
        """Test priority group shows help."""
        result = runner.invoke(cli, ["client", "priority", "--help"])

        assert result.exit_code == 0
        assert "Manage device bandwidth priority" in result.output
        assert "show" in result.output
        assert "on" in result.output
        assert "off" in result.output

    def test_priority_show_help(self, runner):
        """Test priority show shows help."""
        result = runner.invoke(cli, ["client", "priority", "show", "--help"])

        assert result.exit_code == 0
        assert "Show priority status" in result.output

    def test_priority_show_requires_argument(self, runner):
        """Test priority show requires device ID argument."""
        result = runner.invoke(cli, ["client", "priority", "show"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_priority_on_help(self, runner):
        """Test priority on shows help."""
        result = runner.invoke(cli, ["client", "priority", "on", "--help"])

        assert result.exit_code == 0
        assert "Enable priority" in result.output
        assert "--minutes" in result.output

    def test_priority_off_help(self, runner):
        """Test priority off shows help."""
        result = runner.invoke(cli, ["client", "priority", "off", "--help"])

        assert result.exit_code == 0
        assert "Remove priority" in result.output
