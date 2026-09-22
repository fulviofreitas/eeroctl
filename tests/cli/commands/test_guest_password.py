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


def _sdk_client(**method_return_values) -> AsyncMock:
    """Build an AsyncMock EeroClient for patching at the SDK boundary.

    Unlike `_mock_client` (patched over `run_with_client`), this one is
    entered as an async context manager by `utils.build_client`, so it needs
    working `__aenter__`/`__aexit__`.
    """
    client = AsyncMock()
    for method_name, return_value in method_return_values.items():
        setattr(client, method_name, AsyncMock(return_value=return_value))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
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

    def test_missing_password_prompt_leaves_stdout_valid_json(self, runner: CliRunner) -> None:
        """The password prompt writes to stderr, so --output json's stdout
        stays parseable (regression: click.prompt without err=True writes
        the prompt text to stdout, ahead of the JSON envelope)."""
        mock_client = _mock_client(set_guest_password=_OK_RESPONSE)

        with patch(
            "eeroctl.commands.network.guest.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(
                cli,
                ["--output", "json", "network", "guest", "password", "set", "--force"],
                input="prompted-secret\nprompted-secret\n",
            )

        assert result.exit_code == 0
        assert '"ok": true' in result.stdout
        assert "prompted-secret" not in result.stdout
        assert "Guest network password" not in result.stdout

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

    def test_non_interactive_with_password_without_force_exits_safety_rail(
        self, runner: CliRunner
    ) -> None:
        """MEDIUM risk still requires confirmation even when --password is
        given: --non-interactive without --force must exit SAFETY_RAIL (8),
        not silently proceed just because the password was supplied.
        """
        mock_client = _sdk_client(set_guest_password=_OK_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
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
                ],
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_guest_password.assert_not_called()

    def test_declining_confirmation_never_prompts_for_password(self, runner: CliRunner) -> None:
        """Declining the Y/N confirmation must not ask for the password at
        all -- confirmation now runs before the password prompt.
        """
        mock_client = _sdk_client(set_guest_password=_OK_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "guest", "password", "set"], input="n\n")

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_guest_password.assert_not_called()

    def test_json_output_reports_ok(self, runner: CliRunner) -> None:
        mock_client = _mock_client(set_guest_password=_OK_RESPONSE)

        with patch(
            "eeroctl.commands.network.guest.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(
                cli,
                [
                    "--output",
                    "json",
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
        assert '"ok": true' in result.output
        assert "eero.network.guest.password.set/v1" in result.output


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

    def test_json_output_reports_ok(self, runner: CliRunner) -> None:
        mock_client = _mock_client(clear_guest_password=_OK_RESPONSE)

        with patch(
            "eeroctl.commands.network.guest.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(
                cli,
                ["--output", "json", "network", "guest", "password", "clear", "--force"],
            )

        assert result.exit_code == 0
        assert '"ok": true' in result.output
        assert "eero.network.guest.password.clear/v1" in result.output

    def test_falsy_response_exits_nonzero(self, runner: CliRunner) -> None:
        """An empty/falsy response (no meta.code, no truthy body) is a failure."""
        mock_client = _mock_client(clear_guest_password=None)

        with patch(
            "eeroctl.commands.network.guest.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(cli, ["network", "guest", "password", "clear", "--force"])

        assert result.exit_code != 0

    def test_interactive_yes_confirms_and_writes(self, runner: CliRunner) -> None:
        """MEDIUM risk without --force prompts Y/N; 'y' proceeds to the write."""
        mock_client = _sdk_client(clear_guest_password=_OK_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "guest", "password", "clear"], input="y\n")

        assert result.exit_code == 0
        mock_client.clear_guest_password.assert_awaited_once()

    def test_interactive_no_declines_and_exits_safety_rail(self, runner: CliRunner) -> None:
        """MEDIUM risk without --force prompts Y/N; 'n' is a safety-rail failure."""
        mock_client = _sdk_client(clear_guest_password=_OK_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "guest", "password", "clear"], input="n\n")

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.clear_guest_password.assert_not_called()
