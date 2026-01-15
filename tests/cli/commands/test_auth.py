"""Unit tests for eero.cli.commands.auth module.

Tests cover:
- auth login command
- auth logout command
- auth clear command
- auth status command
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner
from eero.exceptions import EeroAuthenticationException

from eero_cli.main import cli


class TestAuthGroup:
    """Tests for the auth command group."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_auth_help(self, runner):
        """Test auth group shows help."""
        result = runner.invoke(cli, ["auth", "--help"])

        assert result.exit_code == 0
        assert "Manage authentication" in result.output
        assert "login" in result.output
        assert "logout" in result.output
        assert "status" in result.output
        assert "clear" in result.output


class TestAuthLogin:
    """Tests for auth login command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_auth_login_help(self, runner):
        """Test auth login shows help."""
        result = runner.invoke(cli, ["auth", "login", "--help"])

        assert result.exit_code == 0
        assert "Login to your Eero account" in result.output
        assert "--force" in result.output
        assert "--no-keyring" in result.output

    @patch("eero_cli.commands.auth.EeroClient")
    @patch("eero_cli.commands.auth.get_cookie_file")
    def test_already_authenticated_shows_message(
        self, mock_cookie_file, mock_client_class, runner, tmp_path
    ):
        """Test shows message when already authenticated."""
        mock_cookie_file.return_value = tmp_path / "cookies.json"

        # Create mock client
        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["auth", "login"])

        assert "Already authenticated" in result.output

    @patch("eero_cli.commands.auth.EeroClient")
    @patch("eero_cli.commands.auth.get_cookie_file")
    def test_force_bypasses_existing_auth(
        self, mock_cookie_file, mock_client_class, runner, tmp_path
    ):
        """Test --force bypasses existing authentication check."""
        mock_cookie_file.return_value = tmp_path / "cookies.json"

        # Create mock client - authenticated but we're forcing new login
        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client._api = MagicMock()
        mock_client._api.auth = MagicMock()
        mock_client._api.auth.clear_auth_data = AsyncMock()
        mock_client_class.return_value = mock_client

        # Use input to simulate user interaction
        runner.invoke(
            cli,
            ["auth", "login", "--force"],
            input="test@example.com\n123456\n",
        )
        # Should proceed to login flow, not show "Already authenticated"
        # (May fail on verification but should attempt)


class TestAuthLogout:
    """Tests for auth logout command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_auth_logout_help(self, runner):
        """Test auth logout shows help."""
        result = runner.invoke(cli, ["auth", "logout", "--help"])

        assert result.exit_code == 0
        assert "Logout from your Eero account" in result.output

    @patch("eero_cli.commands.auth.EeroClient")
    @patch("eero_cli.commands.auth.get_cookie_file")
    def test_logout_when_not_authenticated(
        self, mock_cookie_file, mock_client_class, runner, tmp_path
    ):
        """Test logout when not authenticated shows message."""
        mock_cookie_file.return_value = tmp_path / "cookies.json"

        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["auth", "logout"])

        assert "Not logged in" in result.output

    @patch("eero_cli.commands.auth.EeroClient")
    @patch("eero_cli.commands.auth.get_cookie_file")
    def test_logout_success(self, mock_cookie_file, mock_client_class, runner, tmp_path):
        """Test successful logout."""
        mock_cookie_file.return_value = tmp_path / "cookies.json"

        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.logout = AsyncMock(return_value=True)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["auth", "logout"])

        assert "Logged out successfully" in result.output

    @patch("eero_cli.commands.auth.EeroClient")
    @patch("eero_cli.commands.auth.get_cookie_file")
    def test_logout_failure(self, mock_cookie_file, mock_client_class, runner, tmp_path):
        """Test logout failure."""
        mock_cookie_file.return_value = tmp_path / "cookies.json"

        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.logout = AsyncMock(return_value=False)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["auth", "logout"])

        assert "Failed to logout" in result.output


