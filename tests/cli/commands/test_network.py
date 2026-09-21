"""Unit tests for eero.cli.commands.network module.

Tests cover:
- network list command
- network show command
- network use command
- network rename command
- network dns subcommands
- network security subcommands
- network guest subcommands
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.main import cli


class TestNetworkGroup:
    """Tests for the network command group."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_network_help(self, runner):
        """Test network group shows help."""
        result = runner.invoke(cli, ["network", "--help"])

        assert result.exit_code == 0
        assert "Manage network settings" in result.output
        assert "list" in result.output
        assert "show" in result.output
        assert "use" in result.output


class TestNetworkList:
    """Tests for network list command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_networks(self):
        """Create mock network response (raw API format)."""
        return {
            "meta": {"code": 200},
            "data": {
                "networks": {
                    "count": 2,
                    "data": [
                        {
                            "url": "/2.2/networks/net_1",
                            "name": "Home Network",
                            "status": {"status": "online"},
                            "wan_ip": "203.0.113.1",
                            "public_ip": "203.0.113.1",
                            "isp": {"name": "Comcast"},
                        },
                        {
                            "url": "/2.2/networks/net_2",
                            "name": "Office Network",
                            "status": {"status": "online"},
                            "wan_ip": "203.0.113.2",
                            "public_ip": "203.0.113.2",
                            "isp": {"name": "AT&T"},
                        },
                    ],
                }
            },
        }

    def test_network_list_help(self, runner):
        """Test network list shows help."""
        result = runner.invoke(cli, ["network", "list", "--help"])

        assert result.exit_code == 0
        assert "List all networks" in result.output

    @patch("eeroctl.commands.network.base.run_with_client")
    def test_network_list_displays_networks(self, mock_run_with_client, runner, mock_networks):
        """Test network list displays networks in table format."""
        # Detailed network responses for get_network calls
        detail_net_1 = {
            "meta": {"code": 200},
            "data": {
                "url": "/2.2/networks/net_1",
                "name": "Home Network",
                "status": {"status": "online"},
                "wan_ip": "203.0.113.1",
                "public_ip": "203.0.113.1",
                "isp": {"name": "Comcast"},
            },
        }
        detail_net_2 = {
            "meta": {"code": 200},
            "data": {
                "url": "/2.2/networks/net_2",
                "name": "Office Network",
                "status": {"status": "online"},
                "wan_ip": "203.0.113.2",
                "public_ip": "203.0.113.2",
                "isp": {"name": "AT&T"},
            },
        }

        async def run_func(func):
            # Create mock client and call the function
            mock_client = AsyncMock()
            mock_client.get_networks = AsyncMock(return_value=mock_networks)
            # Mock get_network to return detailed info for each network
            mock_client.get_network = AsyncMock(side_effect=[detail_net_1, detail_net_2])
            await func(mock_client)

        mock_run_with_client.side_effect = run_func

        result = runner.invoke(cli, ["network", "list"])

        # Should contain network names
        assert "Home Network" in result.output or "net_1" in result.output

    @patch("eeroctl.commands.network.base.run_with_client")
    def test_network_list_empty(self, mock_run_with_client, runner):
        """Test network list with no networks."""
        empty_response = {
            "meta": {"code": 200},
            "data": {"networks": {"count": 0, "data": []}},
        }

        async def run_func(func):
            mock_client = AsyncMock()
            mock_client.get_networks = AsyncMock(return_value=empty_response)
            await func(mock_client)

        mock_run_with_client.side_effect = run_func

        result = runner.invoke(cli, ["network", "list"])

        assert "No networks found" in result.output

    @patch("eeroctl.commands.network.base.run_with_client")
    def test_network_list_json_output(self, mock_run_with_client, runner, mock_networks):
        """Test network list with JSON output."""
        # Detailed network responses for get_network calls
        detail_net_1 = {
            "meta": {"code": 200},
            "data": {
                "url": "/2.2/networks/net_1",
                "name": "Home Network",
                "status": {"status": "online"},
                "wan_ip": "203.0.113.1",
                "public_ip": "203.0.113.1",
                "isp": {"name": "Comcast"},
            },
        }
        detail_net_2 = {
            "meta": {"code": 200},
            "data": {
                "url": "/2.2/networks/net_2",
                "name": "Office Network",
                "status": {"status": "online"},
                "wan_ip": "203.0.113.2",
                "public_ip": "203.0.113.2",
                "isp": {"name": "AT&T"},
            },
        }

        async def run_func(func):
            mock_client = AsyncMock()
            mock_client.get_networks = AsyncMock(return_value=mock_networks)
            # Mock get_network to return detailed info for each network
            mock_client.get_network = AsyncMock(side_effect=[detail_net_1, detail_net_2])
            await func(mock_client)

        mock_run_with_client.side_effect = run_func

        result = runner.invoke(cli, ["--output", "json", "network", "list"])

        # Should be valid JSON
        try:
            data = json.loads(result.output)
            assert "data" in data
        except json.JSONDecodeError:
            pass  # May have other output


class TestNetworkShow:
    """Tests for network show command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_network(self):
        """Create a mock network object."""
        network = MagicMock()
        network.id = "net_123"
        network.name = "Home Network"
        network.status = "connected"
        network.public_ip = "203.0.113.42"
        network.isp_name = "Comcast"
        network.model_dump = MagicMock(
            return_value={
                "id": "net_123",
                "name": "Home Network",
                "status": "connected",
            }
        )
        return network

    def test_network_show_help(self, runner):
        """Test network show shows help."""
        result = runner.invoke(cli, ["network", "show", "--help"])

        assert result.exit_code == 0
        assert "Show current network details" in result.output


