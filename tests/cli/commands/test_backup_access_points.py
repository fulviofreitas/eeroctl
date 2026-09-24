"""Unit tests for `network backup access-points *` (eeroctl.commands.network.backup).

Tests cover:
- network backup access-points list     (list_backup_access_points)
- network backup access-points discover (discover_backup_ssids, GET, verified)
"""

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from eero.exceptions import EeroAccessDeniedException, EeroPremiumRequiredException

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli

# Reuse the mock-client helpers defined in test_events.py rather than
# redefining them per module (standing rule from the batch-1 test audit); a
# shared conftest fixture lands after the group-1 stack is pushed.
from .test_events import _mock_client, _mock_client_raising

ACCESS_POINTS_RESPONSE = {
    "meta": {"code": 200},
    "data": {"access_points": [{"ssid": "Backup-1", "enabled": True}]},
}
DISCOVERY_RESPONSE = {
    "meta": {"code": 200},
    "data": {"ssids": ["Neighbour-5G", "Neighbour-2.4G"]},
}
EMPTY_RESPONSE = {"meta": {"code": 200}, "data": {}}


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI runner."""
    return CliRunner()


class TestBackupAccessPointsGroup:
    """Tests for the `network backup access-points` command group."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "backup", "access-points", "--help"])

        assert result.exit_code == 0
        assert "list" in result.output
        assert "discover" in result.output


class TestBackupAccessPointsList:
    """Tests for `network backup access-points list`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "backup", "access-points", "list", "--help"])

        assert result.exit_code == 0
        assert "--output" in result.output
        assert "--network-id" in result.output

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(list_backup_access_points=ACCESS_POINTS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["--output", output_format, "network", "backup", "access-points", "list"],
            )

        assert result.exit_code == 0
        mock_client.list_backup_access_points.assert_awaited_once()

    def test_json_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(list_backup_access_points=ACCESS_POINTS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", "json", "network", "backup", "access-points", "list"]
            )

        parsed = json.loads(result.output)
        assert parsed["data"] == ACCESS_POINTS_RESPONSE["data"]
        assert parsed["schema"] == "eero.network.backup.access_points.list/v1"

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(list_backup_access_points=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "backup", "access-points", "list"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "list_backup_access_points", EeroPremiumRequiredException("Backup")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "backup", "access-points", "list"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        # commit 6 maps EeroAccessDeniedException directly; until then it falls
        # through the generic EeroAPIException branch's status_code == 403 check.
        mock_client = _mock_client_raising(
            "list_backup_access_points", EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "backup", "access-points", "list"])

        assert result.exit_code == ExitCode.FORBIDDEN


class TestBackupAccessPointsDiscover:
    """Tests for `network backup access-points discover`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "backup", "access-points", "discover", "--help"])

        assert result.exit_code == 0

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(discover_backup_ssids=DISCOVERY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["--output", output_format, "network", "backup", "access-points", "discover"],
            )

        assert result.exit_code == 0
        mock_client.discover_backup_ssids.assert_awaited_once()

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(discover_backup_ssids=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "backup", "access-points", "discover"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "discover_backup_ssids", EeroPremiumRequiredException("Backup discover")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "backup", "access-points", "discover"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "discover_backup_ssids", EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "backup", "access-points", "discover"])

        assert result.exit_code == ExitCode.FORBIDDEN

    def test_existing_backup_show_unaffected(self, runner: CliRunner):
        """`backup show` still works after the access-points addition."""
        mock_client = _mock_client(
            get_backup_internet={"meta": {"code": 200}, "data": {"enabled": True}}
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "backup", "show"])

        assert result.exit_code == 0
