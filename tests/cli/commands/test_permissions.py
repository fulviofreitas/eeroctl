"""Unit tests for eeroctl.commands.network.permissions.

Tests cover:
- network permissions (get_permissions) -- data.role + data.permissions
  capability map (eero/api/permissions.py:38-41)
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
import yaml
from click.testing import CliRunner
from eero.exceptions import EeroAccessDeniedException, EeroPremiumRequiredException

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli
from eeroctl.transformers.permissions import extract_capability_map, extract_role

PERMISSIONS_RESPONSE = {
    "meta": {"code": 200},
    "data": {
        "role": "owner",
        "permissions": {"can_manage_network": True, "can_manage_guest_network": False},
    },
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


class TestNetworkPermissions:
    """Tests for `network permissions`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "permissions", "--help"])

        assert result.exit_code == 0
        assert "--output" in result.output
        assert "--network-id" in result.output

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_permissions=PERMISSIONS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", output_format, "network", "permissions"])

        assert result.exit_code == 0
        mock_client.get_permissions.assert_awaited_once()

    def test_table_output_shows_role_and_capabilities(self, runner: CliRunner):
        mock_client = _mock_client(get_permissions=PERMISSIONS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "permissions"])

        assert result.exit_code == 0
        assert "owner" in result.output
        assert "can_manage_network" in result.output

    def test_json_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(get_permissions=PERMISSIONS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "network", "permissions"])

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["data"] == PERMISSIONS_RESPONSE["data"]
        assert parsed["schema"] == "eero.network.permissions/v1"

    def test_yaml_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(get_permissions=PERMISSIONS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "yaml", "network", "permissions"])

        assert result.exit_code == 0
        parsed = yaml.safe_load(result.output)
        assert parsed["data"] == PERMISSIONS_RESPONSE["data"]

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_permissions=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "permissions"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_permissions", EeroPremiumRequiredException("Permissions")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "permissions"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        # commit 6 maps EeroAccessDeniedException directly; until then it falls
        # through the generic EeroAPIException branch's status_code == 403 check.
        mock_client = _mock_client_raising(
            "get_permissions", EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "permissions"])

        assert result.exit_code == ExitCode.FORBIDDEN


class TestExtractRoleAndCapabilityMap:
    """Unit tests for the `data.role`/`data.permissions` accessors."""

    def test_extract_role_returns_role(self):
        assert extract_role({"role": "owner", "permissions": {}}) == "owner"

    def test_extract_role_returns_none_when_missing(self):
        assert extract_role({"permissions": {}}) is None

    def test_extract_role_returns_none_for_non_dict(self):
        assert extract_role(None) is None
        assert extract_role([]) is None

    def test_extract_capability_map_returns_mapping(self):
        data = {"role": "owner", "permissions": {"can_manage_network": True}}
        assert extract_capability_map(data) == {"can_manage_network": True}

    def test_extract_capability_map_defaults_to_empty(self):
        assert extract_capability_map({"role": "owner"}) == {}
        assert extract_capability_map(None) == {}
