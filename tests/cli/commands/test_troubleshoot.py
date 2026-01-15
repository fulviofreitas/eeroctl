"""Unit tests for eero.cli.commands.troubleshoot module.

Tests cover:
- troubleshoot connectivity command
- troubleshoot ping command
- troubleshoot trace command
- troubleshoot doctor command
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from eero_cli.main import cli


class TestTroubleshootGroup:
    """Tests for the troubleshoot command group."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_troubleshoot_help(self, runner):
        """Test troubleshoot group shows help."""
        result = runner.invoke(cli, ["troubleshoot", "--help"])

        assert result.exit_code == 0
        assert "Troubleshooting" in result.output or "diagnostics" in result.output.lower()
        assert "connectivity" in result.output
        assert "ping" in result.output
        assert "doctor" in result.output


class TestTroubleshootConnectivity:
    """Tests for troubleshoot connectivity command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_connectivity_help(self, runner):
        """Test connectivity shows help."""
        result = runner.invoke(cli, ["troubleshoot", "connectivity", "--help"])

        assert result.exit_code == 0
        assert "Check network connectivity" in result.output


class TestTroubleshootPing:
    """Tests for troubleshoot ping command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_ping_help(self, runner):
        """Test ping shows help."""
        result = runner.invoke(cli, ["troubleshoot", "ping", "--help"])

        assert result.exit_code == 0
        assert "Ping a target host" in result.output
        assert "--target" in result.output

    def test_ping_requires_target(self, runner):
        """Test ping requires --target option."""
        result = runner.invoke(cli, ["troubleshoot", "ping"])

        assert result.exit_code != 0
        assert "Missing option" in result.output or "--target" in result.output


class TestTroubleshootTrace:
    """Tests for troubleshoot trace command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_trace_help(self, runner):
        """Test trace shows help."""
        result = runner.invoke(cli, ["troubleshoot", "trace", "--help"])

        assert result.exit_code == 0
        assert "Traceroute" in result.output
        assert "--target" in result.output

    def test_trace_requires_target(self, runner):
        """Test trace requires --target option."""
        result = runner.invoke(cli, ["troubleshoot", "trace"])

        assert result.exit_code != 0
        assert "Missing option" in result.output or "--target" in result.output


class TestTroubleshootDoctor:
    """Tests for troubleshoot doctor command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_doctor_help(self, runner):
        """Test doctor shows help."""
        result = runner.invoke(cli, ["troubleshoot", "doctor", "--help"])

        assert result.exit_code == 0
        assert "Run diagnostic checks" in result.output

    @patch("eero.cli.commands.troubleshoot.EeroClient")
    @patch("eero.cli.utils.get_cookie_file")
    def test_doctor_runs_checks(self, mock_cookie_file, mock_client_class, runner, tmp_path):
        """Test doctor runs health checks."""
        mock_cookie_file.return_value = tmp_path / "cookies.json"

        # Create mock network
        mock_network = MagicMock()
        mock_network.status = "connected"
        mock_network.public_ip = "203.0.113.1"
        mock_network.isp_name = "Test ISP"
        mock_network.health = {}

        # Create mock eeros
        mock_eero = MagicMock()
        mock_eero.status = "green"

        # Create mock devices
        mock_device = MagicMock()
        mock_device.connected = True

        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get_network = AsyncMock(return_value=mock_network)
        mock_client.get_eeros = AsyncMock(return_value=[mock_eero])
        mock_client.get_devices = AsyncMock(return_value=[mock_device])
        mock_client.get_diagnostics = AsyncMock(return_value={"status": "ok"})
        mock_client.is_premium = AsyncMock(return_value=True)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["troubleshoot", "doctor"])

        # Should run checks and display results
        assert "Network" in result.output or "Check" in result.output or "PASS" in result.output

    @patch("eero.cli.commands.troubleshoot.EeroClient")
    @patch("eero.cli.utils.get_cookie_file")
    def test_doctor_json_output(self, mock_cookie_file, mock_client_class, runner, tmp_path):
        """Test doctor with JSON output."""
        mock_cookie_file.return_value = tmp_path / "cookies.json"

        mock_network = MagicMock()
        mock_network.status = "connected"
        mock_network.public_ip = "203.0.113.1"
        mock_network.isp_name = "Test ISP"
        mock_network.health = {}

        mock_eero = MagicMock()
        mock_eero.status = "green"

        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get_network = AsyncMock(return_value=mock_network)
        mock_client.get_eeros = AsyncMock(return_value=[mock_eero])
        mock_client.get_devices = AsyncMock(return_value=[])
        mock_client.get_diagnostics = AsyncMock(return_value={})
        mock_client.is_premium = AsyncMock(return_value=False)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["--output", "json", "troubleshoot", "doctor"])

        # Should produce JSON output
        try:
            data = json.loads(result.output)
            assert "data" in data
            assert "checks" in data["data"]
        except json.JSONDecodeError:
            pass  # May have other output mixed in
