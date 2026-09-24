"""Unit tests for eeroctl.commands.network.events.

Tests cover:
- network events (get_app_events, --page-size/--cursor, cursor in meta)
- network scan (get_network_scan)
- network channels (get_channel_utilization)

All three are plain, live-verified GETs (eero-api 8.0.1 migration plan §4,
phase A) -- no confirmation, no writes.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
import yaml
from click.testing import CliRunner
from eero.exceptions import EeroAccessDeniedException, EeroPremiumRequiredException

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli

EVENTS_RESPONSE = {
    "meta": {"code": 200},
    "data": {"events": [{"type": "client_connected"}], "next_timestamp": "2026-09-20T00:00:00Z"},
}
EVENTS_RESPONSE_NO_CURSOR = {"meta": {"code": 200}, "data": {"events": []}}
SCAN_RESPONSE = {"meta": {"code": 200}, "data": {"networks": [{"ssid": "neighbour"}]}}
CHANNELS_RESPONSE = {"meta": {"code": 200}, "data": {"series": [{"channel": 6, "busy": 12}]}}
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


class TestNetworkEvents:
    """Tests for `network events`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "events", "--help"])

        assert result.exit_code == 0
        assert "--page-size" in result.output
        assert "--cursor" in result.output

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_app_events=EVENTS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", output_format, "network", "events"])

        assert result.exit_code == 0
        mock_client.get_app_events.assert_awaited_once()

    def test_page_size_and_cursor_forwarded(self, runner: CliRunner):
        mock_client = _mock_client(get_app_events=EVENTS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            runner.invoke(
                cli,
                ["network", "events", "--page-size", "25", "--cursor", "abc123"],
            )

        call_kwargs = mock_client.get_app_events.call_args[1]
        assert call_kwargs["page_size"] == 25
        assert call_kwargs["timestamp"] == "abc123"

    def test_page_size_must_be_positive(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "events", "--page-size", "0"])

        assert result.exit_code == 2

    def test_json_output_includes_next_cursor_in_meta(self, runner: CliRunner):
        mock_client = _mock_client(get_app_events=EVENTS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "network", "events"])

        parsed = json.loads(result.output)
        assert parsed["meta"]["next_cursor"] == "2026-09-20T00:00:00Z"
        assert parsed["data"] == EVENTS_RESPONSE["data"]

    def test_yaml_output_includes_next_cursor_in_meta(self, runner: CliRunner):
        mock_client = _mock_client(get_app_events=EVENTS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "yaml", "network", "events"])

        parsed = yaml.safe_load(result.output)
        assert parsed["meta"]["next_cursor"] == "2026-09-20T00:00:00Z"

    def test_json_output_omits_cursor_when_absent(self, runner: CliRunner):
        mock_client = _mock_client(get_app_events=EVENTS_RESPONSE_NO_CURSOR)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "network", "events"])

        parsed = json.loads(result.output)
        assert "next_cursor" not in parsed["meta"]

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_app_events=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "events"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising("get_app_events", EeroPremiumRequiredException("Events"))

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "events"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        # commit 6 maps EeroAccessDeniedException directly; until then it falls
        # through the generic EeroAPIException branch's status_code == 403 check.
        mock_client = _mock_client_raising(
            "get_app_events", EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "events"])

        assert result.exit_code == ExitCode.FORBIDDEN


class TestNetworkScan:
    """Tests for `network scan`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "scan", "--help"])

        assert result.exit_code == 0

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_network_scan=SCAN_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", output_format, "network", "scan"])

        assert result.exit_code == 0
        mock_client.get_network_scan.assert_awaited_once()

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_network_scan=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "scan"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising("get_network_scan", EeroPremiumRequiredException("Scan"))

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "scan"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_network_scan", EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "scan"])

        assert result.exit_code == ExitCode.FORBIDDEN


class TestNetworkChannels:
    """Tests for `network channels`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "channels", "--help"])

        assert result.exit_code == 0
        assert "--start" in result.output
        assert "--end" in result.output
        assert "--band" in result.output
        assert "--eero" in result.output
        assert "--granularity" in result.output
        assert "--busy-threshold" in result.output
        assert "--cadence" not in result.output

    def test_requires_start_and_end(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "channels"])

        assert result.exit_code == 2

    def test_rejects_malformed_start(self, runner: CliRunner):
        result = runner.invoke(
            cli,
            [
                "network",
                "channels",
                "--start",
                "not-a-timestamp",
                "--end",
                "2026-09-21T00:00:00Z",
            ],
        )

        assert result.exit_code == 2

    def test_rejects_inverted_window(self, runner: CliRunner):
        result = runner.invoke(
            cli,
            [
                "network",
                "channels",
                "--start",
                "2026-09-21T00:00:00Z",
                "--end",
                "2026-09-20T00:00:00Z",
            ],
        )

        assert result.exit_code == 2

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_channel_utilization=CHANNELS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--output",
                    output_format,
                    "network",
                    "channels",
                    "--start",
                    "2026-09-20T00:00:00Z",
                    "--end",
                    "2026-09-21T00:00:00Z",
                ],
            )

        assert result.exit_code == 0
        mock_client.get_channel_utilization.assert_awaited_once()

    def test_optional_flags_forwarded(self, runner: CliRunner):
        mock_client = _mock_client(get_channel_utilization=CHANNELS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            runner.invoke(
                cli,
                [
                    "network",
                    "channels",
                    "--start",
                    "2026-09-20T00:00:00Z",
                    "--end",
                    "2026-09-21T00:00:00Z",
                    "--band",
                    "band_5GHz_low",
                    "--eero",
                    "42",
                    "--granularity",
                    "15",
                    "--busy-threshold",
                    "80",
                ],
            )

        call_kwargs = mock_client.get_channel_utilization.call_args[1]
        assert call_kwargs["start"] == "2026-09-20T00:00:00Z"
        assert call_kwargs["end"] == "2026-09-21T00:00:00Z"
        assert call_kwargs["band"] == "band_5GHz_low"
        assert call_kwargs["eero_id"] == 42
        assert call_kwargs["granularity"] == 15
        assert call_kwargs["busy_threshold"] == 80

    def test_invalid_band_rejected(self, runner: CliRunner):
        result = runner.invoke(
            cli,
            [
                "network",
                "channels",
                "--start",
                "2026-09-20T00:00:00Z",
                "--end",
                "2026-09-21T00:00:00Z",
                "--band",
                "not_a_band",
            ],
        )

        assert result.exit_code == 2

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_channel_utilization=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "channels",
                    "--start",
                    "2026-09-20T00:00:00Z",
                    "--end",
                    "2026-09-21T00:00:00Z",
                ],
            )

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_channel_utilization", EeroPremiumRequiredException("Channels")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "channels",
                    "--start",
                    "2026-09-20T00:00:00Z",
                    "--end",
                    "2026-09-21T00:00:00Z",
                ],
            )

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_channel_utilization", EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "channels",
                    "--start",
                    "2026-09-20T00:00:00Z",
                    "--end",
                    "2026-09-21T00:00:00Z",
                ],
            )

        assert result.exit_code == ExitCode.FORBIDDEN