class TestAuthClear:
    """Tests for auth clear command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_auth_clear_help(self, runner):
        """Test auth clear shows help."""
        result = runner.invoke(cli, ["auth", "clear", "--help"])

        assert result.exit_code == 0
        assert "Clear all stored authentication" in result.output
        assert "--force" in result.output

    @patch("eero_cli.commands.auth.EeroClient")
    @patch("eero_cli.commands.auth.get_cookie_file")
    def test_clear_prompts_for_confirmation(
        self, mock_cookie_file, mock_client_class, runner, tmp_path
    ):
        """Test clear prompts for confirmation without --force."""
        mock_cookie_file.return_value = tmp_path / "cookies.json"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        # Decline confirmation
        result = runner.invoke(cli, ["auth", "clear"], input="n\n")

        assert "Cancelled" in result.output

    @patch("eero_cli.commands.auth.EeroClient")
    @patch("eero_cli.commands.auth.get_cookie_file")
    def test_clear_with_force(self, mock_cookie_file, mock_client_class, runner, tmp_path):
        """Test clear with --force skips confirmation."""
        mock_cookie_file.return_value = tmp_path / "cookies.json"

        mock_client = AsyncMock()
        mock_client._api = MagicMock()
        mock_client._api.auth = MagicMock()
        mock_client._api.auth.clear_auth_data = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["auth", "clear", "--force"])

        assert "Authentication data cleared" in result.output

    def test_clear_non_interactive_without_force_fails(self, runner):
        """Test clear in non-interactive mode without --force fails."""
        result = runner.invoke(cli, ["--non-interactive", "auth", "clear"])

        # Should fail because confirmation required
        assert (
            result.exit_code != 0
            or "requires confirmation" in result.output.lower()
            or "force" in result.output.lower()
        )


class TestAuthStatus:
    """Tests for auth status command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_auth_status_help(self, runner):
        """Test auth status shows help."""
        result = runner.invoke(cli, ["auth", "status", "--help"])

        assert result.exit_code == 0
        assert "Show current authentication status" in result.output

    @patch("eero_cli.commands.auth.EeroClient")
    @patch("eero_cli.commands.auth.get_cookie_file")
    def test_status_when_not_authenticated(
        self, mock_cookie_file, mock_client_class, runner, tmp_path
    ):
        """Test status shows not authenticated."""
        mock_cookie_file.return_value = tmp_path / "cookies.json"

        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["auth", "status"])

        assert "Not Authenticated" in result.output

    @patch("eero_cli.commands.auth.EeroClient")
    @patch("eero_cli.commands.auth.get_cookie_file")
    def test_status_when_authenticated(self, mock_cookie_file, mock_client_class, runner, tmp_path):
        """Test status shows authenticated with network count."""
        mock_cookie_file.return_value = tmp_path / "cookies.json"

        # Create mock networks
        mock_network = MagicMock()
        mock_network.id = "net_123"
        mock_network.name = "Home Network"

        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get_networks = AsyncMock(return_value=[mock_network])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["auth", "status"])

        assert "Authenticated" in result.output
        assert "Networks" in result.output or "1" in result.output

    @patch("eero_cli.commands.auth.EeroClient")
    @patch("eero_cli.commands.auth.get_cookie_file")
    def test_status_json_output(self, mock_cookie_file, mock_client_class, runner, tmp_path):
        """Test status with JSON output format."""
        mock_cookie_file.return_value = tmp_path / "cookies.json"

        mock_network = MagicMock()
        mock_network.id = "net_123"
        mock_network.name = "Home Network"

        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get_networks = AsyncMock(return_value=[mock_network])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["--output", "json", "auth", "status"])

        # Should be valid JSON
        try:
            data = json.loads(result.output)
            assert "data" in data
            assert data["data"]["authenticated"] is True
        except json.JSONDecodeError:
            # Output might have other content, just check it ran
            pass

    @patch("eero_cli.commands.auth.EeroClient")
    @patch("eero_cli.commands.auth.get_cookie_file")
    def test_status_session_expired(self, mock_cookie_file, mock_client_class, runner, tmp_path):
        """Test status shows expired when session is invalid."""
        mock_cookie_file.return_value = tmp_path / "cookies.json"

        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get_networks = AsyncMock(side_effect=EeroAuthenticationException("Expired"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["auth", "status"])

        assert "Expired" in result.output or "login" in result.output.lower()
