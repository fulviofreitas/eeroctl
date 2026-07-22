"""Unit tests for eeroctl.commands.activity module.

Tests cover:
- activity history command (get_insights)
- activity categories command (get_insights, hardcoded blocked)
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.main import cli

# ---------------------------------------------------------------------------
# Shared fixture data
# ---------------------------------------------------------------------------

INSIGHTS_RESPONSE = {
    "meta": {"code": 200},
    "data": {
        "series": [
            {
                "insight_type": "inspected",
                "sum": 42,
                "values": [{"time": "2026-07-21T00:00:00Z", "value": 42}],
            }
        ]
    },
}

BLOCKED_INSIGHTS_RESPONSE = {
    "meta": {"code": 200},
    "data": {
        "series": [
            {
                "insight_type": "blocked",
                "sum": 17,
                "values": [
                    {"time": "2026-07-20T00:00:00Z", "value": 8},
                    {"time": "2026-07-21T00:00:00Z", "value": 9},
                ],
            }
        ]
    },
}


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
        assert "activity" in result.output.lower()
        assert "history" in result.output
        assert "categories" in result.output

    def test_activity_help_no_summary_or_clients(self, runner):
        """Test activity help does not mention removed summary/clients subcommands."""
        result = runner.invoke(cli, ["activity", "--help"])

        assert result.exit_code == 0
        assert "summary" not in result.output
        assert "clients" not in result.output

    def test_activity_mentions_eero_plus(self, runner):
        """Test activity help mentions Eero Plus requirement."""
        result = runner.invoke(cli, ["activity", "--help"])

        assert result.exit_code == 0
        assert "Plus" in result.output or "premium" in result.output.lower()


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
        assert "--start" in result.output
        assert "--end" in result.output

    def test_activity_history_requires_start(self, runner):
        """Test activity history exits with code 2 when --start is missing."""
        result = runner.invoke(cli, ["activity", "history", "--end", "2026-07-22"])

        assert result.exit_code == 2
        assert "start" in result.output.lower() or "Missing option" in result.output

    def test_activity_history_requires_end(self, runner):
        """Test activity history exits with code 2 when --end is missing."""
        result = runner.invoke(cli, ["activity", "history", "--start", "2026-07-01"])

        assert result.exit_code == 2
        assert "end" in result.output.lower() or "Missing option" in result.output

    def test_activity_history_requires_both_flags(self, runner):
        """Test activity history exits with code 2 when both --start and --end are missing."""
        result = runner.invoke(cli, ["activity", "history"])

        assert result.exit_code == 2

    def test_activity_history_renders_table(self, runner):
        """Test activity history renders a table with insight_type and sum."""
        mock_client = AsyncMock()
        mock_client.get_insights = AsyncMock(return_value=INSIGHTS_RESPONSE)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "activity",
                    "history",
                    "--start",
                    "2026-07-01",
                    "--end",
                    "2026-07-22",
                ],
            )

        assert result.exit_code == 0
        assert "inspected" in result.output
        assert "42" in result.output

    def test_activity_history_calls_get_insights_with_correct_args(self, runner):
        """Test activity history passes all required args to get_insights."""
        mock_client = AsyncMock()
        mock_client.get_insights = AsyncMock(return_value=INSIGHTS_RESPONSE)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            runner.invoke(
                cli,
                [
                    "activity",
                    "history",
                    "--start",
                    "2026-07-01",
                    "--end",
                    "2026-07-22",
                    "--insight-type",
                    "blocked",
                    "--cadence",
                    "weekly",
                ],
            )

        mock_client.get_insights.assert_awaited_once()
        call_kwargs = mock_client.get_insights.call_args[1]
        assert call_kwargs["start"] == "2026-07-01"
        assert call_kwargs["end"] == "2026-07-22"
        assert call_kwargs["insight_type"] == "blocked"
        assert call_kwargs["cadence"] == "weekly"

    def test_activity_history_json_output_round_trips_envelope(self, runner):
        """Test activity history --output json round-trips the API envelope."""
        mock_client = AsyncMock()
        mock_client.get_insights = AsyncMock(return_value=INSIGHTS_RESPONSE)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--output",
                    "json",
                    "activity",
                    "history",
                    "--start",
                    "2026-07-01",
                    "--end",
                    "2026-07-22",
                ],
            )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        # The CLI wraps in its own envelope; raw data nested inside
        assert "inspected" in result.output
        assert "42" in result.output
        assert parsed is not None


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
        assert "blocked" in result.output.lower() or "category" in result.output.lower()

    def test_activity_categories_requires_start(self, runner):
        """Test activity categories exits with code 2 when --start is missing."""
        result = runner.invoke(cli, ["activity", "categories", "--end", "2026-07-22"])

        assert result.exit_code == 2

    def test_activity_categories_requires_end(self, runner):
        """Test activity categories exits with code 2 when --end is missing."""
        result = runner.invoke(cli, ["activity", "categories", "--start", "2026-07-01"])

        assert result.exit_code == 2

    def test_activity_categories_renders_table(self, runner):
        """Test activity categories renders table with blocked insight data."""
        mock_client = AsyncMock()
        mock_client.get_insights = AsyncMock(return_value=BLOCKED_INSIGHTS_RESPONSE)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "activity",
                    "categories",
                    "--start",
                    "2026-07-01",
                    "--end",
                    "2026-07-22",
                ],
            )

        assert result.exit_code == 0
        assert "blocked" in result.output
        assert "17" in result.output

    def test_activity_categories_hardcodes_blocked_insight_type(self, runner):
        """Test categories always passes insight_type='blocked' to get_insights."""
        mock_client = AsyncMock()
        mock_client.get_insights = AsyncMock(return_value=BLOCKED_INSIGHTS_RESPONSE)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            runner.invoke(
                cli,
                [
                    "activity",
                    "categories",
                    "--start",
                    "2026-07-01",
                    "--end",
                    "2026-07-22",
                ],
            )

        mock_client.get_insights.assert_awaited_once()
        call_kwargs = mock_client.get_insights.call_args[1]
        assert call_kwargs["insight_type"] == "blocked"

    def test_activity_categories_no_insight_type_option(self, runner):
        """Test activity categories does not expose --insight-type flag."""
        result = runner.invoke(
            cli,
            [
                "activity",
                "categories",
                "--start",
                "2026-07-01",
                "--end",
                "2026-07-22",
                "--insight-type",
                "adblock",
            ],
        )

        # Should fail because --insight-type is not a valid option for categories
        assert result.exit_code != 0
