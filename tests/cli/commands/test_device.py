"""Unit tests for eero.cli.commands.device module.

Tests cover:
- device list command
- device show command
- device rename command
- device block/unblock commands
- device pause/unpause commands
- device transformer regression (blacklisted field)
"""

import re
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.main import cli

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _plain(text: str) -> str:
    """Strip ANSI escapes and collapse whitespace from Rich console output.

    Rich wraps to the console width even under CliRunner and re-applies
    styling per wrapped line, so a substring straddling a wrap point is
    broken up by escape codes and whitespace otherwise.
    """
    return re.sub(r"\s+", " ", _ANSI_RE.sub("", text))


class TestDeviceGroup:
    """Tests for the device command group."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_device_help(self, runner):
        """Test device group shows help."""
        result = runner.invoke(cli, ["device", "--help"])

        assert result.exit_code == 0
        assert "Manage connected devices" in result.output
        assert "list" in result.output
        assert "show" in result.output
        assert "rename" in result.output
        assert "block" in result.output
        assert "unblock" in result.output
        assert "pause" in result.output
        assert "unpause" in result.output

    def test_device_help_no_priority(self, runner):
        """Test device group help does not mention priority."""
        result = runner.invoke(cli, ["device", "--help"])

        assert result.exit_code == 0
        assert "priority" not in result.output


class TestDeviceList:
    """Tests for device list command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_device_list_help(self, runner):
        """Test device list shows help."""
        result = runner.invoke(cli, ["device", "list", "--help"])

        assert result.exit_code == 0
        assert "List all connected devices" in result.output


