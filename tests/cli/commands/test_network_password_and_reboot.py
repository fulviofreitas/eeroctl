"""Unit tests for `network password set|clear` and `network reboot`.

Migration plan §4 phase C row 39 -- both HIGH risk with a typed phrase.
Mocks at the SDK boundary (`patch("eeroctl.utils.EeroClient", ...)`).
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli


def _client(**method_return_values) -> AsyncMock:
    client = AsyncMock()
    for name, value in method_return_values.items():
        setattr(client, name, AsyncMock(return_value=value))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestPasswordSet:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_password_flag_requires_disconnect_phrase(self, runner: CliRunner) -> None:
        mock_client = _client(set_network_password={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["network", "password", "set", "--password", "hunter2"],
                input="DISCONNECT\n",
            )

        assert result.exit_code == 0
        mock_client.set_network_password.assert_awaited_once_with("hunter2", None)

    def test_password_never_echoed(self, runner: CliRunner) -> None:
        mock_client = _client(set_network_password={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["--force", "network", "password", "set", "--password", "super-secret"],
            )

        assert "super-secret" not in result.output

    def test_missing_password_prompts_hidden(self, runner: CliRunner) -> None:
        mock_client = _client(set_network_password={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["--force", "network", "password", "set"],
                input="prompted-secret\nprompted-secret\n",
            )

        assert result.exit_code == 0
        mock_client.set_network_password.assert_awaited_once_with("prompted-secret", None)
        assert "prompted-secret" not in result.output

    def test_missing_password_prompt_leaves_stdout_empty_or_valid_json(
        self, runner: CliRunner
    ) -> None:
        """The password prompt writes to stderr, so --output json's stdout
        stays parseable (regression: click.prompt without err=True writes
        the prompt text to stdout, ahead of the JSON envelope)."""
        mock_client = _client(set_network_password={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["--output", "json", "--force", "network", "password", "set"],
                input="prompted-secret\nprompted-secret\n",
            )

        assert result.exit_code == 0
        # getpass's non-tty fallback (exercised under CliRunner, not a real
        # terminal) echoes the prompt suffix's last character to stdout via
        # the builtin input(); that pre-existing artifact is whitespace-only
        # and unrelated to this fix, so strip it before validating.
        stdout = result.stdout.strip()
        assert stdout == "" or json.loads(stdout)
        assert "prompted-secret" not in result.stdout
        assert "Network password" not in result.stdout

    def test_non_interactive_without_password_exits_usage_error(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--non-interactive", "network", "password", "set"])

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.set_network_password.assert_not_called()

    def test_wrong_phrase_is_safety_rail(self, runner: CliRunner) -> None:
        mock_client = _client(set_network_password={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["network", "password", "set", "--password", "hunter2"],
                input="nope\n",
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_network_password.assert_not_called()


class TestPasswordClear:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_clear_requires_disconnect_phrase(self, runner: CliRunner) -> None:
        mock_client = _client(clear_network_password={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "password", "clear"], input="DISCONNECT\n")

        assert result.exit_code == 0
        mock_client.clear_network_password.assert_awaited_once_with(None)

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--non-interactive", "network", "password", "clear"])

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.clear_network_password.assert_not_called()


class TestNetworkReboot:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_requires_reboot_phrase(self, runner: CliRunner) -> None:
        mock_client = _client(reboot_network={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "reboot"], input="REBOOT\n")

        assert result.exit_code == 0
        assert "Network reboot initiated" in result.output
        # No envelope pre-fetch any more: the 8.4.0 facade resolves the
        # reboot link itself, and None lets it pick the preferred network.
        mock_client.get_network.assert_not_called()
        mock_client.reboot_network.assert_awaited_once_with(None)

    def test_forwards_explicit_network_id(self, runner: CliRunner) -> None:
        mock_client = _client(reboot_network={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "reboot", "--network-id", "net1", "--force"])

        assert result.exit_code == 0
        mock_client.reboot_network.assert_awaited_once_with("net1")

    def test_empty_envelope_is_a_failure(self, runner: CliRunner) -> None:
        mock_client = _client(reboot_network={})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "reboot", "--force"])

        assert result.exit_code == ExitCode.GENERIC_ERROR
        assert "Failed to reboot network" in result.output

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--non-interactive", "network", "reboot"])

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.reboot_network.assert_not_called()
