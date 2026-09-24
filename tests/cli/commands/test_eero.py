"""Unit tests for eero.cli.commands.eero module.

Tests cover:
- eero list command
- eero show command
- eero reboot command
- eero led subcommands
- eero nightlight subcommands
- eero updates subcommands
"""

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.main import cli


def _mock_client(**method_returns):
    """An AsyncMock EeroClient wired for `eeroctl.utils.EeroClient` patching."""
    client = AsyncMock()
    for name, value in method_returns.items():
        setattr(client, name, AsyncMock(return_value=value))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


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
        """Test nightlight schedule shows help.

        `--on-time`/`--off-time` were renamed to `--on`/`--off` (Q4,
        BREAKING CHANGE); `--schedule-json` and `--disable` were added.
        """
        result = runner.invoke(cli, ["eero", "nightlight", "schedule", "--help"])

        assert result.exit_code == 0
        assert "--on " in result.output or "--on TEXT" in result.output
        assert "--off " in result.output or "--off TEXT" in result.output
        assert "--disable" in result.output
        assert "--schedule-json" in result.output
        assert "--on-time" not in result.output
        assert "--off-time" not in result.output


class TestEeroLEDBrightnessBehavior:
    """CLI-behavioural tests for `eero led brightness` (v8 call shape)."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_out_of_range_exits_usage_error_before_any_client_call(self, runner):
        """`101` is rejected by click.IntRange(0, 100) during parsing -- no
        client is ever constructed and no confirmation prompt is shown."""
        with patch("eeroctl.utils.EeroClient") as mock_client_class:
            result = runner.invoke(cli, ["eero", "led", "brightness", "123", "101"], input="")

        assert result.exit_code == 2
        mock_client_class.assert_not_called()


class TestEeroNightlightBrightnessBehavior:
    """CLI-behavioural tests for `eero nightlight brightness` (v8 call shape)."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_awaits_set_nightlight_brightness_with_exact_args(self, runner):
        """`set_nightlight_brightness(eero_id, brightness_percentage, network_id)`
        is the real facade signature on eero-api 8.0.1 (client.py:1920);
        this pins the exact positional shape `nightlight_brightness` passes.
        """
        mock_client = _mock_client(
            get_eero={"meta": {"code": 200}, "data": {"id": "123", "url": "/2.2/eeros/123"}},
            set_nightlight_brightness={"meta": {"code": 200}, "data": {}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["-n", "111111", "eero", "nightlight", "brightness", "123", "40"]
            )

        assert result.exit_code == 0, result.output
        mock_client.set_nightlight_brightness.assert_awaited_once_with("123", 40, "111111")

    def test_out_of_range_exits_usage_error_before_any_client_call(self, runner):
        """`101` is rejected by click.IntRange(0, 100) during parsing -- no
        client is ever constructed and no confirmation prompt is shown."""
        with patch("eeroctl.utils.EeroClient") as mock_client_class:
            result = runner.invoke(
                cli, ["eero", "nightlight", "brightness", "123", "101"], input=""
            )

        assert result.exit_code == 2
        mock_client_class.assert_not_called()


class TestEeroNightlightShowRendersBothShapes:
    """`get_nightlight` now GETs the `data.nightlight.url` sub-resource and
    returns the nightlight object itself, so settings usually live at
    `data.*`; the view must still tolerate the old `data.nightlight.*` shape
    (migration plan §2.7, unverified -- no Beacon available)."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_renders_flat_data_shape(self, runner):
        mock_client = _mock_client(
            get_eero={"meta": {"code": 200}, "data": {"id": "123", "url": "/2.2/eeros/123"}},
            get_nightlight={
                "meta": {"code": 200},
                "data": {"enabled": True, "brightness": 55},
            },
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["-n", "111111", "eero", "nightlight", "show", "123"])

        assert result.exit_code == 0, result.output
        assert "55" in result.output
        assert "Yes" in result.output

    def test_renders_nested_nightlight_shape(self, runner):
        mock_client = _mock_client(
            get_eero={"meta": {"code": 200}, "data": {"id": "123", "url": "/2.2/eeros/123"}},
            get_nightlight={
                "meta": {"code": 200},
                "data": {"nightlight": {"enabled": False, "brightness": 20}},
            },
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["-n", "111111", "eero", "nightlight", "show", "123"])

        assert result.exit_code == 0, result.output
        assert "20" in result.output
        assert "No" in result.output


class TestEeroNightlightScheduleBehavior:
    """`nightlight schedule --on/--off` builds the v7 schedule
    shape and forwards it verbatim (migration plan Q4, unverified)."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_passes_v7_schedule_shape(self, runner):
        mock_client = _mock_client(
            get_eero={"meta": {"code": 200}, "data": {"id": "123", "url": "/2.2/eeros/123"}},
            set_nightlight_schedule={"meta": {"code": 200}, "data": {}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "-n",
                    "111111",
                    "eero",
                    "nightlight",
                    "schedule",
                    "123",
                    "--on",
                    "20:00",
                    "--off",
                    "06:00",
                ],
            )

        assert result.exit_code == 0, result.output
        mock_client.set_nightlight_schedule.assert_awaited_once_with(
            "123", {"enabled": True, "on": "20:00", "off": "06:00"}, "111111"
        )


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