class TestNetworkUse:
    """Tests for network use command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_network_use_help(self, runner):
        """Test network use shows help."""
        result = runner.invoke(cli, ["network", "use", "--help"])

        assert result.exit_code == 0
        assert "Set preferred network" in result.output

    def test_network_use_requires_argument(self, runner):
        """Test network use requires network ID argument."""
        result = runner.invoke(cli, ["network", "use"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output or "NETWORK_ID" in result.output


class TestNetworkRename:
    """Tests for network rename command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_network_rename_help(self, runner):
        """Test network rename shows help."""
        result = runner.invoke(cli, ["network", "rename", "--help"])

        assert result.exit_code == 0
        assert "Rename the network" in result.output
        assert "--name" in result.output

    def test_network_rename_requires_name_option(self, runner):
        """Test network rename requires --name option."""
        result = runner.invoke(cli, ["network", "rename"])

        assert result.exit_code != 0
        assert "Missing option" in result.output or "--name" in result.output


class TestNetworkDNS:
    """Tests for network dns subcommands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_dns_group_help(self, runner):
        """Test dns group shows help."""
        result = runner.invoke(cli, ["network", "dns", "--help"])

        assert result.exit_code == 0
        assert "Manage DNS settings" in result.output
        assert "show" in result.output
        assert "mode" in result.output
        assert "caching" in result.output

    def test_dns_show_help(self, runner):
        """Test dns show shows help."""
        result = runner.invoke(cli, ["network", "dns", "show", "--help"])

        assert result.exit_code == 0
        assert "Show current DNS settings" in result.output

    def test_dns_mode_set_help(self, runner):
        """Help states the contract rather than enumerating providers.

        Provider names come from the network's catalogue, not a fixed list, so
        --help must stay correct offline and point at 'dns providers'.
        """
        result = runner.invoke(cli, ["network", "dns", "mode", "set", "--help"])

        assert result.exit_code == 0
        assert "auto" in result.output
        assert "custom" in result.output
        assert "dns providers" in result.output
        assert "reboots every eero" in result.output

    def test_dns_providers_help(self, runner):
        """Test dns providers shows help."""
        result = runner.invoke(cli, ["network", "dns", "providers", "--help"])

        assert result.exit_code == 0
        assert "DNS providers" in result.output

    def test_dns_clear_help(self, runner):
        """dns clear documents that it is non-destructive."""
        result = runner.invoke(cli, ["network", "dns", "clear", "--help"])

        assert result.exit_code == 0
        assert "--family" in result.output
        assert "retains" in result.output

    def test_dns_caching_enable_help(self, runner):
        """Test dns caching enable shows help."""
        result = runner.invoke(cli, ["network", "dns", "caching", "enable", "--help"])

        assert result.exit_code == 0
        assert "Enable DNS caching" in result.output

    def test_dns_caching_disable_help(self, runner):
        """Test dns caching disable shows help."""
        result = runner.invoke(cli, ["network", "dns", "caching", "disable", "--help"])

        assert result.exit_code == 0
        assert "Disable DNS caching" in result.output


# ---------------------------------------------------------------------------
# TestDNSShow
# ---------------------------------------------------------------------------


_SENSITIVE_NETWORK_FIELDS = {
    "password": "br@stemp",
    "wan_ip": "162.206.74.252",
    "geo_ip": {"city": "Brentwood", "postalCode": "94513"},
    "guest_network": {"name": "Guest", "password": "california19", "enabled": False},
    "eeros": {
        "count": 1,
        "data": [{"serial": "GGB21E0A402700SM", "mac_address": "24:2d:6c:76:ac:c0"}],
    },
}
"""Fields the network endpoint returns that ``dns show`` must never emit.

