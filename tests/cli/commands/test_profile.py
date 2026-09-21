"""Unit tests for eeroctl.commands.profile module.

Tests cover:
- profile list command
- profile show command
- profile pause/unpause commands
- profile apps subcommands
- profile schedule subcommands
"""

from unittest.mock import AsyncMock, patch

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


def _mock_client_for_apps(dns_policy_response, block_response=None):
    """Build an AsyncMock client wired for `profile apps` command tests."""
    mock_profiles_response = {
        "meta": {"code": 200},
        "data": [{"url": "/2.2/networks/net1/profiles/p1", "name": "Kids"}],
    }
    mock_client = AsyncMock()
    mock_client.get_profiles = AsyncMock(return_value=mock_profiles_response)
    mock_client.get_dns_policy_applications = AsyncMock(return_value=dns_policy_response)
    mock_client.set_profile_blocked_applications = AsyncMock(
        return_value=block_response or {"meta": {"code": 200}, "data": {}}
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestProfileAppsBlockedShapeValidation:
    """Tests for the fail-closed `_blocked_app_ids`/`_extract_dns_policy_applications`
    validation in `profile apps block`/`unblock` (security review finding, High).

    `set_profile_blocked_applications` REPLACES the full blocked-application
    list, so a wrong guess about the API's response shape would silently
    unblock (or block) every other application. These tests pin that the
    write is never attempted when the shape can't be trusted.
    """

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_bare_string_list_blocks_successfully(self, runner):
        """A bare-string `applications` list is a recognised shape."""
        dns_policy_response = {
            "meta": {"code": 200},
            "data": {"applications": ["facebook"], "categories_list": []},
        }
        mock_client = _mock_client_for_apps(dns_policy_response)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["profile", "apps", "block", "Kids", "tiktok"])

        assert result.exit_code == 0
        mock_client.set_profile_blocked_applications.assert_awaited_once()
        call_args = mock_client.set_profile_blocked_applications.call_args
        assert sorted(call_args[0][1]) == ["facebook", "tiktok"]

    def test_dict_list_with_blocked_key_blocks_successfully(self, runner):
        """A dict `applications` list where entries carry `blocked` is recognised."""
        dns_policy_response = {
            "meta": {"code": 200},
            "data": {
                "applications": [
                    {"id": "facebook", "name": "Facebook", "blocked": True},
                    {"id": "tiktok", "name": "TikTok", "blocked": False},
                ],
                "categories_list": [],
            },
        }
        mock_client = _mock_client_for_apps(dns_policy_response)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["profile", "apps", "block", "Kids", "tiktok"])

        assert result.exit_code == 0
        mock_client.set_profile_blocked_applications.assert_awaited_once()
        call_args = mock_client.set_profile_blocked_applications.call_args
        assert sorted(call_args[0][1]) == ["facebook", "tiktok"]

    def test_dict_list_without_any_blocked_key_fails_closed(self, runner):
        """Dict entries with no `blocked` key anywhere is an unrecognised shape:

        defaulting to "nothing is blocked" would silently unblock every real
        blocked app on the next write. Must exit 1 and never write.
        """
        dns_policy_response = {
            "meta": {"code": 200},
            "data": {
                "applications": [
                    {"id": "facebook", "name": "Facebook"},
                    {"id": "tiktok", "name": "TikTok"},
                ],
                "categories_list": [],
            },
        }
        mock_client = _mock_client_for_apps(dns_policy_response)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["profile", "apps", "block", "Kids", "tiktok"])

        assert result.exit_code == 1
        mock_client.set_profile_blocked_applications.assert_not_awaited()

    def test_missing_applications_key_fails_closed(self, runner):
        """A `data` envelope with no `applications` key at all must exit 1
        and never reach the write.
        """
        dns_policy_response = {
            "meta": {"code": 200},
            "data": {"categories_list": []},
        }
        mock_client = _mock_client_for_apps(dns_policy_response)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["profile", "apps", "block", "Kids", "tiktok"])

        assert result.exit_code == 1
        mock_client.set_profile_blocked_applications.assert_not_awaited()

    def test_unblock_dict_list_without_blocked_key_fails_closed(self, runner):
        """Same fail-closed rule applies to `apps unblock`."""
        dns_policy_response = {
            "meta": {"code": 200},
            "data": {
                "applications": [{"id": "facebook", "name": "Facebook"}],
                "categories_list": [],
            },
        }
        mock_client = _mock_client_for_apps(dns_policy_response)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["profile", "apps", "unblock", "Kids", "facebook"])

        assert result.exit_code == 1
        mock_client.set_profile_blocked_applications.assert_not_awaited()


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
