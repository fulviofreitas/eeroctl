"""Unit tests for eeroctl.commands.profile module.

Tests cover:
- profile list command
- profile show command
- profile pause/unpause commands
- profile apps subcommands
- profile schedule subcommands
"""

import pytest
from click.testing import CliRunner

from eeroctl.main import cli


class TestProfileGroup:
    """Tests for the profile command group."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_profile_help(self, runner):
        """Test profile group shows help."""
        result = runner.invoke(cli, ["profile", "--help"])

        assert result.exit_code == 0
        assert "Manage profiles" in result.output
        assert "list" in result.output
        assert "show" in result.output
        assert "pause" in result.output
        assert "unpause" in result.output
        assert "apps" in result.output
        assert "schedule" in result.output


class TestProfileList:
    """Tests for profile list command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_profile_list_help(self, runner):
        """Test profile list shows help."""
        result = runner.invoke(cli, ["profile", "list", "--help"])

        assert result.exit_code == 0
        assert "List all profiles" in result.output


class TestProfileShow:
    """Tests for profile show command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_profile_show_help(self, runner):
        """Test profile show shows help."""
        result = runner.invoke(cli, ["profile", "show", "--help"])

        assert result.exit_code == 0
        assert "Show details of a specific profile" in result.output
        assert "PROFILE_ID" in result.output

    def test_profile_show_requires_argument(self, runner):
        """Test profile show requires profile ID argument."""
        result = runner.invoke(cli, ["profile", "show"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output


class TestProfilePause:
    """Tests for profile pause command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_profile_pause_help(self, runner):
        """Test profile pause shows help."""
        result = runner.invoke(cli, ["profile", "pause", "--help"])

        assert result.exit_code == 0
        assert "Pause internet access" in result.output
        assert "--force" in result.output
        assert "--duration" in result.output

    def test_profile_pause_requires_argument(self, runner):
        """Test profile pause requires profile ID argument."""
        result = runner.invoke(cli, ["profile", "pause"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output


class TestProfileUnpause:
    """Tests for profile unpause command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_profile_unpause_help(self, runner):
        """Test profile unpause shows help."""
        result = runner.invoke(cli, ["profile", "unpause", "--help"])

        assert result.exit_code == 0
        assert "Resume internet access" in result.output
        assert "--force" in result.output

    def test_profile_unpause_requires_argument(self, runner):
        """Test profile unpause requires profile ID argument."""
        result = runner.invoke(cli, ["profile", "unpause"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output


class TestProfileApps:
    """Tests for profile apps subcommands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_apps_group_help(self, runner):
        """Test apps group shows help."""
        result = runner.invoke(cli, ["profile", "apps", "--help"])

        assert result.exit_code == 0
        assert "Manage blocked applications" in result.output
        assert "list" in result.output
        assert "block" in result.output
        assert "unblock" in result.output

    def test_apps_list_help(self, runner):
        """Test apps list shows help."""
        result = runner.invoke(cli, ["profile", "apps", "list", "--help"])

        assert result.exit_code == 0
        assert "List blocked applications" in result.output

    def test_apps_list_requires_argument(self, runner):
        """Test apps list requires profile ID argument."""
        result = runner.invoke(cli, ["profile", "apps", "list"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_apps_block_help(self, runner):
        """Test apps block shows help."""
        result = runner.invoke(cli, ["profile", "apps", "block", "--help"])

        assert result.exit_code == 0
        assert "Block application" in result.output

    def test_apps_block_requires_arguments(self, runner):
        """Test apps block requires profile ID and apps arguments."""
        result = runner.invoke(cli, ["profile", "apps", "block", "profile_id"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_apps_unblock_help(self, runner):
        """Test apps unblock shows help."""
        result = runner.invoke(cli, ["profile", "apps", "unblock", "--help"])

        assert result.exit_code == 0
        assert "Unblock application" in result.output


class TestProfileSchedule:
    """Tests for profile schedule subcommands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_schedule_group_help(self, runner):
        """Test schedule group shows help."""
        result = runner.invoke(cli, ["profile", "schedule", "--help"])

        assert result.exit_code == 0
        assert "Manage internet access schedule" in result.output
        assert "show" in result.output
        assert "set" in result.output
        assert "clear" in result.output

    def test_schedule_show_help(self, runner):
        """Test schedule show shows help."""
        result = runner.invoke(cli, ["profile", "schedule", "show", "--help"])

        assert result.exit_code == 0
        assert "Show schedule" in result.output

    def test_schedule_show_requires_argument(self, runner):
        """Test schedule show requires profile ID argument."""
        result = runner.invoke(cli, ["profile", "schedule", "show"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_schedule_set_help(self, runner):
        """Test schedule set shows help."""
        result = runner.invoke(cli, ["profile", "schedule", "set", "--help"])

        assert result.exit_code == 0
        assert "Set bedtime schedule" in result.output
        assert "--start" in result.output
        assert "--end" in result.output
        assert "--days" in result.output
        assert "--force" in result.output

    def test_schedule_set_requires_options(self, runner):
        """Test schedule set requires start and end options."""
        result = runner.invoke(cli, ["profile", "schedule", "set", "profile_id"])

        assert result.exit_code != 0
        assert "--start" in result.output or "Missing option" in result.output

    def test_schedule_clear_help(self, runner):
        """Test schedule clear shows help."""
        result = runner.invoke(cli, ["profile", "schedule", "clear", "--help"])

        assert result.exit_code == 0
        assert "Clear all schedules" in result.output
        assert "--force" in result.output

    def test_schedule_clear_requires_argument(self, runner):
        """Test schedule clear requires profile ID argument."""
        result = runner.invoke(cli, ["profile", "schedule", "clear"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output
