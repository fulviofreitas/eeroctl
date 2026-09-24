"""Unit tests for commit 17's phase-A reads.

Tests cover:
- network dhcp show (get_network -> data.dhcp/lease/connection/ip_settings/wan_type)
- network wpa3 show (get_wpa3_per_band)
- network security fast-transition show (get_fast_transition)
- network security show extended with mlo_mode/passpoint/proxied_nodes/ddns
"""

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from eero.exceptions import EeroAccessDeniedException, EeroPremiumRequiredException

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli
from eeroctl.transformers.network import extract_network_dhcp_view, extract_network_security_extras

# Reuse the mock-client helpers defined in test_events.py rather than
# redefining them per module (standing rule from the batch-1 test audit); a
# shared conftest fixture lands after the group-1 stack is pushed.
from .test_events import _mock_client, _mock_client_raising

NETWORK_RESPONSE = {
    "meta": {"code": 200},
    "data": {
        "id": "1",
        "name": "Home",
        "dhcp": {"mode": "automatic"},
        "lease": {"time_seconds": 86400},
        "connection": {"mode": "NAT"},
        "ip_settings": {"wan_ip": "203.0.113.1"},
        "wan_type": "dhcp",
        "mlo_mode": "disabled",
        "passpoint": {"enabled": False},
        "proxied_nodes": {"enabled": False},
        "ddns": {"enabled": False},
    },
}
EMPTY_NETWORK_RESPONSE = {"meta": {"code": 200}, "data": {}}

SECURITY_RESPONSE = {
    "meta": {"code": 200},
    "data": {"wpa3": True, "band_steering": True, "upnp": True, "ipv6_upstream": False},
}

WPA3_RESPONSE = {
    "meta": {"code": 200},
    "data": {"band_2_4_ghz": "WPA2_WPA3", "band_5_ghz": "WPA3"},
}
EMPTY_RESPONSE = {"meta": {"code": 200}, "data": {}}

FAST_TRANSITION_RESPONSE = {"meta": {"code": 200}, "data": {"enabled": True}}


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI runner."""
    return CliRunner()


class TestDhcpShow:
    """Tests for `network dhcp show`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "dhcp", "show", "--help"])

        assert result.exit_code == 0
        assert "--output" in result.output
        assert "--network-id" in result.output

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_network=NETWORK_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", output_format, "network", "dhcp", "show"])

        assert result.exit_code == 0
        mock_client.get_network.assert_awaited_once()

    def test_json_output_contains_expected_keys(self, runner: CliRunner):
        mock_client = _mock_client(get_network=NETWORK_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "network", "dhcp", "show"])

        parsed = json.loads(result.output)
        assert set(parsed["data"].keys()) == {
            "dhcp",
            "lease",
            "connection",
            "ip_settings",
            "wan_type",
        }
        assert parsed["data"]["wan_type"] == "dhcp"
        assert parsed["schema"] == "eero.network.dhcp.show/v1"

    def test_empty_network_data(self, runner: CliRunner):
        mock_client = _mock_client(get_network=EMPTY_NETWORK_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "dhcp", "show"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising("get_network", EeroPremiumRequiredException("DHCP"))

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "dhcp", "show"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        # commit 6 maps EeroAccessDeniedException directly; until then it falls
        # through the generic EeroAPIException branch's status_code == 403 check.
        mock_client = _mock_client_raising(
            "get_network", EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "dhcp", "show"])

        assert result.exit_code == ExitCode.FORBIDDEN

    def test_existing_reservations_command_unaffected(self, runner: CliRunner):
        """`dhcp reservations` still works after the `show` addition."""
        mock_client = _mock_client(get_reservations={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "dhcp", "reservations"])

        assert result.exit_code == 0


class TestWpa3Show:
    """Tests for `network wpa3 show`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "wpa3", "show", "--help"])

        assert result.exit_code == 0

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_wpa3_per_band=WPA3_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", output_format, "network", "wpa3", "show"])

        assert result.exit_code == 0
        mock_client.get_wpa3_per_band.assert_awaited_once()

    def test_json_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(get_wpa3_per_band=WPA3_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "network", "wpa3", "show"])

        parsed = json.loads(result.output)
        assert parsed["data"] == WPA3_RESPONSE["data"]
        assert parsed["schema"] == "eero.network.wpa3.show/v1"

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_wpa3_per_band=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "wpa3", "show"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_wpa3_per_band", EeroPremiumRequiredException("WPA3")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "wpa3", "show"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_wpa3_per_band", EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "wpa3", "show"])

        assert result.exit_code == ExitCode.FORBIDDEN

    def test_distinct_from_security_wpa3_toggle(self, runner: CliRunner):
        """`network wpa3` is a separate group from `network security wpa3`."""
        result = runner.invoke(cli, ["network", "wpa3", "--help"])

        assert result.exit_code == 0
        assert "enable" not in result.output
        assert "disable" not in result.output


class TestSecurityFastTransitionShow:
    """Tests for `network security fast-transition show`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "security", "fast-transition", "show", "--help"])

        assert result.exit_code == 0
        assert "--output" in result.output
        assert "--network-id" in result.output

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_fast_transition=FAST_TRANSITION_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["--output", output_format, "network", "security", "fast-transition", "show"],
            )

        assert result.exit_code == 0
        mock_client.get_fast_transition.assert_awaited_once()

    def test_json_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(get_fast_transition=FAST_TRANSITION_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", "json", "network", "security", "fast-transition", "show"]
            )

        parsed = json.loads(result.output)
        assert parsed["data"] == FAST_TRANSITION_RESPONSE["data"]
        assert parsed["schema"] == "eero.network.security.fast_transition.show/v1"

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_fast_transition=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "security", "fast-transition", "show"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_fast_transition", EeroPremiumRequiredException("FT")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "security", "fast-transition", "show"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_fast_transition", EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "security", "fast-transition", "show"])

        assert result.exit_code == ExitCode.FORBIDDEN


