"""Unit tests for `network dns policy show` (eeroctl.commands.network.dns).

Tests cover:
- network dns policy show (get_advanced_content_filter, premium,
  data.allowed_list/blocked_list -- eero-api 8.0.1 migration plan §4)
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
import yaml
from click.testing import CliRunner
from eero.exceptions import EeroAccessDeniedException, EeroPremiumRequiredException

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli

DNS_POLICY_RESPONSE = {
    "meta": {"code": 200},
    "data": {"allowed_list": ["example.com"], "blocked_list": ["ads.example.net"]},
}
EMPTY_RESPONSE = {"meta": {"code": 200}, "data": {}}


def _mock_client(**method_returns) -> AsyncMock:
    """Build an AsyncMock EeroClient with the given async method return values."""
    mock_client = AsyncMock()
    for name, value in method_returns.items():
        setattr(mock_client, name, AsyncMock(return_value=value))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def _mock_client_raising(method_name: str, exc: Exception) -> AsyncMock:
    mock_client = AsyncMock()
    setattr(mock_client, method_name, AsyncMock(side_effect=exc))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI runner."""
    return CliRunner()


class TestDnsPolicyGroup:
    """Tests for the `network dns policy` command group."""

    def test_policy_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "dns", "policy", "--help"])

        assert result.exit_code == 0
        assert "show" in result.output


class TestDnsPolicyShow:
    """Tests for `network dns policy show`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "dns", "policy", "show", "--help"])

        assert result.exit_code == 0
        assert "--output" in result.output
        assert "--network-id" in result.output

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_advanced_content_filter=DNS_POLICY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", output_format, "network", "dns", "policy", "show"]
            )

        assert result.exit_code == 0
        mock_client.get_advanced_content_filter.assert_awaited_once()

    def test_json_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(get_advanced_content_filter=DNS_POLICY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "network", "dns", "policy", "show"])

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["data"] == DNS_POLICY_RESPONSE["data"]
        assert parsed["schema"] == "eero.network.dns.policy.show/v1"

    def test_yaml_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(get_advanced_content_filter=DNS_POLICY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "yaml", "network", "dns", "policy", "show"])

        assert result.exit_code == 0
        parsed = yaml.safe_load(result.output)
        assert parsed["data"] == DNS_POLICY_RESPONSE["data"]

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_advanced_content_filter=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "dns", "policy", "show"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_advanced_content_filter", EeroPremiumRequiredException("DNS policy")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "dns", "policy", "show"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        # commit 6 maps EeroAccessDeniedException directly; until then it falls
        # through the generic EeroAPIException branch's status_code == 403 check.
        mock_client = _mock_client_raising(
            "get_advanced_content_filter", EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "dns", "policy", "show"])

        assert result.exit_code == ExitCode.FORBIDDEN

    def test_does_not_require_confirmation(self, runner: CliRunner):
        """DNS policy show is a plain GET, unlike every DNS write in this group."""
        mock_client = _mock_client(get_advanced_content_filter=DNS_POLICY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "dns", "policy", "show"], input="")

        assert result.exit_code == 0
