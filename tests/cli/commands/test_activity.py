"""Unit tests for eero_cli.commands.activity module.

Tests cover:
- activity summary command
- activity clients command
- activity history command
- activity categories command
"""

import pytest
from click.testing import CliRunner

from eero_cli.main import cli


class TestActivityGroup:
    """Tests for the activity command group."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_activity_help(self, runner):
        """Test activity group shows help."""
        result = runner.invoke(cli, ["activity", "--help"])

        assert result.exit_code == 0
        assert "View network activity" in result.output or "activity" in result.output.lower()
        assert "summary" in result.output
        assert "clients" in result.output
        assert "history" in result.output
        assert "categories" in result.output

    def test_activity_mentions_eero_plus(self, runner):
        """Test activity help mentions Eero Plus requirement."""
        result = runner.invoke(cli, ["activity", "--help"])

        assert result.exit_code == 0
        assert "Plus" in result.output or "premium" in result.output.lower()


class TestActivitySummary:
    """Tests for activity summary command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_activity_summary_help(self, runner):
        """Test activity summary shows help."""
        result = runner.invoke(cli, ["activity", "summary", "--help"])

        assert result.exit_code == 0
        assert "Show network activity summary" in result.output


class TestActivityClients:
    """Tests for activity clients command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_activity_clients_help(self, runner):
        """Test activity clients shows help."""
        result = runner.invoke(cli, ["activity", "clients", "--help"])

        assert result.exit_code == 0
        assert "Show per-client activity" in result.output


class TestActivityHistory:
    """Tests for activity history command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_activity_history_help(self, runner):
        """Test activity history shows help."""
        result = runner.invoke(cli, ["activity", "history", "--help"])

        assert result.exit_code == 0
        assert "Show historical activity" in result.output
        assert "--period" in result.output

    def test_activity_history_period_options(self, runner):
        """Test activity history accepts valid period options."""
        result = runner.invoke(cli, ["activity", "history", "--help"])

        assert result.exit_code == 0
        assert "hour" in result.output
        assert "day" in result.output
        assert "week" in result.output
        assert "month" in result.output


class TestActivityCategories:
    """Tests for activity categories command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_activity_categories_help(self, runner):
        """Test activity categories shows help."""
        result = runner.invoke(cli, ["activity", "categories", "--help"])

        assert result.exit_code == 0
        assert "Show activity" in result.output
        assert "category" in result.output.lower()


class TestActivityFormatBytes:
    """Tests for the _format_bytes helper function."""

    def test_format_bytes_values(self):
        """Test _format_bytes formats values correctly."""
        from eero_cli.commands.activity import _format_bytes

        assert "B" in _format_bytes(500)
        assert "KB" in _format_bytes(2048)
        assert "MB" in _format_bytes(1024 * 1024 * 5)
        assert "GB" in _format_bytes(1024 * 1024 * 1024 * 2)

    def test_format_bytes_zero(self):
        """Test _format_bytes handles zero."""
        from eero_cli.commands.activity import _format_bytes

        result = _format_bytes(0)
        assert "0" in result
        assert "B" in result