class TestDeviceShow:
    """Tests for device show command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_device_show_help(self, runner):
        """Test device show shows help."""
        result = runner.invoke(cli, ["device", "show", "--help"])

        assert result.exit_code == 0
        assert "Show details of a specific device" in result.output
        assert "DEVICE_ID" in result.output

    def test_device_show_requires_argument(self, runner):
        """Test device show requires device ID argument."""
        result = runner.invoke(cli, ["device", "show"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output


class TestDeviceRename:
    """Tests for device rename command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_device_rename_help(self, runner):
        """Test device rename shows help."""
        result = runner.invoke(cli, ["device", "rename", "--help"])

        assert result.exit_code == 0
        assert "Rename a device" in result.output
        assert "--name" in result.output

    def test_device_rename_requires_argument(self, runner):
        """Test device rename requires device ID argument."""
        result = runner.invoke(cli, ["device", "rename", "--name", "New Name"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_device_rename_requires_name_option(self, runner):
        """Test device rename requires --name option."""
        result = runner.invoke(cli, ["device", "rename", "device_id"])

        assert result.exit_code != 0
        assert "Missing option" in result.output or "--name" in result.output


class TestDeviceBlock:
    """Tests for device block command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_device_block_help(self, runner):
        """Test device block shows help."""
        result = runner.invoke(cli, ["device", "block", "--help"])

        assert result.exit_code == 0
        assert "Block a device" in result.output
        assert "--force" in result.output

    def test_device_block_requires_argument(self, runner):
        """Test device block requires device ID argument."""
        result = runner.invoke(cli, ["device", "block"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_device_block_calls_block_device(self, runner):
        """Test device block calls client.block_device with correct args."""
        mock_devices_response = {
            "meta": {"code": 200},
            "data": [
                {
                    "url": "/2.2/networks/net1/devices/dev1",
                    "mac": "AA:BB:CC:DD:EE:FF",
                    "nickname": "MyPhone",
                    "hostname": "myphone",
                    "connected": True,
                    "blacklisted": False,
                    "paused": False,
                }
            ],
        }
        mock_block_response = {"meta": {"code": 200}, "data": {}}

        mock_client = AsyncMock()
        mock_client.get_devices = AsyncMock(return_value=mock_devices_response)
        mock_client.block_device = AsyncMock(return_value=mock_block_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["device", "block", "MyPhone", "--force"])

        assert result.exit_code == 0
        # write_if_changed's generic acceptance message replaced the old
        # command-specific "Device blocked" text (safety §3.2 item 4).
        assert "accepted" in result.output.lower()
        # eero-api 8.0.1 split block/unblock into two methods; neither takes a
        # bare `blocked: bool` positional anymore (device.py:358).
        mock_client.block_device.assert_awaited_once()
        call_args = mock_client.block_device.call_args
        assert len(call_args[0]) == 2  # (device_id, network_id) -- no blocked bool


class TestDeviceUnblock:
    """Tests for device unblock command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_device_unblock_help(self, runner):
        """Test device unblock shows help."""
        result = runner.invoke(cli, ["device", "unblock", "--help"])

        assert result.exit_code == 0
        assert "Unblock a device" in result.output
        assert "--force" in result.output

    def test_device_unblock_requires_argument(self, runner):
        """Test device unblock requires device ID argument."""
        result = runner.invoke(cli, ["device", "unblock"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output


class TestDevicePause:
    """Tests for device pause command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_device_pause_help(self, runner):
        """Test device pause shows help."""
        result = runner.invoke(cli, ["device", "pause", "--help"])

        assert result.exit_code == 0
        assert "Pause a device" in result.output
        assert "--force" in result.output

    def test_device_pause_requires_argument(self, runner):
        """Test device pause requires device ID argument."""
        result = runner.invoke(cli, ["device", "pause"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_device_pause_calls_pause_device(self, runner):
        """Test device pause calls client.pause_device with paused=True."""
        mock_devices_response = {
            "meta": {"code": 200},
            "data": [
                {
                    "url": "/2.2/networks/net1/devices/dev1",
                    "mac": "AA:BB:CC:DD:EE:FF",
                    "nickname": "MyPhone",
                    "hostname": "myphone",
                    "connected": True,
                    "blacklisted": False,
                    "paused": False,
                }
            ],
        }
        mock_pause_response = {"meta": {"code": 200}, "data": {}}

        mock_client = AsyncMock()
        mock_client.get_devices = AsyncMock(return_value=mock_devices_response)
        mock_client.pause_device = AsyncMock(return_value=mock_pause_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["device", "pause", "MyPhone", "--force"])

        assert result.exit_code == 0
        assert "accepted" in result.output.lower()
        mock_client.pause_device.assert_awaited_once()
        call_args = mock_client.pause_device.call_args
        assert call_args[0][1] is True  # paused=True

    def test_device_pause_passes_network_id(self, runner):
        """Test device pause passes network_id to pause_device."""
        mock_devices_response = {
            "meta": {"code": 200},
            "data": [
                {
                    "url": "/2.2/networks/net1/devices/dev1",
                    "mac": "AA:BB:CC:DD:EE:FF",
                    "nickname": "Tablet",
                    "hostname": "tablet",
                    "connected": True,
                    "blacklisted": False,
                    "paused": False,
                }
            ],
        }
        mock_pause_response = {"meta": {"code": 200}, "data": {}}

        mock_client = AsyncMock()
        mock_client.get_devices = AsyncMock(return_value=mock_devices_response)
        mock_client.pause_device = AsyncMock(return_value=mock_pause_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["device", "pause", "Tablet", "--force", "--network-id", "mynet123"]
            )

        assert result.exit_code == 0
        call_args = mock_client.pause_device.call_args
        # Third positional arg is network_id
        assert call_args[0][2] == "mynet123"


class TestDeviceUnpause:
    """Tests for device unpause command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_device_unpause_help(self, runner):
        """Test device unpause shows help."""
        result = runner.invoke(cli, ["device", "unpause", "--help"])

        assert result.exit_code == 0
        assert "Unpause a device" in result.output
        assert "--force" in result.output

    def test_device_unpause_requires_argument(self, runner):
        """Test device unpause requires device ID argument."""
        result = runner.invoke(cli, ["device", "unpause"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_device_unpause_calls_pause_device_false(self, runner):
        """Test device unpause calls client.pause_device with paused=False."""
        mock_devices_response = {
            "meta": {"code": 200},
            "data": [
                {
                    "url": "/2.2/networks/net1/devices/dev1",
                    "mac": "AA:BB:CC:DD:EE:FF",
                    "nickname": "MyLaptop",
                    "hostname": "mylaptop",
                    "connected": True,
                    "blacklisted": False,
                    "paused": True,
                }
            ],
        }
        mock_unpause_response = {"meta": {"code": 200}, "data": {}}

        mock_client = AsyncMock()
        mock_client.get_devices = AsyncMock(return_value=mock_devices_response)
        mock_client.pause_device = AsyncMock(return_value=mock_unpause_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["device", "unpause", "MyLaptop", "--force"])

        assert result.exit_code == 0
        assert "accepted" in result.output.lower()
        mock_client.pause_device.assert_awaited_once()
        call_args = mock_client.pause_device.call_args
        assert call_args[0][1] is False  # paused=False


class TestDeviceTransformerRegression:
    """Regression tests for #106 — blacklisted field in transformer."""

    def test_blacklisted_true_maps_to_blocked_true(self):
        """Raw dict with blacklisted=True must yield blocked=True and blacklisted=True."""
        from eeroctl.transformers.device import normalize_device

        raw = {
            "url": "/2.2/networks/net1/devices/dev1",
            "mac": "AA:BB:CC:DD:EE:FF",
            "blacklisted": True,
            "paused": False,
            "connected": True,
        }
        result = normalize_device(raw)

        assert result["blocked"] is True
        assert result["blacklisted"] is True

    def test_blacklisted_false_maps_to_blocked_false(self):
        """Raw dict with blacklisted=False must yield blocked=False."""
        from eeroctl.transformers.device import normalize_device

        raw = {
            "url": "/2.2/networks/net1/devices/dev1",
            "mac": "AA:BB:CC:DD:EE:FF",
            "blacklisted": False,
            "paused": False,
            "connected": True,
        }
        result = normalize_device(raw)

        assert result["blocked"] is False
        assert result["blacklisted"] is False

    def test_missing_blacklisted_defaults_to_false(self):
        """Raw dict with no blacklisted key must default blocked/blacklisted to False."""
        from eeroctl.transformers.device import normalize_device

        raw = {
            "url": "/2.2/networks/net1/devices/dev1",
            "mac": "AA:BB:CC:DD:EE:FF",
            "paused": False,
            "connected": True,
        }
        result = normalize_device(raw)

        assert result["blocked"] is False
        assert result["blacklisted"] is False

    def test_no_spurious_blocked_field_is_not_used(self):
        """A raw dict with only 'blocked' (wrong field) must NOT propagate as blocked=True."""
        from eeroctl.transformers.device import normalize_device

        raw = {
            "url": "/2.2/networks/net1/devices/dev1",
            "mac": "AA:BB:CC:DD:EE:FF",
            "blocked": True,  # wrong SDK field; SDK uses 'blacklisted'
            "paused": False,
            "connected": True,
        }
        result = normalize_device(raw)

        # 'blacklisted' key absent → blocked and blacklisted should both be False
        assert result["blocked"] is False
        assert result["blacklisted"] is False


# ---------------------------------------------------------------------------
# TestSkipUnchangedAndReadCommandHints
# ---------------------------------------------------------------------------


class TestSkipUnchangedAndReadCommandHints:
    """Integration coverage for the ``write_if_changed`` skip-unchanged path
    and the per-command ``read_command`` hint (migration plan §3.2 item 4,
    §3.3) for ``device unblock``/``device pause`` and ``eero led
    on``/``off`` -- registered write commands that skip an unchanged state
    using the target already fetched by ``get_devices``/``get_led_status``.

    ``eero led`` lives outside the ``device`` command tree, but is covered
    here rather than in a new file since this commit's file list is
    ``test_network_mutations.py``, ``test_device.py`` and
    ``test_warning_filter.py``.

    Uses the SDK-boundary mock (``eeroctl.utils.EeroClient``), matching the
    pattern already established by ``TestDeviceBlock``/``TestDevicePause``
    above, not a ``run_with_client`` patch.
    """

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    @staticmethod
    def _devices_response(*, blacklisted: bool, paused: bool):
        return {
            "meta": {"code": 200},
            "data": [
                {
                    "url": "/2.2/networks/net1/devices/dev1",
                    "mac": "AA:BB:CC:DD:EE:FF",
                    "nickname": "MyPhone",
                    "hostname": "myphone",
                    "connected": True,
                    "blacklisted": blacklisted,
                    "paused": paused,
                }
            ],
        }

    # -- device unblock ---------------------------------------------------

    def test_device_unblock_already_configured_skips_the_write(self, runner):
        """Already unblocked (blacklisted=False): a plain Y confirms
        (device unblock is MEDIUM, verified), but the write is skipped."""
        mock_client = AsyncMock()
        mock_client.get_devices = AsyncMock(
            return_value=self._devices_response(blacklisted=False, paused=False)
        )
        mock_client.unblock_device = AsyncMock(return_value={"meta": {"code": 200}, "data": {}})
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["device", "unblock", "MyPhone"], input="y\n")

        assert result.exit_code == 0
        mock_client.unblock_device.assert_not_awaited()
        plain_output = _plain(result.output)
        assert "already" in plain_output.lower()
        assert "eero device list" in plain_output

    def test_device_unblock_changed_state_writes_and_hints_read_command(self, runner):
        """Currently blocked (blacklisted=True): unblock writes and hints
        the read command to verify with."""
        mock_client = AsyncMock()
        mock_client.get_devices = AsyncMock(
            return_value=self._devices_response(blacklisted=True, paused=False)
        )
        mock_client.unblock_device = AsyncMock(return_value={"meta": {"code": 200}, "data": {}})
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["device", "unblock", "MyPhone", "--force"])

        assert result.exit_code == 0
        mock_client.unblock_device.assert_awaited_once()
        assert "verify with `eero device list`" in _plain(result.output).lower()

    # -- device pause -----------------------------------------------------

    def test_device_pause_already_configured_skips_the_write(self, runner):
        """Already paused: the write is skipped."""
        mock_client = AsyncMock()
        mock_client.get_devices = AsyncMock(
            return_value=self._devices_response(blacklisted=False, paused=True)
        )
        mock_client.pause_device = AsyncMock(return_value={"meta": {"code": 200}, "data": {}})
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["device", "pause", "MyPhone"], input="y\n")

        assert result.exit_code == 0
        mock_client.pause_device.assert_not_awaited()
        plain_output = _plain(result.output)
        assert "already" in plain_output.lower()
        assert "eero device list" in plain_output

    def test_device_pause_changed_state_writes_and_hints_read_command(self, runner):
        """Not yet paused: pause writes and hints the read command."""
        mock_client = AsyncMock()
        mock_client.get_devices = AsyncMock(
            return_value=self._devices_response(blacklisted=False, paused=False)
        )
        mock_client.pause_device = AsyncMock(return_value={"meta": {"code": 200}, "data": {}})
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["device", "pause", "MyPhone", "--force"])

        assert result.exit_code == 0
        mock_client.pause_device.assert_awaited_once()
        assert "verify with `eero device list`" in _plain(result.output).lower()

    # -- eero led on/off ----------------------------------------------------

    @staticmethod
    def _led_client(*, led_on: bool):
        mock_client = AsyncMock()
        # "123" is numeric, so resolve_eero_identifier resolves it directly
        # via get_eero rather than searching get_eeros.
        mock_client.get_eero = AsyncMock(
            return_value={
                "meta": {"code": 200},
                "data": {"url": "/2.2/networks/net1/eeros/123", "id": "123"},
            }
        )
        mock_client.get_led_status = AsyncMock(
            return_value={"meta": {"code": 200}, "data": {"led_on": led_on}}
        )
        mock_client.set_led = AsyncMock(return_value={"meta": {"code": 200}, "data": {}})
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        return mock_client

    def test_led_on_already_configured_skips_the_write(self, runner):
        """LED already on: no prompt (LOW risk), and the write is skipped."""
        mock_client = self._led_client(led_on=True)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["eero", "led", "on", "123"])

        assert result.exit_code == 0
        mock_client.set_led.assert_not_awaited()
        plain_output = _plain(result.output)
        assert "already" in plain_output.lower()
        assert "eero eero led show" in plain_output

    def test_led_off_changed_state_writes_and_hints_read_command(self, runner):
        """LED currently on: `led off` writes and hints the read command."""
        mock_client = self._led_client(led_on=True)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["eero", "led", "off", "123"])

        assert result.exit_code == 0
        mock_client.set_led.assert_awaited_once_with("123", False, None)
        assert "verify with `eero eero led show`" in _plain(result.output).lower()

    def test_device_unblock_output_json_leaves_stdout_json_safe(self, runner):
        """--output json --force on a device write: same stdout-safety
        contract as the network-family test in test_network_mutations.py
        (device unblock, device.py:~393)."""
        import json

        mock_client = AsyncMock()
        mock_client.get_devices = AsyncMock(
            return_value=self._devices_response(blacklisted=True, paused=False)
        )
        mock_client.unblock_device = AsyncMock(return_value={"meta": {"code": 200}, "data": {}})
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", "json", "device", "unblock", "MyPhone", "--force"]
            )

        assert result.exit_code == 0
        if result.stdout:
            json.loads(result.stdout)
        assert "Write accepted" not in result.stdout
        assert "verify with" not in result.stdout.lower()
