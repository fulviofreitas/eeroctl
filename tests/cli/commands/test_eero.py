"""Unit tests for eero.cli.commands.eero module.

Tests cover:
- eero list command
- eero show command
- eero reboot command
- eero led subcommands
- eero nightlight subcommands
- eero updates subcommands
"""

import pytest
from click.testing import CliRunner

from eero_cli.main import cli


class TestEeroGroup:
    """Tests for the eero command group."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_eero_help(self, runner):
        """Test eero group shows help."""
        result = runner.invoke(cli, ["eero", "--help"])

        assert result.exit_code == 0
        assert "Manage Eero mesh nodes" in result.output
        assert "list" in result.output
        assert "show" in result.output
        assert "reboot" in result.output
        assert "led" in result.output
        assert "nightlight" in result.output
        assert "updates" in result.output


class TestEeroList:
    """Tests for eero list command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_eero_list_help(self, runner):
        """Test eero list shows help."""
        result = runner.invoke(cli, ["eero", "list", "--help"])

        assert result.exit_code == 0
        assert "List all Eero mesh nodes" in result.output


class TestEeroShow:
    """Tests for eero show command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_eero_show_help(self, runner):
        """Test eero show shows help."""
        result = runner.invoke(cli, ["eero", "show", "--help"])

        assert result.exit_code == 0
        assert "Show details of a specific Eero node" in result.output
        assert "EERO_ID" in result.output

    def test_eero_show_requires_argument(self, runner):
        """Test eero show requires eero ID argument."""
        result = runner.invoke(cli, ["eero", "show"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output


class TestEeroReboot:
    """Tests for eero reboot command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_eero_reboot_help(self, runner):
        """Test eero reboot shows help."""
        result = runner.invoke(cli, ["eero", "reboot", "--help"])

        assert result.exit_code == 0
        assert "Reboot an Eero node" in result.output
        assert "--force" in result.output

    def test_eero_reboot_requires_argument(self, runner):
        """Test eero reboot requires eero ID argument."""
        result = runner.invoke(cli, ["eero", "reboot"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output


class TestEeroLED:
    """Tests for eero led subcommands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_led_group_help(self, runner):
        """Test led group shows help."""
        result = runner.invoke(cli, ["eero", "led", "--help"])

        assert result.exit_code == 0
        assert "Manage LED settings" in result.output
        assert "show" in result.output
        assert "on" in result.output
        assert "off" in result.output
        assert "brightness" in result.output

    def test_led_show_help(self, runner):
        """Test led show shows help."""
        result = runner.invoke(cli, ["eero", "led", "show", "--help"])

        assert result.exit_code == 0
        assert "Show LED status" in result.output

    def test_led_show_requires_argument(self, runner):
        """Test led show requires eero ID argument."""
        result = runner.invoke(cli, ["eero", "led", "show"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_led_on_help(self, runner):
        """Test led on shows help."""
        result = runner.invoke(cli, ["eero", "led", "on", "--help"])

        assert result.exit_code == 0
        assert "Turn LED on" in result.output

    def test_led_off_help(self, runner):
        """Test led off shows help."""
        result = runner.invoke(cli, ["eero", "led", "off", "--help"])

        assert result.exit_code == 0
        assert "Turn LED off" in result.output

    def test_led_brightness_help(self, runner):
        """Test led brightness shows help."""
        result = runner.invoke(cli, ["eero", "led", "brightness", "--help"])

        assert result.exit_code == 0
        assert "Set LED brightness" in result.output
        assert "0-100" in result.output

    def test_led_brightness_requires_arguments(self, runner):
        """Test led brightness requires both arguments."""
        result = runner.invoke(cli, ["eero", "led", "brightness", "eero_id"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_led_brightness_validates_range(self, runner):
        """Test led brightness validates 0-100 range."""
        result = runner.invoke(cli, ["eero", "led", "brightness", "eero_id", "150"])

        assert result.exit_code != 0
        # Should reject value outside range


class TestEeroNightlight:
    """Tests for eero nightlight subcommands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_nightlight_group_help(self, runner):
        """Test nightlight group shows help."""
        result = runner.invoke(cli, ["eero", "nightlight", "--help"])

        assert result.exit_code == 0
        assert "nightlight" in result.output.lower()
        assert "Beacon" in result.output or "beacon" in result.output.lower()

    def test_nightlight_show_help(self, runner):
        """Test nightlight show shows help."""
        result = runner.invoke(cli, ["eero", "nightlight", "show", "--help"])

        assert result.exit_code == 0
        assert "Show nightlight settings" in result.output

    def test_nightlight_schedule_help(self, runner):
        """Test nightlight schedule shows help."""
        result = runner.invoke(cli, ["eero", "nightlight", "schedule", "--help"])

        assert result.exit_code == 0
        assert "Set nightlight schedule" in result.output
        assert "--on-time" in result.output
        assert "--off-time" in result.output


class TestEeroUpdates:
    """Tests for eero updates subcommands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_updates_group_help(self, runner):
        """Test updates group shows help."""
        result = runner.invoke(cli, ["eero", "updates", "--help"])

        assert result.exit_code == 0
        assert "Manage updates" in result.output
        assert "show" in result.output
        assert "check" in result.output

    def test_updates_show_help(self, runner):
        """Test updates show shows help."""
        result = runner.invoke(cli, ["eero", "updates", "show", "--help"])

        assert result.exit_code == 0
        assert "Show update status" in result.output

    def test_updates_check_help(self, runner):
        """Test updates check shows help."""
        result = runner.invoke(cli, ["eero", "updates", "check", "--help"])

        assert result.exit_code == 0
        assert "Check for available updates" in result.output
