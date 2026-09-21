"""Unit tests for commit 22's phase-A reads.

Tests cover:
- eero connections <id>    (get_connections)
- eero support <id>        (get_eero_support; Q7: EeroNotFoundException ->
  "unavailable", exit 0)
- device labels show <id>  (get_device_labels, read only)
- network ouicheck <eero>  (get_ouicheck, serial/version from the eero
  envelope via resolve_eero_identifier)
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner
from eero.exceptions import (
    EeroAccessDeniedException,
    EeroNotFoundException,
    EeroPremiumRequiredException,
)

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli

# Reuse the mock-client helpers defined in test_events.py rather than
# redefining them per module (standing rule from the batch-1 test audit); a
# shared conftest fixture lands after the group-1 stack is pushed.
from .test_events import _mock_client

EEROS_RESPONSE = {
    "meta": {"code": 200},
    "data": {
        "eeros": [
            {
                "url": "/2.2/eeros/1",
                "serial": "ABC123",
                "name": "Living Room",
                "os_version": "6.20.1",
            }
        ]
    },
}
CONNECTIONS_RESPONSE = {"meta": {"code": 200}, "data": {"connections": []}}
SUPPORT_RESPONSE = {"meta": {"code": 200}, "data": {"support_id": "abc"}}
DEVICES_RESPONSE = {
    "meta": {"code": 200},
    "data": {"devices": [{"url": "/2.2/devices/1", "mac": "AA:BB:CC", "nickname": "Laptop"}]},
}
LABELS_RESPONSE = {"meta": {"code": 200}, "data": {"labels": ["kids"]}}
OUICHECK_RESPONSE = {"meta": {"code": 200}, "data": {"result": "ok"}}
EMPTY_RESPONSE = {"meta": {"code": 200}, "data": {}}


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI runner."""
    return CliRunner()


