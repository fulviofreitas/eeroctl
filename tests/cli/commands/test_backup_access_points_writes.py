"""Unit tests for `network backup access-points add|update|delete|rearrange`,
`discover --start`, and `check`.

Migration plan §4 phase C row 45 (#50). Mocks at the SDK boundary
(`patch("eeroctl.utils.EeroClient", ...)`).
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


class TestBackupAccessPointsAdd:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_adds_with_password_flag(self, runner: CliRunner) -> None:
        mock_client = _client(add_backup_access_point={"meta": {"code": 201}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "backup",
                    "access-points",
                    "add",
                    "--ssid",
                    "Guest",
                    "--password",
                    "hunter22",
                    "--force",
                ],
            )

        assert result.exit_code == 0
        mock_client.add_backup_access_point.assert_awaited_once_with(
            None, ssid="Guest", password="hunter22", uuid=None
        )
        assert "hunter22" not in result.output

    def test_non_interactive_without_password_exits_usage_error(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--non-interactive",
                    "network",
                    "backup",
                    "access-points",
                    "add",
                    "--ssid",
                    "Guest",
                ],
            )

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.add_backup_access_point.assert_not_called()

    def test_password_prompt_hidden_and_confirmed(self, runner: CliRunner) -> None:
        mock_client = _client(add_backup_access_point={"meta": {"code": 201}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["network", "backup", "access-points", "add", "--ssid", "Guest", "--force"],
                input="hunter22\nhunter22\n",
            )

        assert result.exit_code == 0
        mock_client.add_backup_access_point.assert_awaited_once_with(
            None, ssid="Guest", password="hunter22", uuid=None
        )
        assert "hunter22" not in result.output

    def test_password_prompt_leaves_stdout_empty_or_valid_json(self, runner: CliRunner) -> None:
        """The password prompt writes to stderr, so --output json's stdout
        stays parseable (regression: click.prompt without err=True writes
        the prompt text to stdout, ahead of the JSON envelope)."""
        mock_client = _client(add_backup_access_point={"meta": {"code": 201}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--output",
                    "json",
                    "network",
                    "backup",
                    "access-points",
                    "add",
                    "--ssid",
                    "Guest",
                    "--force",
                ],
                input="hunter22\nhunter22\n",
            )

        assert result.exit_code == 0
        # getpass's non-tty fallback (exercised under CliRunner, not a real
        # terminal) echoes the prompt suffix's last character to stdout via
        # the builtin input(); that pre-existing artifact is whitespace-only
        # and unrelated to this fix, so strip it before validating.
        stdout = result.stdout.strip()
        assert stdout == "" or json.loads(stdout)
        assert "hunter22" not in result.stdout
        assert "Backup access point password" not in result.stdout


class TestBackupAccessPointsUpdate:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_no_fields_exits_usage_error(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "backup", "access-points", "update", "bap1"])

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.update_backup_access_point.assert_not_called()

    def test_updates_ssid(self, runner: CliRunner) -> None:
        mock_client = _client(update_backup_access_point={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "backup",
                    "access-points",
                    "update",
                    "bap1",
                    "--ssid",
                    "NewName",
                    "--force",
                ],
            )

        assert result.exit_code == 0
        mock_client.update_backup_access_point.assert_awaited_once_with(
            "bap1",
            None,
            ssid="NewName",
            password=None,
            enabled=None,
            uuid=None,
            connectivity=None,
            created=None,
            last_updated_at=None,
        )

    def test_password_with_no_value_prompts_hidden_and_confirmed(self, runner: CliRunner) -> None:
        """`--password` with no value (flag_value sentinel) prompts for the new
        secret instead of taking it from argv; omitting `--password` entirely
        still means "leave unchanged" (covered by test_updates_ssid above)."""
        mock_client = _client(update_backup_access_point={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "backup",
                    "access-points",
                    "update",
                    "bap1",
                    "--password",
                    "--force",
                ],
                input="newsecret\nnewsecret\n",
            )

        assert result.exit_code == 0
        mock_client.update_backup_access_point.assert_awaited_once_with(
            "bap1",
            None,
            ssid=None,
            password="newsecret",
            enabled=None,
            uuid=None,
            connectivity=None,
            created=None,
            last_updated_at=None,
        )
        assert "newsecret" not in result.output


class TestBackupAccessPointsDelete:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_deletes(self, runner: CliRunner) -> None:
        mock_client = _client(delete_backup_access_point={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "backup", "access-points", "delete", "bap1", "--force"]
            )

        assert result.exit_code == 0
        mock_client.delete_backup_access_point.assert_awaited_once_with("bap1", None)

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--non-interactive",
                    "network",
                    "backup",
                    "access-points",
                    "delete",
                    "bap1",
                ],
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.delete_backup_access_point.assert_not_called()


class TestBackupAccessPointsRearrange:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_rearranges(self, runner: CliRunner) -> None:
        mock_client = _client(rearrange_backup_access_points={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "backup",
                    "access-points",
                    "rearrange",
                    "bap2",
                    "bap1",
                    "--force",
                ],
            )

        assert result.exit_code == 0
        mock_client.rearrange_backup_access_points.assert_awaited_once_with(["bap2", "bap1"], None)


class TestBackupAccessPointsDiscoverStart:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_discover_without_start_reads(self, runner: CliRunner) -> None:
        mock_client = _client(discover_backup_ssids={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "backup", "access-points", "discover"])

        assert result.exit_code == 0
        mock_client.discover_backup_ssids.assert_awaited_once()
        mock_client.start_backup_ssid_discovery.assert_not_called()

    def test_discover_with_start_writes(self, runner: CliRunner) -> None:
        mock_client = _client(start_backup_ssid_discovery={"meta": {"code": 202}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "backup", "access-points", "discover", "--start", "--force"]
            )

        assert result.exit_code == 0
        mock_client.start_backup_ssid_discovery.assert_awaited_once_with(None)

    def test_non_interactive_start_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--non-interactive",
                    "network",
                    "backup",
                    "access-points",
                    "discover",
                    "--start",
                ],
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.start_backup_ssid_discovery.assert_not_called()


class TestBackupAccessPointsCheck:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_runs_check(self, runner: CliRunner) -> None:
        mock_client = _client(backup_connectivity_check={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "backup", "access-points", "check", "--force"])

        assert result.exit_code == 0
        mock_client.backup_connectivity_check.assert_awaited_once_with(None)

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["--non-interactive", "network", "backup", "access-points", "check"],
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.backup_connectivity_check.assert_not_called()
