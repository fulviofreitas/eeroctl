"""Unit tests for `account name|email|phone|consents|push` writes.

Migration plan §4 phase C, `account name set` row. Mocks at the SDK boundary
(`patch("eeroctl.utils.EeroClient", ...)`).
"""

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli

_ACCOUNT_ENVELOPE = {
    "meta": {"code": 200},
    "data": {"name": "John Doe", "consents": {"marketing_emails": False}},
}


def _client(**method_return_values) -> AsyncMock:
    client = AsyncMock()
    for name, value in method_return_values.items():
        setattr(client, name, AsyncMock(return_value=value))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestAccountNameSet:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_sets_name(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_account=_ACCOUNT_ENVELOPE,
            set_account_name={"meta": {"code": 200}, "data": {}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["account", "name", "set", "Jane Doe", "--force"])

        assert result.exit_code == 0
        mock_client.set_account_name.assert_awaited_once_with("Jane Doe")

    def test_skips_write_when_unchanged(self, runner: CliRunner) -> None:
        # --force would also bypass write_if_changed's skip-unchanged
        # short-circuit, so answer the Y/N prompt instead.
        mock_client = _client(get_account=_ACCOUNT_ENVELOPE, set_account_name=AsyncMock())

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["account", "name", "set", "John Doe"], input="y\n")

        assert result.exit_code == 0
        assert "already configured" in result.output.lower()
        mock_client.set_account_name.assert_not_called()

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client(get_account=_ACCOUNT_ENVELOPE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--non-interactive", "account", "name", "set", "Jane Doe"])

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_account_name.assert_not_called()


class TestAccountEmail:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_set_sends_verification_code(self, runner: CliRunner) -> None:
        mock_client = _client(set_account_email={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["account", "email", "set", "jane@example.com", "--force"])

        assert result.exit_code == 0
        mock_client.set_account_email.assert_awaited_once_with("jane@example.com")
        assert "account email verify" in result.output

    def test_verify_confirms_change(self, runner: CliRunner) -> None:
        mock_client = _client(verify_account_email={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["account", "email", "verify", "123456", "--force"])

        assert result.exit_code == 0
        mock_client.verify_account_email.assert_awaited_once_with("123456")

    def test_set_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--non-interactive", "account", "email", "set", "jane@example.com"]
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_account_email.assert_not_called()

    def test_verify_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--non-interactive", "account", "email", "verify", "123456"]
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.verify_account_email.assert_not_called()


class TestAccountPhone:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_set_sends_verification_code(self, runner: CliRunner) -> None:
        mock_client = _client(set_account_phone={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["account", "phone", "set", "+15551234567", "--force"])

        assert result.exit_code == 0
        mock_client.set_account_phone.assert_awaited_once_with("+15551234567")
        assert "account phone verify" in result.output

    def test_verify_confirms_change(self, runner: CliRunner) -> None:
        mock_client = _client(verify_account_phone={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["account", "phone", "verify", "123456", "--force"])

        assert result.exit_code == 0
        mock_client.verify_account_phone.assert_awaited_once_with("123456")

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--non-interactive", "account", "phone", "set", "+15551234567"]
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_account_phone.assert_not_called()


class TestAccountConsents:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_requires_a_direction(self, runner: CliRunner) -> None:
        mock_client = _client(get_account=_ACCOUNT_ENVELOPE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["account", "consents", "--force"])

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.set_account_consents.assert_not_called()

    def test_opts_in(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_account=_ACCOUNT_ENVELOPE,  # marketing_emails: False
            set_account_consents={"meta": {"code": 200}, "data": {}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["account", "consents", "--marketing-emails", "--force"])

        assert result.exit_code == 0
        mock_client.set_account_consents.assert_awaited_once_with(marketing_emails=True)

    def test_skips_write_when_unchanged(self, runner: CliRunner) -> None:
        # --force would also bypass write_if_changed's skip-unchanged
        # short-circuit, so answer the Y/N prompt instead.
        mock_client = _client(
            get_account=_ACCOUNT_ENVELOPE,  # marketing_emails: False
            set_account_consents=AsyncMock(),
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["account", "consents", "--no-marketing-emails"], input="y\n"
            )

        assert result.exit_code == 0
        assert "already configured" in result.output.lower()
        mock_client.set_account_consents.assert_not_called()

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client(get_account=_ACCOUNT_ENVELOPE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--non-interactive", "account", "consents", "--marketing-emails"]
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_account_consents.assert_not_called()


class TestAccountPushSet:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_requires_at_least_one_pair(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["account", "push", "set", "--force"])

        assert result.exit_code == ExitCode.USAGE_ERROR

    def test_invalid_pair_exits_usage_error(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["account", "push", "set", "--set", "not-a-pair", "--force"]
            )

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.set_push_settings.assert_not_called()

    def test_invalid_value_exits_usage_error(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["account", "push", "set", "--set", "digest=maybe", "--force"]
            )

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.set_push_settings.assert_not_called()

    def test_sets_push_settings(self, runner: CliRunner) -> None:
        mock_client = _client(set_push_settings={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "account",
                    "push",
                    "set",
                    "--set",
                    "device_offline=true",
                    "--set",
                    "weekly_digest=0",
                    "--force",
                ],
            )

        assert result.exit_code == 0
        mock_client.set_push_settings.assert_awaited_once_with(
            {"device_offline": True, "weekly_digest": False}
        )

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--non-interactive",
                    "account",
                    "push",
                    "set",
                    "--set",
                    "device_offline=true",
                ],
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_push_settings.assert_not_called()
