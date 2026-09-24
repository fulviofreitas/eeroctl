"""Unit tests for eeroctl.commands.network.subnets.

Tests cover:
- network subnets show                    (get_subnets_config)
- network subnets filters show <subnet-id> (get_subnet_content_filters)
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

SUBNETS_RESPONSE = {
    "meta": {"code": 200},
    "data": {"main": {"id": "main"}, "guest": {"id": "guest"}},
}
FILTERS_RESPONSE = {
    "meta": {"code": 200},
    "data": {"blocked_categories": ["adult"], "allowed_domains": []},
}
EMPTY_RESPONSE = {"meta": {"code": 200}, "data": {}}


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI runner."""
    return CliRunner()


class TestSubnetsGroup:
    """Tests for the `network subnets` command group."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "subnets", "--help"])

        assert result.exit_code == 0
        assert "show" in result.output
        assert "filters" in result.output


class TestSubnetsShow:
    """Tests for `network subnets show`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "subnets", "show", "--help"])

        assert result.exit_code == 0
        assert "--output" in result.output
        assert "--network-id" in result.output

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_subnets_config=SUBNETS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", output_format, "network", "subnets", "show"])

        assert result.exit_code == 0
        mock_client.get_subnets_config.assert_awaited_once()

    def test_json_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(get_subnets_config=SUBNETS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "network", "subnets", "show"])

        parsed = json.loads(result.output)
        assert parsed["data"] == SUBNETS_RESPONSE["data"]
        assert parsed["schema"] == "eero.network.subnets.show/v1"

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_subnets_config=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "subnets", "show"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_subnets_config", EeroPremiumRequiredException("Subnets")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "subnets", "show"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        # commit 6 maps EeroAccessDeniedException directly; until then it falls
        # through the generic EeroAPIException branch's status_code == 403 check.
        mock_client = _mock_client_raising(
            "get_subnets_config", EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "subnets", "show"])

        assert result.exit_code == ExitCode.FORBIDDEN


class TestSubnetFiltersShow:
    """Tests for `network subnets filters show <subnet-id>`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "subnets", "filters", "show", "--help"])

        assert result.exit_code == 0
        assert "SUBNET_ID" in result.output

    def test_requires_subnet_id(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "subnets", "filters", "show"])

        assert result.exit_code == 2

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_subnet_content_filters=FILTERS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["--output", output_format, "network", "subnets", "filters", "show", "main"],
            )

        assert result.exit_code == 0
        mock_client.get_subnet_content_filters.assert_awaited_once()

    def test_subnet_id_passed_verbatim(self, runner: CliRunner):
        mock_client = _mock_client(get_subnet_content_filters=FILTERS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            runner.invoke(cli, ["network", "subnets", "filters", "show", "some-subnet-id"])

        call_args = mock_client.get_subnet_content_filters.call_args[0]
        assert call_args[0] == "some-subnet-id"

    def test_json_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(get_subnet_content_filters=FILTERS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", "json", "network", "subnets", "filters", "show", "main"]
            )

        parsed = json.loads(result.output)
        assert parsed["data"] == FILTERS_RESPONSE["data"]
        assert parsed["schema"] == "eero.network.subnets.filters.show/v1"

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_subnet_content_filters=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "subnets", "filters", "show", "main"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_subnet_content_filters", EeroPremiumRequiredException("Filters")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "subnets", "filters", "show", "main"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_subnet_content_filters", EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "subnets", "filters", "show", "main"])

        assert result.exit_code == ExitCode.FORBIDDEN
