"""Unit tests for `troubleshoot diagnostics run` and `network thread set`.

Migration plan §4 phase C row 40. Mocks at the SDK boundary
(`patch("eeroctl.utils.EeroClient", ...)`).
"""

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


class TestDiagnosticsRun:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_runs_diagnostics_with_flags(self, runner: CliRunner) -> None:
        mock_client = _client(run_diagnostics={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "troubleshoot",
                    "diagnostics",
                    "run",
                    "--device",
                    "AA:BB:CC:DD:EE:FF",
                    "--symptom",
                    "no_internet",
                    "--force",
                ],
            )

        assert result.exit_code == 0
        mock_client.run_diagnostics.assert_awaited_once_with(
            None, device="AA:BB:CC:DD:EE:FF", symptom="no_internet"
        )

    def test_no_flags_still_runs(self, runner: CliRunner) -> None:
        """LOW risk: no confirmation prompt, so it just runs."""
        mock_client = _client(run_diagnostics={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["troubleshoot", "diagnostics", "run"])

        assert result.exit_code == 0
        mock_client.run_diagnostics.assert_awaited_once_with(None, device=None, symptom=None)


class TestThreadSet:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_no_flags_exits_usage_error(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "thread", "set", "--force"])

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.update_thread.assert_not_called()
        mock_client.regenerate_thread_credentials.assert_not_called()

    def test_credential_syncing_calls_update_thread(self, runner: CliRunner) -> None:
        mock_client = _client(update_thread={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "thread", "set", "--credential-syncing", "--force"]
            )

        assert result.exit_code == 0
        mock_client.update_thread.assert_awaited_once_with(
            enable_credential_syncing=True, network_id=None
        )
        mock_client.regenerate_thread_credentials.assert_not_called()

    def test_regenerate_calls_regenerate_thread_credentials(self, runner: CliRunner) -> None:
        mock_client = _client(regenerate_thread_credentials={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "thread", "set", "--regenerate", "--force"])

        assert result.exit_code == 0
        mock_client.regenerate_thread_credentials.assert_awaited_once_with(None)
        mock_client.update_thread.assert_not_called()

    def test_both_flags_call_both_methods(self, runner: CliRunner) -> None:
        mock_client = _client(
            update_thread={"meta": {"code": 200}},
            regenerate_thread_credentials={"meta": {"code": 200}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "thread",
                    "set",
                    "--credential-syncing",
                    "--regenerate",
                    "--force",
                ],
            )

        assert result.exit_code == 0
        mock_client.update_thread.assert_awaited_once()
        mock_client.regenerate_thread_credentials.assert_awaited_once()

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["--non-interactive", "network", "thread", "set", "--regenerate"],
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.regenerate_thread_credentials.assert_not_called()
