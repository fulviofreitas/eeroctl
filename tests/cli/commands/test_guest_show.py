"""Unit tests for the rewired `network guest show` (eeroctl.commands.network.guest).

Tests cover:
- network guest show now reads get_guest_network instead of the full
  network envelope, and keeps the password masked in every format
"""

import json
from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner
from eero.exceptions import EeroAccessDeniedException, EeroPremiumRequiredException

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli

# Reuse the mock-client helpers defined in test_events.py rather than
# redefining them per module (standing rule from the batch-1 test audit); a
# shared conftest fixture lands after the group-1 stack is pushed.
from .test_events import _mock_client, _mock_client_raising

GUEST_RESPONSE = {
    "meta": {"code": 200},
    "data": {"enabled": True, "name": "Guest WiFi", "password": "hunter2secret"},
}
GUEST_DISABLED_RESPONSE = {
    "meta": {"code": 200},
    "data": {"enabled": False, "name": None, "password": None},
}
EMPTY_RESPONSE = {"meta": {"code": 200}, "data": {}}


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI runner."""
    return CliRunner()


class TestGuestShow:
    """Tests for `network guest show`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "guest", "show", "--help"])

        assert result.exit_code == 0

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_guest_network=GUEST_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", output_format, "network", "guest", "show"])

        assert result.exit_code == 0
        mock_client.get_guest_network.assert_awaited_once()

    def test_calls_get_guest_network_not_get_network(self, runner: CliRunner):
        """Confirms the rewire: no more full-network-envelope read for this command."""
        mock_client = _mock_client(get_guest_network=GUEST_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            runner.invoke(cli, ["network", "guest", "show"])

        mock_client.get_guest_network.assert_awaited_once()
        mock_client.get_network.assert_not_awaited()

    def test_enabled_and_name_shown(self, runner: CliRunner):
        mock_client = _mock_client(get_guest_network=GUEST_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "guest", "show"])

        assert "Guest WiFi" in result.output
        assert "Yes" in result.output

    def test_password_masked_in_table_output(self, runner: CliRunner):
        mock_client = _mock_client(get_guest_network=GUEST_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "guest", "show"])

        assert "hunter2secret" not in result.output
        assert "********" in result.output

    def test_password_masked_in_json_output(self, runner: CliRunner):
        """The password stays masked even in json -- this command never
        round-trips the real value, unlike the generic-renderer convention
        elsewhere (json is not an opt-in to this particular secret).
        """
        mock_client = _mock_client(get_guest_network=GUEST_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "network", "guest", "show"])

        assert "hunter2secret" not in result.output
        parsed = json.loads(result.output)
        assert parsed["data"]["password"] == "********"
        assert parsed["data"]["enabled"] is True
        assert parsed["data"]["name"] == "Guest WiFi"

    def test_password_masked_in_yaml_output(self, runner: CliRunner):
        mock_client = _mock_client(get_guest_network=GUEST_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "yaml", "network", "guest", "show"])

        assert "hunter2secret" not in result.output
        parsed = yaml.safe_load(result.output)
        assert parsed["data"]["password"] == "********"

    def test_password_masked_in_list_output(self, runner: CliRunner):
        mock_client = _mock_client(get_guest_network=GUEST_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "list", "network", "guest", "show"])

        assert "hunter2secret" not in result.output

    def test_password_masked_in_text_output(self, runner: CliRunner):
        mock_client = _mock_client(get_guest_network=GUEST_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "text", "network", "guest", "show"])

        assert "hunter2secret" not in result.output
        assert result.exit_code == 0

    def test_no_password_shows_na(self, runner: CliRunner):
        mock_client = _mock_client(get_guest_network=GUEST_DISABLED_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "guest", "show"])

        assert result.exit_code == 0
        assert "N/A" in result.output

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_guest_network=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "guest", "show"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_guest_network", EeroPremiumRequiredException("Guest")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "guest", "show"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        # commit 6 maps EeroAccessDeniedException directly; until then it falls
        # through the generic EeroAPIException branch's status_code == 403 check.
        mock_client = _mock_client_raising(
            "get_guest_network", EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "guest", "show"])

        assert result.exit_code == ExitCode.FORBIDDEN