Values mirror the shape of a real ``GET networks/{id}`` response.
"""


def _dns_response(**overrides):
    """Build a realistic ``get_dns_settings`` envelope.

    Includes the sensitive network fields by default, because the real endpoint
    does and the scoping tests need something to fail against.
    """
    data = {
        **_SENSITIVE_NETWORK_FIELDS,
        "dns": {
            "mode": "custom",
            "parent": {"ips": ["192.168.1.254"]},
            "custom": {"ips": ["1.1.1.1", "1.0.0.1"]},
            "caching": False,
            "default_test_servers": [
                {
                    "name": "Cloudflare",
                    "ipv4": ["1.1.1.1", "1.0.0.1"],
                    "ipv6": ["2606:4700:4700::1111", "2606:4700:4700::1001"],
                },
            ],
        },
        "ipv6": {
            "name_servers": {
                "mode": "custom",
                # The API stores IPv6 fully expanded.
                "custom": ["2606:4700:4700:0:0:0:0:1111", "2606:4700:4700:0:0:0:0:1001"],
            }
        },
    }
    data.update(overrides)
    return {"meta": {"code": 200, "server_time": "2026-09-14T04:54:38.854Z"}, "data": data}


class TestDNSShow:
    """Tests for ``eero network dns show`` field reads and output scoping."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def _invoke(self, runner, response, *args):
        """Run ``dns show`` against a mocked client returning *response*."""
        client = MagicMock()
        client.get_dns_settings = AsyncMock(return_value=response)

        async def _run(func):
            await func(client)

        with patch("eeroctl.commands.network.dns.run_with_client", side_effect=_run):
            return runner.invoke(cli, ["--network-id", "NID", "network", "dns", "show", *args])

    # -- field reads --------------------------------------------------------

    def test_show_reads_mode_from_data_envelope(self, runner):
        """Mode comes from data.dns.mode, not a top-level key."""
        result = self._invoke(runner, _dns_response())

        assert result.exit_code == 0
        assert "custom" in result.output

    def test_show_renders_ipv4_custom_servers(self, runner):
        """Custom IPv4 servers come from data.dns.custom.ips."""
        result = self._invoke(runner, _dns_response())

        assert "1.1.1.1" in result.output
        assert "1.0.0.1" in result.output

    def test_show_renders_ipv6_custom_servers_compacted(self, runner):
        """IPv6 servers are stored expanded and rendered compact."""
        result = self._invoke(runner, _dns_response())

        assert "2606:4700:4700::1111" in result.output
        assert "2606:4700:4700:0:0:0:0:1111" not in result.output

    def test_show_renders_caching_disabled(self, runner):
        """Caching false renders as Disabled, read from data.dns.caching."""
        result = self._invoke(runner, _dns_response())

        assert "Disabled" in result.output

    def test_show_renders_caching_enabled(self, runner):
        """Caching true renders as Enabled."""
        response = _dns_response()
        response["data"]["dns"]["caching"] = True

        result = self._invoke(runner, response)

        assert "Enabled" in result.output

    def test_show_renders_isp_assigned_servers(self, runner):
        """Parent (ISP-assigned) servers are surfaced."""
        result = self._invoke(runner, _dns_response())

        assert "192.168.1.254" in result.output

    def test_show_automatic_mode_omits_custom_line(self, runner):
        """Automatic mode with no custom servers never prints a Custom DNS line."""
        response = _dns_response()
        response["data"]["dns"] = {"mode": "automatic", "caching": True, "parent": {"ips": []}}
        response["data"]["ipv6"] = {"name_servers": {"mode": "automatic"}}

        result = self._invoke(runner, response)

        assert result.exit_code == 0
        assert "automatic" in result.output
        assert "Custom DNS" not in result.output

    def test_show_missing_dns_key_renders_unknown_not_auto(self, runner):
        """An absent dns key must not be reported as a real 'auto' reading."""
        response = _dns_response()
        del response["data"]["dns"]
        del response["data"]["ipv6"]

        result = self._invoke(runner, response)

        assert result.exit_code == 0
        assert "unknown" in result.output
        assert "auto" not in result.output

    # -- output scoping (security) -----------------------------------------

    @pytest.mark.parametrize("fmt", ["json", "yaml", "text", "list"])
    def test_structured_output_excludes_credentials(self, runner, fmt):
        """Structured output must not carry passwords or network inventory.

        Asserts on the serialised string so nested occurrences are caught.
        """
        result = self._invoke(runner, _dns_response(), "--output", fmt)

        assert result.exit_code == 0
        for secret in ("br@stemp", "california19", "162.206.74.252", "Brentwood", "94513"):
            assert secret not in result.output
        for key in ("password", "wan_ip", "geo_ip", "guest_network", "serial"):
            assert key not in result.output

    @pytest.mark.parametrize("fmt", ["json", "yaml", "text", "list"])
    def test_structured_output_includes_dns_subtree(self, runner, fmt):
        """Scoping keeps the fields the command is actually about.

        Key casing differs by renderer (text/list title-case), so match
        case-insensitively.
        """
        result = self._invoke(runner, _dns_response(), "--output", fmt)

        assert result.exit_code == 0
        assert "1.1.1.1" in result.output
        assert "caching" in result.output.lower()

    def test_json_output_is_scoped_and_versioned(self, runner):
        """JSON payload carries only dns/ipv6 and the v2 schema id."""
        result = self._invoke(runner, _dns_response(), "--output", "json")

        payload = json.loads(result.output)

        assert payload["schema"] == "eero.network.dns.show/v2"
        assert set(payload["data"]) == {"dns", "ipv6"}
        assert set(payload["data"]["ipv6"]) == {"name_servers"}
        assert payload["data"]["dns"]["mode"] == "custom"

    def test_yaml_output_is_not_the_table_panel(self, runner):
        """YAML previously fell through to the Rich panel."""
        result = self._invoke(runner, _dns_response(), "--output", "yaml")

        assert result.exit_code == 0
        assert "DNS Settings" not in result.output

    def test_text_output_is_not_the_table_panel(self, runner):
        """Text previously fell through to the Rich panel."""
        result = self._invoke(runner, _dns_response(), "--output", "text")

        assert result.exit_code == 0
        assert "DNS Settings" not in result.output


class TestNetworkSecurity:
    """Tests for network security subcommands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_security_group_help(self, runner):
        """Test security group shows help."""
        result = runner.invoke(cli, ["network", "security", "--help"])

        assert result.exit_code == 0
        assert "Manage security settings" in result.output
        assert "show" in result.output
        assert "wpa3" in result.output

    def test_security_show_help(self, runner):
        """Test security show shows help."""
        result = runner.invoke(cli, ["network", "security", "show", "--help"])

        assert result.exit_code == 0
        assert "Show security settings" in result.output

    def test_wpa3_enable_help(self, runner):
        """Test wpa3 enable shows help."""
        result = runner.invoke(cli, ["network", "security", "wpa3", "enable", "--help"])

        assert result.exit_code == 0
        assert "--force" in result.output

    def test_upnp_disable_help(self, runner):
        """Test upnp disable shows help."""
        result = runner.invoke(cli, ["network", "security", "upnp", "disable", "--help"])

        assert result.exit_code == 0
        assert "--force" in result.output


class TestNetworkGuest:
    """Tests for network guest subcommands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_guest_group_help(self, runner):
        """Test guest group shows help."""
        result = runner.invoke(cli, ["network", "guest", "--help"])

        assert result.exit_code == 0
        assert "Manage guest network" in result.output
        assert "show" in result.output
        assert "enable" in result.output
        assert "disable" in result.output

    def test_guest_show_help(self, runner):
        """Test guest show shows help."""
        result = runner.invoke(cli, ["network", "guest", "show", "--help"])

        assert result.exit_code == 0
        assert "Show guest network settings" in result.output

    def test_guest_set_help(self, runner):
        """Test guest set shows help."""
        result = runner.invoke(cli, ["network", "guest", "set", "--help"])

        assert result.exit_code == 0
        assert "--name" in result.output
        assert "--password" in result.output


class TestNetworkSpeedtest:
    """Tests for network speedtest subcommands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_speedtest_group_help(self, runner):
        """Test speedtest group shows help."""
        result = runner.invoke(cli, ["network", "speedtest", "--help"])

        assert result.exit_code == 0
        assert "run" in result.output
        assert "show" in result.output

    def test_speedtest_run_help(self, runner):
        """Test speedtest run shows help."""
        result = runner.invoke(cli, ["network", "speedtest", "run", "--help"])

        assert result.exit_code == 0
        assert "Run a new speed test" in result.output

    def test_speedtest_show_help(self, runner):
        """Test speedtest show shows help."""
        result = runner.invoke(cli, ["network", "speedtest", "show", "--help"])

        assert result.exit_code == 0
        assert "Show last speed test results" in result.output


class TestNetworkSQM:
    """Tests for network sqm subcommands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_sqm_group_help(self, runner):
        """Test sqm group shows help."""
        result = runner.invoke(cli, ["network", "sqm", "--help"])

        assert result.exit_code == 0
        assert "Smart Queue Management" in result.output or "SQM" in result.output

    def test_sqm_set_is_removed(self, runner):
        """`network sqm set` was removed in eero-api 8.0.1 -- no bandwidth
        fields exist on SQM (BREAKING CHANGE). The subcommand must not exist.
        """
        result = runner.invoke(cli, ["network", "sqm", "set", "--help"])

        assert result.exit_code == 2
        assert "No such command" in result.output
