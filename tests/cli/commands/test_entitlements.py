"""Unit tests for eeroctl.commands.network.entitlements and commands.account.

Tests cover:
- network entitlements show|upsell|capabilities (get_entitlement_features,
  get_upsell_features, get_model_capabilities)
- account premium (get_premium_customer)

Each command is a plain, live-verified GET (eero-api 8.0.1 migration plan §4,
phase A) -- no confirmation, no writes. Mocking follows the pattern established
in test_activity.py: patch `eeroctl.utils.EeroClient` (the single construction
site behind `build_client`), not the command module.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
import yaml
from click.testing import CliRunner
from eero.exceptions import EeroAccessDeniedException, EeroPremiumRequiredException

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli

ENTITLEMENTS_RESPONSE = {
    "meta": {"code": 200},
    "data": {"premium_eligible": True, "premium_dns": True},
}
UPSELL_RESPONSE = {"meta": {"code": 200}, "data": {"available_plans": ["plus", "secure"]}}
CAPABILITIES_RESPONSE = {"meta": {"code": 200}, "data": {"model": "eero6", "wifi6": True}}
PREMIUM_CUSTOMER_RESPONSE = {"meta": {"code": 200}, "data": {"is_premium_customer": True}}
EMPTY_RESPONSE = {"meta": {"code": 200}, "data": {}}


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI runner."""
    return CliRunner()


def _mock_client(**method_returns) -> AsyncMock:
    """Build an AsyncMock EeroClient with the given async method return values."""
    mock_client = AsyncMock()
    for name, value in method_returns.items():
        setattr(mock_client, name, AsyncMock(return_value=value))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestEntitlementsGroup:
    """Tests for the `network entitlements` command group."""

    def test_entitlements_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "entitlements", "--help"])

        assert result.exit_code == 0
        assert "show" in result.output
        assert "upsell" in result.output
        assert "capabilities" in result.output


class TestEntitlementsShow:
    """Tests for `network entitlements show`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "entitlements", "show", "--help"])

        assert result.exit_code == 0
        assert "--output" in result.output
        assert "--network-id" in result.output

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_entitlement_features=ENTITLEMENTS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", output_format, "network", "entitlements", "show"]
            )

        assert result.exit_code == 0
        mock_client.get_entitlement_features.assert_awaited_once()

    def test_json_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(get_entitlement_features=ENTITLEMENTS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "network", "entitlements", "show"])

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["data"] == ENTITLEMENTS_RESPONSE["data"]
        assert parsed["schema"] == "eero.network.entitlements.show/v1"

    def test_yaml_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(get_entitlement_features=ENTITLEMENTS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "yaml", "network", "entitlements", "show"])

        assert result.exit_code == 0
        parsed = yaml.safe_load(result.output)
        assert parsed["data"] == ENTITLEMENTS_RESPONSE["data"]

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_entitlement_features=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "entitlements", "show"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = AsyncMock()
        mock_client.get_entitlement_features = AsyncMock(
            side_effect=EeroPremiumRequiredException("Entitlements")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "entitlements", "show"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        # commit 6 maps EeroAccessDeniedException directly; until then it falls
        # through the generic EeroAPIException branch's status_code == 403 check.
        mock_client = AsyncMock()
        mock_client.get_entitlement_features = AsyncMock(
            side_effect=EeroAccessDeniedException(403, "Forbidden")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "entitlements", "show"])

        assert result.exit_code == ExitCode.FORBIDDEN


class TestEntitlementsUpsell:
    """Tests for `network entitlements upsell`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "entitlements", "upsell", "--help"])

        assert result.exit_code == 0

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_upsell_features=UPSELL_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", output_format, "network", "entitlements", "upsell"]
            )

        assert result.exit_code == 0
        mock_client.get_upsell_features.assert_awaited_once()

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_upsell_features=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "entitlements", "upsell"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = AsyncMock()
        mock_client.get_upsell_features = AsyncMock(
            side_effect=EeroPremiumRequiredException("Upsell")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "entitlements", "upsell"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        mock_client = AsyncMock()
        mock_client.get_upsell_features = AsyncMock(
            side_effect=EeroAccessDeniedException(403, "Forbidden")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "entitlements", "upsell"])

        assert result.exit_code == ExitCode.FORBIDDEN


class TestEntitlementsCapabilities:
    """Tests for `network entitlements capabilities`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "entitlements", "capabilities", "--help"])

        assert result.exit_code == 0

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_model_capabilities=CAPABILITIES_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", output_format, "network", "entitlements", "capabilities"]
            )

        assert result.exit_code == 0
        mock_client.get_model_capabilities.assert_awaited_once()

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_model_capabilities=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "entitlements", "capabilities"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = AsyncMock()
        mock_client.get_model_capabilities = AsyncMock(
            side_effect=EeroPremiumRequiredException("Capabilities")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "entitlements", "capabilities"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        mock_client = AsyncMock()
        mock_client.get_model_capabilities = AsyncMock(
            side_effect=EeroAccessDeniedException(403, "Forbidden")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "entitlements", "capabilities"])

        assert result.exit_code == ExitCode.FORBIDDEN


class TestAccountGroup:
    """Tests for the `account` command group."""

    def test_account_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["account", "--help"])

        assert result.exit_code == 0
        assert "premium" in result.output


class TestAccountPremium:
    """Tests for `account premium` (get_premium_customer -- no network_id)."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["account", "premium", "--help"])

        assert result.exit_code == 0
        assert "--output" in result.output
        assert "--network-id" not in result.output

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_premium_customer=PREMIUM_CUSTOMER_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", output_format, "account", "premium"])

        assert result.exit_code == 0
        mock_client.get_premium_customer.assert_awaited_once_with()

    def test_json_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(get_premium_customer=PREMIUM_CUSTOMER_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "account", "premium"])

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["data"] == PREMIUM_CUSTOMER_RESPONSE["data"]
        assert parsed["schema"] == "eero.account.premium/v1"

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_premium_customer=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["account", "premium"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = AsyncMock()
        mock_client.get_premium_customer = AsyncMock(
            side_effect=EeroPremiumRequiredException("Account premium")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["account", "premium"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        mock_client = AsyncMock()
        mock_client.get_premium_customer = AsyncMock(
            side_effect=EeroAccessDeniedException(403, "Forbidden")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["account", "premium"])

        assert result.exit_code == ExitCode.FORBIDDEN
