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

from eeroctl.const import KEYRING_ACCOUNT_NAME, KEYRING_SERVICE_NAME
from eeroctl.main import cli


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

    @patch("eeroctl.commands.auth.build_client")
    @patch("eeroctl.commands.auth.get_cookie_file")
    def test_already_authenticated_shows_message(
        self, mock_cookie_file, mock_build_client, runner, tmp_path
    ):
        """Test shows message when already authenticated."""
        mock_cookie_file.return_value = tmp_path / "cookies.json"

        # Create mock client
        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_build_client.return_value = mock_client

        result = runner.invoke(cli, ["auth", "login"])

        assert "Already authenticated" in result.output

    @patch("eeroctl.commands.auth.build_client")
    @patch("eeroctl.commands.auth.get_cookie_file")
    def test_force_bypasses_existing_auth(
        self, mock_cookie_file, mock_build_client, runner, tmp_path
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
        mock_build_client.return_value = mock_client

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

    @patch("eeroctl.commands.auth.build_client")
    @patch("eeroctl.commands.auth.get_cookie_file")
    def test_logout_when_not_authenticated(
        self, mock_cookie_file, mock_build_client, runner, tmp_path
    ):
        """Test logout when not authenticated shows message."""
        mock_cookie_file.return_value = tmp_path / "cookies.json"

        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_build_client.return_value = mock_client

        result = runner.invoke(cli, ["auth", "logout"])

        assert "Not logged in" in result.output

    @patch("eeroctl.commands.auth.build_client")
    @patch("eeroctl.commands.auth.get_cookie_file")
    def test_logout_success(self, mock_cookie_file, mock_build_client, runner, tmp_path):
        """Test successful logout."""
        mock_cookie_file.return_value = tmp_path / "cookies.json"

        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.logout = AsyncMock(return_value=True)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_build_client.return_value = mock_client

        result = runner.invoke(cli, ["auth", "logout"])

        assert "Logged out successfully" in result.output

    @patch("eeroctl.commands.auth.build_client")
    @patch("eeroctl.commands.auth.get_cookie_file")
    def test_logout_failure(self, mock_cookie_file, mock_build_client, runner, tmp_path):
        """Test logout failure."""
        mock_cookie_file.return_value = tmp_path / "cookies.json"

        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.logout = AsyncMock(return_value=False)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_build_client.return_value = mock_client

        result = runner.invoke(cli, ["auth", "logout"])

        assert "Failed to logout" in result.output

    @patch("eeroctl.commands.auth.build_client")
    def test_logout_validation_exception_maps_to_exit_2(self, mock_build_client, runner):
        """A construction-time EeroValidationException (e.g. a bad
        EEROCTL_ACCEPT_LANGUAGE) exits 2, not an unhandled traceback."""
        from eero.exceptions import EeroValidationException

        mock_build_client.side_effect = EeroValidationException(
            "accept_language", "must be printable ASCII"
        )

        result = runner.invoke(cli, ["auth", "logout"])

        assert result.exit_code == 2


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

    @patch("eeroctl.commands.auth.build_client")
    @patch("eeroctl.commands.auth.get_cookie_file")
    def test_clear_prompts_for_confirmation(
        self, mock_cookie_file, mock_build_client, runner, tmp_path
    ):
        """Test clear prompts for confirmation without --force."""
        mock_cookie_file.return_value = tmp_path / "cookies.json"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_build_client.return_value = mock_client

        # Decline confirmation
        result = runner.invoke(cli, ["auth", "clear"], input="n\n")

        assert "Cancelled" in result.output

    @patch("eeroctl.commands.auth.build_client")
    @patch("eeroctl.commands.auth.get_cookie_file")
    def test_clear_with_force(self, mock_cookie_file, mock_build_client, runner, tmp_path):
        """Test clear with --force skips confirmation."""
        mock_cookie_file.return_value = tmp_path / "cookies.json"

        mock_client = AsyncMock()
        mock_client._api = MagicMock()
        mock_client._api.auth = MagicMock()
        mock_client._api.auth.clear_auth_data = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_build_client.return_value = mock_client

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

    @patch("eeroctl.commands.auth.build_client")
    def test_clear_validation_exception_maps_to_exit_2(self, mock_build_client, runner):
        """A construction-time EeroValidationException (e.g. a bad
        EEROCTL_ACCEPT_LANGUAGE) exits 2, not an unhandled traceback."""
        from eero.exceptions import EeroValidationException

        mock_build_client.side_effect = EeroValidationException(
            "accept_language", "must be printable ASCII"
        )

        result = runner.invoke(cli, ["auth", "clear", "--force"])

        assert result.exit_code == 2


class TestAuthStatus:
    """Tests for auth status command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    @staticmethod
    def _session_info(tmp_path, *, present=True, schema_version=2):
        return {
            "path": str(tmp_path / "cookies.json"),
            "present": present,
            "schema_version": schema_version,
        }

    @staticmethod
    def _account_response():
        return {
            "meta": {"code": 200},
            "data": {
                "url": "/2.2/accounts/account_123",
                "id": "account_123",
                "name": "Test Account",
                "premium_status": "active",
                "premium_expiry": None,
                "created_at": None,
                "users": [
                    {
                        "id": "user_123",
                        "name": "Test User",
                        "email": "test@example.com",
                        "phone": None,
                        "role": "owner",
                        "created_at": None,
                    }
                ],
            },
        }

    def test_auth_status_help(self, runner):
        """Test auth status shows help."""
        result = runner.invoke(cli, ["auth", "status", "--help"])

        assert result.exit_code == 0
        assert "Show current authentication status" in result.output
        assert "--offline" in result.output
        assert "--check" in result.output

    @patch("eeroctl.commands.auth._get_session_info")
    @patch("eeroctl.commands.auth._check_keyring_available")
    @patch("eeroctl.commands.auth.build_client")
    def test_status_when_not_authenticated(
        self, mock_build_client, mock_keyring, mock_session_info, runner, tmp_path
    ):
        """Test status shows not authenticated."""
        mock_keyring.return_value = False
        mock_session_info.return_value = self._session_info(
            tmp_path, present=False, schema_version=None
        )

        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_build_client.return_value = mock_client

        result = runner.invoke(cli, ["auth", "status"])

        assert "Not authenticated" in result.output

    @patch("eeroctl.commands.auth._get_session_info")
    @patch("eeroctl.commands.auth._check_keyring_available")
    @patch("eeroctl.commands.auth.build_client")
    def test_status_not_authenticated_check_exits_auth_required(
        self, mock_build_client, mock_keyring, mock_session_info, runner, tmp_path
    ):
        """--check exits 3 when there is no stored token at all."""
        mock_keyring.return_value = False
        mock_session_info.return_value = self._session_info(
            tmp_path, present=False, schema_version=None
        )

        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_build_client.return_value = mock_client

        result = runner.invoke(cli, ["auth", "status", "--check"])

        assert result.exit_code == 3

    @patch("eeroctl.commands.auth._get_session_info")
    @patch("eeroctl.commands.auth._check_keyring_available")
    @patch("eeroctl.commands.auth.build_client")
    def test_status_when_authenticated(
        self, mock_build_client, mock_keyring, mock_session_info, runner, tmp_path
    ):
        """Test status shows authenticated with account info when the live probe succeeds."""
        mock_keyring.return_value = False
        mock_session_info.return_value = self._session_info(tmp_path)

        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get_account = AsyncMock(return_value=self._account_response())
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_build_client.return_value = mock_client

        result = runner.invoke(cli, ["auth", "status"])

        # Check for session and account info
        assert "Valid" in result.output or "valid" in result.output
        assert "Account" in result.output or "account_123" in result.output
        mock_client.get_account.assert_awaited_once()

    @patch("eeroctl.commands.auth._get_session_info")
    @patch("eeroctl.commands.auth._check_keyring_available")
    @patch("eeroctl.commands.auth.build_client")
    def test_status_invalid_session_shows_invalid(
        self, mock_build_client, mock_keyring, mock_session_info, runner, tmp_path
    ):
        """A stored token that the live probe rejects renders as Invalid, not a crash."""
        mock_keyring.return_value = False
        mock_session_info.return_value = self._session_info(tmp_path)

        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get_account = AsyncMock(side_effect=EeroAuthenticationException("expired"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_build_client.return_value = mock_client

        result = runner.invoke(cli, ["auth", "status"])

        assert result.exit_code == 0
        assert "Invalid" in result.output

    @patch("eeroctl.commands.auth._get_session_info")
    @patch("eeroctl.commands.auth._check_keyring_available")
    @patch("eeroctl.commands.auth.build_client")
    def test_status_invalid_session_check_exits_auth_required(
        self, mock_build_client, mock_keyring, mock_session_info, runner, tmp_path
    ):
        """--check exits 3 when the stored token is present but the probe rejects it."""
        mock_keyring.return_value = False
        mock_session_info.return_value = self._session_info(tmp_path)

        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get_account = AsyncMock(side_effect=EeroAuthenticationException("expired"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_build_client.return_value = mock_client

        result = runner.invoke(cli, ["auth", "status", "--check"])

        assert result.exit_code == 3

    @patch("eeroctl.commands.auth._get_session_info")
    @patch("eeroctl.commands.auth._check_keyring_available")
    @patch("eeroctl.commands.auth.build_client")
    def test_status_offline_skips_the_live_probe(
        self, mock_build_client, mock_keyring, mock_session_info, runner, tmp_path
    ):
        """--offline makes no get_account() call and reports 'Stored, not verified'."""
        mock_keyring.return_value = False
        mock_session_info.return_value = self._session_info(tmp_path)

        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get_account = AsyncMock(return_value=self._account_response())
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_build_client.return_value = mock_client

        result = runner.invoke(cli, ["auth", "status", "--offline"])

        mock_client.get_account.assert_not_awaited()
        assert "Stored, not verified" in result.output

    @patch("eeroctl.commands.auth._get_session_info")
    @patch("eeroctl.commands.auth._check_keyring_available")
    @patch("eeroctl.commands.auth.build_client")
    def test_status_offline_check_does_not_fail(
        self, mock_build_client, mock_keyring, mock_session_info, runner, tmp_path
    ):
        """--check with --offline does not exit 3: an unverified token is not a failure."""
        mock_keyring.return_value = False
        mock_session_info.return_value = self._session_info(tmp_path)

        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_build_client.return_value = mock_client

        result = runner.invoke(cli, ["auth", "status", "--offline", "--check"])

        assert result.exit_code == 0

    @patch("eeroctl.commands.auth.get_auth_method")
    @patch("eeroctl.commands.auth._get_session_info")
    @patch("eeroctl.commands.auth._check_keyring_available")
    @patch("eeroctl.commands.auth.build_client")
    def test_status_json_output(
        self, mock_build_client, mock_keyring, mock_session_info, mock_auth_method, runner, tmp_path
    ):
        """Test status with JSON output format uses the eero.auth.status/v2 schema."""
        mock_keyring.return_value = True
        mock_auth_method.return_value = "keyring"
        mock_session_info.return_value = self._session_info(tmp_path)

        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get_account = AsyncMock(return_value=self._account_response())
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_build_client.return_value = mock_client

        result = runner.invoke(cli, ["--output", "json", "auth", "status"])

        data = json.loads(result.output)
        assert data["schema"] == "eero.auth.status/v2"
        assert data["data"]["authenticated"] is True
        assert data["data"]["session_valid"] is True
        assert data["data"]["auth_method"] == "keyring"
        assert data["data"]["storage"]["keyring"]["present"] is True
        assert data["data"]["storage"]["cookie_file"]["present"] is True
        assert data["data"]["storage"]["cookie_file"]["schema_version"] == 2
        assert data["data"]["account"]["id"] == "account_123"
        assert "session_expiry" not in json.dumps(data)

    @patch("eeroctl.commands.auth.get_auth_method")
    @patch("eeroctl.commands.auth._get_session_info")
    @patch("eeroctl.commands.auth._check_keyring_available")
    @patch("eeroctl.commands.auth.build_client")
    def test_status_auth_method_is_cookie_file_verbatim(
        self, mock_build_client, mock_keyring, mock_session_info, mock_auth_method, runner, tmp_path
    ):
        """auth_method is the configured value ("cookie_file"), not "cookie"."""
        mock_keyring.return_value = False
        mock_auth_method.return_value = "cookie_file"
        mock_session_info.return_value = self._session_info(tmp_path)

        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get_account = AsyncMock(return_value=self._account_response())
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_build_client.return_value = mock_client

        result = runner.invoke(cli, ["--output", "json", "auth", "status"])

        data = json.loads(result.output)
        assert data["data"]["auth_method"] == "cookie_file"

    @patch("eeroctl.commands.auth.get_auth_method")
    @patch("eeroctl.commands.auth._get_session_info")
    @patch("eeroctl.commands.auth._check_keyring_available")
    @patch("eeroctl.commands.auth.build_client")
    def test_status_auth_method_independent_of_keyring_probe(
        self, mock_build_client, mock_keyring, mock_session_info, mock_auth_method, runner, tmp_path
    ):
        """auth_method reflects the *configured* method even when the keyring
        probe finds no record there: that fact lives in storage.keyring.present."""
        mock_keyring.return_value = False  # no record found in the keyring
        mock_auth_method.return_value = "keyring"  # but keyring IS the configured method
        mock_session_info.return_value = self._session_info(tmp_path)

        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get_account = AsyncMock(return_value=self._account_response())
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_build_client.return_value = mock_client

        result = runner.invoke(cli, ["--output", "json", "auth", "status"])

        data = json.loads(result.output)
        assert data["data"]["auth_method"] == "keyring"
        assert data["data"]["storage"]["keyring"]["present"] is False

    @patch("eeroctl.commands.auth.get_auth_method")
    @patch("eeroctl.commands.auth._get_session_info")
    @patch("eeroctl.commands.auth._check_keyring_available")
    @patch("eeroctl.commands.auth.build_client")
    def test_status_list_output_auth_method(
        self, mock_build_client, mock_keyring, mock_session_info, mock_auth_method, runner, tmp_path
    ):
        """--output list prints the same configured auth_method value."""
        mock_keyring.return_value = True
        mock_auth_method.return_value = "cookie_file"
        mock_session_info.return_value = self._session_info(tmp_path)

        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get_account = AsyncMock(return_value=self._account_response())
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_build_client.return_value = mock_client

        result = runner.invoke(cli, ["--output", "list", "auth", "status"])

        assert "auth_method         cookie_file" in result.output

    @patch("eeroctl.commands.auth.get_auth_method")
    @patch("eeroctl.commands.auth._get_session_info")
    @patch("eeroctl.commands.auth._check_keyring_available")
    @patch("eeroctl.commands.auth.build_client")
    def test_status_table_output_auth_method(
        self, mock_build_client, mock_keyring, mock_session_info, mock_auth_method, runner, tmp_path
    ):
        """The table's Auth Method row shows the configured method verbatim."""
        mock_keyring.return_value = True
        mock_auth_method.return_value = "cookie_file"
        mock_session_info.return_value = self._session_info(tmp_path)

        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get_account = AsyncMock(return_value=self._account_response())
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_build_client.return_value = mock_client

        result = runner.invoke(cli, ["auth", "status"])

        assert "cookie_file" in result.output

    @patch("eeroctl.commands.auth._get_session_info")
    @patch("eeroctl.commands.auth._check_keyring_available")
    @patch("eeroctl.commands.auth.build_client")
    def test_status_list_output_has_schema_version_not_session_expiry(
        self, mock_build_client, mock_keyring, mock_session_info, runner, tmp_path
    ):
        """list format drops session_expiry and adds schema_version."""
        mock_keyring.return_value = False
        mock_session_info.return_value = self._session_info(tmp_path, schema_version=2)

        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get_account = AsyncMock(return_value=self._account_response())
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_build_client.return_value = mock_client

        result = runner.invoke(cli, ["--output", "list", "auth", "status"])

        assert "session_expiry" not in result.output
        assert "schema_version      2" in result.output

    @patch("eeroctl.commands.auth._check_keyring_available")
    @patch("eeroctl.commands.auth.build_client")
    def test_status_reports_schema1_cookie_file(
        self, mock_build_client, mock_keyring, runner, schema1_cookie_file, monkeypatch
    ):
        """A legacy (schema 1) cookie file reports schema_version None."""
        monkeypatch.setattr("eeroctl.commands.auth.get_cookie_file", lambda: schema1_cookie_file)
        mock_keyring.return_value = False

        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get_account = AsyncMock(return_value=self._account_response())
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_build_client.return_value = mock_client

        result = runner.invoke(cli, ["--output", "list", "auth", "status"])

        assert "schema_version      N/A" in result.output

    @patch("eeroctl.commands.auth._check_keyring_available")
    @patch("eeroctl.commands.auth.build_client")
    def test_status_reports_schema2_cookie_file(
        self, mock_build_client, mock_keyring, runner, schema2_cookie_file, monkeypatch
    ):
        """A current (schema 2) cookie file reports schema_version 2."""
        monkeypatch.setattr("eeroctl.commands.auth.get_cookie_file", lambda: schema2_cookie_file)
        mock_keyring.return_value = False

        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get_account = AsyncMock(return_value=self._account_response())
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_build_client.return_value = mock_client

        result = runner.invoke(cli, ["--output", "list", "auth", "status"])

        assert "schema_version      2" in result.output


class TestCheckKeyringAvailable:
    """Tests for _check_keyring_available, the keyring probe helper."""

    def test_probes_using_the_sdk_constants(self, monkeypatch):
        """The probe must use eeroctl.const.KEYRING_*, not a hardcoded literal."""
        from eeroctl.commands import auth as auth_module

        calls = []

        class _FakeKeyring:
            @staticmethod
            def get_password(service, account):
                calls.append((service, account))
                return "a-token"

        monkeypatch.setitem(__import__("sys").modules, "keyring", _FakeKeyring())

        assert auth_module._check_keyring_available() is True
        assert calls == [(KEYRING_SERVICE_NAME, KEYRING_ACCOUNT_NAME)]

    def test_returns_false_when_no_token_stored(self, monkeypatch):
        from eeroctl.commands import auth as auth_module

        class _FakeKeyring:
            @staticmethod
            def get_password(service, account):
                return None

        monkeypatch.setitem(__import__("sys").modules, "keyring", _FakeKeyring())

        assert auth_module._check_keyring_available() is False


class TestSessionTokenOverride:
    """Tests for EEROCTL_SESSION_TOKEN (v8 migration plan §3.4, Q6)."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_login_refuses_when_session_token_set(self, runner, monkeypatch):
        monkeypatch.setenv("EEROCTL_SESSION_TOKEN", "a-token")

        result = runner.invoke(cli, ["auth", "login"])

        assert result.exit_code == 2
        normalized = " ".join(result.output.split())
        assert "session comes from EEROCTL_SESSION_TOKEN" in normalized
        assert "unset it to manage stored credentials" in normalized

    def test_logout_refuses_when_session_token_set(self, runner, monkeypatch):
        monkeypatch.setenv("EEROCTL_SESSION_TOKEN", "a-token")

        result = runner.invoke(cli, ["auth", "logout"])

        assert result.exit_code == 2
        normalized = " ".join(result.output.split())
        assert "session comes from EEROCTL_SESSION_TOKEN" in normalized
        assert "unset it to manage stored credentials" in normalized

    def test_clear_refuses_when_session_token_set(self, runner, monkeypatch):
        monkeypatch.setenv("EEROCTL_SESSION_TOKEN", "a-token")

        result = runner.invoke(cli, ["auth", "clear", "--force"])

        assert result.exit_code == 2
        normalized = " ".join(result.output.split())
        assert "session comes from EEROCTL_SESSION_TOKEN" in normalized
        assert "unset it to manage stored credentials" in normalized

    @patch("eeroctl.commands.auth._check_keyring_available")
    @patch("eeroctl.commands.auth.build_client")
    def test_status_reports_env_auth_method(
        self, mock_build_client, mock_keyring, runner, monkeypatch
    ):
        """auth status reports auth_method: env, no cookie file, no keyring probe."""
        monkeypatch.setenv("EEROCTL_SESSION_TOKEN", "a-token")

        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get_account = AsyncMock(return_value=TestAuthStatus._account_response())
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_build_client.return_value = mock_client

        result = runner.invoke(cli, ["--output", "json", "auth", "status"])

        data = json.loads(result.output)
        assert data["schema"] == "eero.auth.status/v2"
        assert data["data"]["auth_method"] == "env"
        assert data["data"]["storage"]["cookie_file"]["present"] is False
        assert data["data"]["storage"]["keyring"]["present"] is False
        mock_client.set_session_token.assert_awaited_once_with("a-token")
        mock_keyring.assert_not_called()

    @patch("eeroctl.commands.auth.build_client")
    def test_status_debug_never_echoes_the_token(self, mock_build_client, runner, monkeypatch):
        """The token value never appears in stdout or stderr, even under --debug."""
        monkeypatch.setenv("EEROCTL_SESSION_TOKEN", "super-secret-value")

        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get_account = AsyncMock(return_value=TestAuthStatus._account_response())
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_build_client.return_value = mock_client

        result = runner.invoke(cli, ["--debug", "auth", "status"])

        assert "super-secret-value" not in result.stdout
        assert "super-secret-value" not in result.stderr

    @patch("eeroctl.commands.auth.build_client")
    def test_status_invalid_token_maps_to_exit_2(self, mock_build_client, runner, monkeypatch):
        """A malformed EEROCTL_SESSION_TOKEN (EeroValidationException) exits 2."""
        from eero.exceptions import EeroValidationException

        monkeypatch.setenv("EEROCTL_SESSION_TOKEN", "bad\r\nvalue")

        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.set_session_token = AsyncMock(
            side_effect=EeroValidationException("token", "must be printable ASCII")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_build_client.return_value = mock_client

        result = runner.invoke(cli, ["auth", "status"])

        assert result.exit_code == 2
