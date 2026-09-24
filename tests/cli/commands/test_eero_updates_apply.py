"""Unit tests for `eero updates apply`.

Migration plan §4 phase C row 38: HIGH, phrase REBOOT, no read-first.
Mocks at the SDK boundary (`patch("eeroctl.utils.EeroClient", ...)`).
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


class TestUpdatesApply:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["eero", "updates", "apply", "--help"])

        assert result.exit_code == 0

    def test_requires_reboot_phrase(self, runner: CliRunner) -> None:
        mock_client = _client(apply_update={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["eero", "updates", "apply"], input="REBOOT\n")

        assert result.exit_code == 0
        mock_client.apply_update.assert_awaited_once_with(None)

    def test_wrong_phrase_is_safety_rail(self, runner: CliRunner) -> None:
        mock_client = _client(apply_update={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["eero", "updates", "apply"], input="nope\n")

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.apply_update.assert_not_called()

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--non-interactive", "eero", "updates", "apply"])

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.apply_update.assert_not_called()

    def test_force_still_writes(self, runner: CliRunner) -> None:
        mock_client = _client(apply_update={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--force", "eero", "updates", "apply"])

        assert result.exit_code == 0
        mock_client.apply_update.assert_awaited_once_with(None)
