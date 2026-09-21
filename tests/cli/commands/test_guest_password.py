"""Unit tests for `eero network guest password set` and `... clear`.

Migration plan §4 phase B row 26: `set_guest_password`/`clear_guest_password`
are on the SDK's live-verified allowlist (MEDIUM risk, VERIFIED,
"disconnects guest clients"). Covers:

- happy path for set and clear
- password provided via --password never appears in stdout/stderr
- password omitted -> interactive prompt (hidden, confirmed)
- --non-interactive without --password exits 2 (USAGE_ERROR)
- --force skips the Y/N confirmation
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli

_OK_RESPONSE = {"meta": {"code": 200, "error": None}, "data": {}}


def _make_run_with_client(mock_client: MagicMock):
    async def _run(func):
        await func(mock_client)

    return _run


def _mock_client(**method_return_values) -> MagicMock:
    client = MagicMock()
    for method_name, return_value in method_return_values.items():
        setattr(client, method_name, AsyncMock(return_value=return_value))
    return client


class TestGuestPasswordGroup:
    """Tests for the `network guest password` command group."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["network", "guest", "password", "--help"])

        assert result.exit_code == 0
        assert "set" in result.output
        assert "clear" in result.output


class TestGuestPasswordSet:
    """Tests for `network guest password set`."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["network", "guest", "password", "set", "--help"])

        assert result.exit_code == 0
        assert "--password" in result.output

    def test_password_flag_calls_set_guest_password(self, runner: CliRunner) -> None:
        mock_client = _mock_client(set_guest_password=_OK_RESPONSE)

        with patch(
            "eeroctl.commands.network.guest.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(
                cli,
                ["network", "guest", "password", "set", "--password", "hunter2", "--force"],
            )

        assert result.exit_code == 0
        mock_client.set_guest_password.assert_awaited_once()
        call_args = mock_client.set_guest_password.call_args
        assert call_args[0][0] == "hunter2"

    def test_password_never_echoed(self, runner: CliRunner) -> None:
        mock_client = _mock_client(set_guest_password=_OK_RESPONSE)

        with patch(
            "eeroctl.commands.network.guest.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(
                cli,
                ["network", "guest", "password", "set", "--password", "super-secret", "--force"],
            )

        assert "super-secret" not in result.output

    def test_missing_password_prompts_hidden_and_confirmed(self, runner: CliRunner) -> None:
        """No --password: prompts for it, hidden and confirmed, never echoed."""
        mock_client = _mock_client(set_guest_password=_OK_RESPONSE)

        with patch(
            "eeroctl.commands.network.guest.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(
                cli,
                ["network", "guest", "password", "set", "--force"],
                input="prompted-secret\nprompted-secret\n",
            )

        assert result.exit_code == 0
        mock_client.set_guest_password.assert_awaited_once()
        call_args = mock_client.set_guest_password.call_args
        assert call_args[0][0] == "prompted-secret"
        assert "prompted-secret" not in result.output

    def test_non_interactive_without_password_exits_usage_error(self, runner: CliRunner) -> None:
        mock_client = _mock_client(set_guest_password=_OK_RESPONSE)

        with patch(
            "eeroctl.commands.network.guest.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(
                cli,
                ["--non-interactive", "network", "guest", "password", "set"],
            )

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.set_guest_password.assert_not_called()

    def test_non_interactive_with_password_still_writes(self, runner: CliRunner) -> None:
        mock_client = _mock_client(set_guest_password=_OK_RESPONSE)

        with patch(
            "eeroctl.commands.network.guest.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(
                cli,
                [
                    "--non-interactive",
                    "network",
                    "guest",
                    "password",
                    "set",
                    "--password",
                    "hunter2",
                    "--force",
                ],
            )

        assert result.exit_code == 0
        mock_client.set_guest_password.assert_awaited_once()

    def test_falsy_response_exits_nonzero(self, runner: CliRunner) -> None:
        """An empty/falsy response (no meta.code, no truthy body) is a failure."""
        mock_client = _mock_client(set_guest_password=None)

        with patch(
            "eeroctl.commands.network.guest.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(
                cli,
                ["network", "guest", "password", "set", "--password", "hunter2", "--force"],
            )

        assert result.exit_code != 0


class TestGuestPasswordClear:
    """Tests for `network guest password clear`."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["network", "guest", "password", "clear", "--help"])

        assert result.exit_code == 0
        assert "Clear the guest network" in result.output

    def test_clear_calls_clear_guest_password(self, runner: CliRunner) -> None:
        mock_client = _mock_client(clear_guest_password=_OK_RESPONSE)

        with patch(
            "eeroctl.commands.network.guest.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(cli, ["network", "guest", "password", "clear", "--force"])

        assert result.exit_code == 0
        mock_client.clear_guest_password.assert_awaited_once()

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _mock_client(clear_guest_password=_OK_RESPONSE)

        with patch(
            "eeroctl.commands.network.guest.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(
                cli, ["--non-interactive", "network", "guest", "password", "clear"]
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.clear_guest_password.assert_not_called()

    def test_falsy_response_exits_nonzero(self, runner: CliRunner) -> None:
        """An empty/falsy response (no meta.code, no truthy body) is a failure."""
        mock_client = _mock_client(clear_guest_password=None)

        with patch(
            "eeroctl.commands.network.guest.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(cli, ["network", "guest", "password", "clear", "--force"])

        assert result.exit_code != 0