class TestEeroConnections:
    """Tests for `eero connections <id>`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["eero", "connections", "--help"])

        assert result.exit_code == 0

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_eeros=EEROS_RESPONSE, get_connections=CONNECTIONS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", output_format, "eero", "connections", "ABC123"]
            )

        assert result.exit_code == 0
        mock_client.get_connections.assert_awaited_once()

    def test_json_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(get_eeros=EEROS_RESPONSE, get_connections=CONNECTIONS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "eero", "connections", "ABC123"])

        parsed = json.loads(result.output)
        assert parsed["data"] == CONNECTIONS_RESPONSE["data"]
        assert parsed["schema"] == "eero.eero.connections/v1"

    def test_not_found_exits_5(self, runner: CliRunner):
        mock_client = _mock_client(
            get_eeros={"meta": {"code": 200}, "data": {"eeros": []}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["eero", "connections", "nonexistent"])

        assert result.exit_code == ExitCode.NOT_FOUND

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client(get_eeros=EEROS_RESPONSE)
        mock_client.get_connections = AsyncMock(
            side_effect=EeroPremiumRequiredException("Connections")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["eero", "connections", "ABC123"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        # commit 6 maps EeroAccessDeniedException directly; until then it falls
        # through the generic EeroAPIException branch's status_code == 403 check.
        mock_client = _mock_client(get_eeros=EEROS_RESPONSE)
        mock_client.get_connections = AsyncMock(
            side_effect=EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["eero", "connections", "ABC123"])

        assert result.exit_code == ExitCode.FORBIDDEN


class TestEeroSupport:
    """Tests for `eero support <id>`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["eero", "support", "--help"])

        assert result.exit_code == 0

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_eeros=EEROS_RESPONSE, get_eero_support=SUPPORT_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", output_format, "eero", "support", "ABC123"])

        assert result.exit_code == 0
        mock_client.get_eero_support.assert_awaited_once_with("ABC123")

    def test_not_found_exits_5(self, runner: CliRunner):
        mock_client = _mock_client(get_eeros={"meta": {"code": 200}, "data": {"eeros": []}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["eero", "support", "nonexistent"])

        assert result.exit_code == ExitCode.NOT_FOUND

    def test_unavailable_on_node_exits_0_with_unavailable_line(self, runner: CliRunner):
        """Q7: EeroNotFoundException from get_eero_support -> exit 0, 'unavailable'."""
        mock_client = _mock_client(get_eeros=EEROS_RESPONSE)
        mock_client.get_eero_support = AsyncMock(
            side_effect=EeroNotFoundException("eero_support", "ABC123")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["eero", "support", "ABC123"])

        assert result.exit_code == 0
        assert "unavailable" in result.output.lower()

    def test_unavailable_json_output_is_data_null(self, runner: CliRunner):
        mock_client = _mock_client(get_eeros=EEROS_RESPONSE)
        mock_client.get_eero_support = AsyncMock(
            side_effect=EeroNotFoundException("eero_support", "ABC123")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "eero", "support", "ABC123"])

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["data"] is None

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client(get_eeros=EEROS_RESPONSE)
        mock_client.get_eero_support = AsyncMock(
            side_effect=EeroPremiumRequiredException("Support")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["eero", "support", "ABC123"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED


class TestDeviceLabelsShow:
    """Tests for `device labels show <id>`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["device", "labels", "show", "--help"])

        assert result.exit_code == 0

    def test_no_set_command(self, runner: CliRunner):
        """No `device labels set` -- set_device_labels is a documented no-op write."""
        result = runner.invoke(cli, ["device", "labels", "--help"])

        assert result.exit_code == 0
        assert "set" not in result.output

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_devices=DEVICES_RESPONSE, get_device_labels=LABELS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", output_format, "device", "labels", "show", "Laptop"]
            )

        assert result.exit_code == 0
        mock_client.get_device_labels.assert_awaited_once()

    def test_json_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(get_devices=DEVICES_RESPONSE, get_device_labels=LABELS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "device", "labels", "show", "Laptop"])

        parsed = json.loads(result.output)
        assert parsed["data"] == LABELS_RESPONSE["data"]
        assert parsed["schema"] == "eero.device.labels.show/v1"

    def test_device_not_found_exits_5(self, runner: CliRunner):
        mock_client = _mock_client(get_devices={"meta": {"code": 200}, "data": {"devices": []}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["device", "labels", "show", "nonexistent"])

        assert result.exit_code == ExitCode.NOT_FOUND

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_devices=DEVICES_RESPONSE, get_device_labels=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["device", "labels", "show", "Laptop"])

        assert result.exit_code == 0


class TestNetworkOuicheck:
    """Tests for `network ouicheck <eero>`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "ouicheck", "--help"])

        assert result.exit_code == 0

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_eeros=EEROS_RESPONSE, get_ouicheck=OUICHECK_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", output_format, "network", "ouicheck", "ABC123"]
            )

        assert result.exit_code == 0
        mock_client.get_ouicheck.assert_awaited_once()

    def test_serial_and_version_forwarded_from_eero_envelope(self, runner: CliRunner):
        mock_client = _mock_client(get_eeros=EEROS_RESPONSE, get_ouicheck=OUICHECK_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            runner.invoke(cli, ["network", "ouicheck", "ABC123"])

        call_kwargs = mock_client.get_ouicheck.call_args[1]
        assert call_kwargs["serial"] == "ABC123"
        assert call_kwargs["version"] == "6.20.1"

    def test_json_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(get_eeros=EEROS_RESPONSE, get_ouicheck=OUICHECK_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "network", "ouicheck", "ABC123"])

        parsed = json.loads(result.output)
        assert parsed["data"] == OUICHECK_RESPONSE["data"]
        assert parsed["schema"] == "eero.network.ouicheck/v1"

    def test_not_found_exits_5(self, runner: CliRunner):
        mock_client = _mock_client(get_eeros={"meta": {"code": 200}, "data": {"eeros": []}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "ouicheck", "nonexistent"])

        assert result.exit_code == ExitCode.NOT_FOUND

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client(get_eeros=EEROS_RESPONSE)
        mock_client.get_ouicheck = AsyncMock(side_effect=EeroPremiumRequiredException("OUI"))

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "ouicheck", "ABC123"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED
