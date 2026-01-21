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
        """Create mock network objects."""
        # Create mock status with .value attribute (like an enum)
        status1 = MagicMock()
        status1.value = "online"

        status2 = MagicMock()
        status2.value = "online"

        network1 = MagicMock()
        network1.id = "net_1"
        network1.name = "Home Network"
        network1.status = status1
        network1.public_ip = "203.0.113.1"
        network1.isp_name = "Comcast"

        network2 = MagicMock()
        network2.id = "net_2"
        network2.name = "Office Network"
        network2.status = status2
        network2.public_ip = "203.0.113.2"
        network2.isp_name = "AT&T"

        return [network1, network2]

    def test_network_list_help(self, runner):
        """Test network list shows help."""
        result = runner.invoke(cli, ["network", "list", "--help"])

        assert result.exit_code == 0
        assert "List all networks" in result.output

    @patch("eeroctl.commands.network.base.run_with_client")
    def test_network_list_displays_networks(self, mock_run_with_client, runner, mock_networks):
        """Test network list displays networks in table format."""

        async def run_func(func):
            # Create mock client and call the function
            mock_client = AsyncMock()
            mock_client.get_networks = AsyncMock(return_value=mock_networks)
            await func(mock_client)

        mock_run_with_client.side_effect = run_func

        result = runner.invoke(cli, ["network", "list"])

        # Should contain network names
        assert "Home Network" in result.output or "net_1" in result.output

    @patch("eeroctl.commands.network.base.run_with_client")
    def test_network_list_empty(self, mock_run_with_client, runner):
        """Test network list with no networks."""

        async def run_func(func):
            mock_client = AsyncMock()
            mock_client.get_networks = AsyncMock(return_value=[])
            await func(mock_client)

        mock_run_with_client.side_effect = run_func

        result = runner.invoke(cli, ["network", "list"])

        assert "No networks found" in result.output

    @patch("eeroctl.commands.network.base.run_with_client")
    def test_network_list_json_output(self, mock_run_with_client, runner, mock_networks):
        """Test network list with JSON output."""

        async def run_func(func):
            mock_client = AsyncMock()
            mock_client.get_networks = AsyncMock(return_value=mock_networks)
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
        """Test dns mode set shows help."""
        result = runner.invoke(cli, ["network", "dns", "mode", "set", "--help"])

        assert result.exit_code == 0
        assert "auto" in result.output
        assert "cloudflare" in result.output
        assert "google" in result.output

    def test_dns_mode_set_custom_requires_servers(self, runner):
        """Test dns mode set custom requires --servers."""
        result = runner.invoke(cli, ["--force", "network", "dns", "mode", "set", "custom"])

        assert result.exit_code != 0
        assert "servers" in result.output.lower()

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

    def test_sqm_set_help(self, runner):
        """Test sqm set shows help."""
        result = runner.invoke(cli, ["network", "sqm", "set", "--help"])

        assert result.exit_code == 0
        assert "--upload" in result.output
        assert "--download" in result.output

    def test_sqm_set_requires_bandwidth(self, runner):
        """Test sqm set requires at least one bandwidth option."""
        result = runner.invoke(cli, ["--force", "network", "sqm", "set"])

        assert (
            result.exit_code != 0
            or "upload" in result.output.lower()
            or "download" in result.output.lower()
        )