class TestSecurityShowExtended:
    """Tests for the extended `network security show`."""

    def test_calls_both_get_security_settings_and_get_network(self, runner: CliRunner):
        mock_client = _mock_client(
            get_security_settings=SECURITY_RESPONSE, get_network=NETWORK_RESPONSE
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "security", "show"])

        assert result.exit_code == 0
        mock_client.get_security_settings.assert_awaited_once()
        mock_client.get_network.assert_awaited_once()

    def test_json_output_includes_extended_fields(self, runner: CliRunner):
        mock_client = _mock_client(
            get_security_settings=SECURITY_RESPONSE, get_network=NETWORK_RESPONSE
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "network", "security", "show"])

        parsed = json.loads(result.output)
        for key in ("mlo_mode", "passpoint", "proxied_nodes", "ddns"):
            assert key in parsed["data"]
        assert parsed["data"]["mlo_mode"] == "disabled"
        # Original security fields still present alongside the extras.
        assert parsed["data"]["wpa3"] is True

    def test_table_output_shows_extended_fields(self, runner: CliRunner):
        mock_client = _mock_client(
            get_security_settings=SECURITY_RESPONSE, get_network=NETWORK_RESPONSE
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "security", "show"])

        assert result.exit_code == 0
        assert "mlo_mode" in result.output

    def test_table_output_redacts_sensitive_extras(self, runner: CliRunner):
        """Regression test for the batch-2 security review Low finding.

        Extras used to be rendered with str(...) outside render_generic, so
        a planted ddns credential (a provider username/token) leaked in
        table output.
        """
        network_with_ddns_secret = {
            "meta": {"code": 200},
            "data": {
                **NETWORK_RESPONSE["data"],
                "ddns": {"provider": "dyndns", "password": "DDNSSECRET123"},
            },
        }
        mock_client = _mock_client(
            get_security_settings=SECURITY_RESPONSE, get_network=network_with_ddns_secret
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "security", "show"])

        assert result.exit_code == 0
        assert "DDNSSECRET123" not in result.output

    def test_list_output_redacts_sensitive_extras(self, runner: CliRunner):
        network_with_ddns_secret = {
            "meta": {"code": 200},
            "data": {
                **NETWORK_RESPONSE["data"],
                "ddns": {"provider": "dyndns", "password": "DDNSSECRET123"},
            },
        }
        mock_client = _mock_client(
            get_security_settings=SECURITY_RESPONSE, get_network=network_with_ddns_secret
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "list", "network", "security", "show"])

        assert result.exit_code == 0
        assert "DDNSSECRET123" not in result.output

    def test_json_output_still_carries_the_raw_ddns_value(self, runner: CliRunner):
        """json stays the deliberate raw-payload opt-in."""
        network_with_ddns_secret = {
            "meta": {"code": 200},
            "data": {
                **NETWORK_RESPONSE["data"],
                "ddns": {"provider": "dyndns", "password": "DDNSSECRET123"},
            },
        }
        mock_client = _mock_client(
            get_security_settings=SECURITY_RESPONSE, get_network=network_with_ddns_secret
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "network", "security", "show"])

        parsed = json.loads(result.output)
        assert parsed["data"]["ddns"]["password"] == "DDNSSECRET123"
        assert "passpoint" in result.output


class TestExtractHelpers:
    """Unit tests for the new network.py accessors."""

    def test_extract_network_dhcp_view_returns_expected_keys(self):
        view = extract_network_dhcp_view(NETWORK_RESPONSE["data"])
        assert set(view.keys()) == {"dhcp", "lease", "connection", "ip_settings", "wan_type"}
        assert view["wan_type"] == "dhcp"

    def test_extract_network_dhcp_view_defaults_to_none(self):
        view = extract_network_dhcp_view({})
        assert view == {
            "dhcp": None,
            "lease": None,
            "connection": None,
            "ip_settings": None,
            "wan_type": None,
        }

    def test_extract_network_security_extras_returns_expected_keys(self):
        extras = extract_network_security_extras(NETWORK_RESPONSE["data"])
        assert extras == {
            "mlo_mode": "disabled",
            "passpoint": {"enabled": False},
            "proxied_nodes": {"enabled": False},
            "ddns": {"enabled": False},
        }

    def test_extract_network_security_extras_defaults_to_none(self):
        extras = extract_network_security_extras({})
        assert extras == {
            "mlo_mode": None,
            "passpoint": None,
            "proxied_nodes": None,
            "ddns": None,
        }
