"""Unit tests for eeroctl.commands.network.notifications.

Tests cover:
- network notifications show    (get_notification_settings)
- network notifications unread  (has_unread_notifications)
- network notifications history (get_notification_history, --cursor)
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
import yaml
from click.testing import CliRunner
from eero.exceptions import EeroAccessDeniedException, EeroPremiumRequiredException

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli
from eeroctl.transformers.notifications import extract_history_next_cursor, extract_unread_flag

SETTINGS_RESPONSE = {
    "meta": {"code": 200},
    "data": {"network.updated": True, "device.new": False},
}
UNREAD_RESPONSE = {"meta": {"code": 200}, "data": {"has_unread": True}}
HISTORY_RESPONSE = {
    "meta": {"code": 200},
    "data": {"notifications": [{"id": "1"}], "next_timestamp": "2026-09-20T00:00:00Z"},
}
HISTORY_RESPONSE_NO_CURSOR = {"meta": {"code": 200}, "data": {"notifications": []}}
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


class TestNotificationsGroup:
    """Tests for the `network notifications` command group."""

    def test_notifications_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "notifications", "--help"])

        assert result.exit_code == 0
        assert "show" in result.output
        assert "unread" in result.output
        assert "history" in result.output


class TestNotificationsShow:
    """Tests for `network notifications show`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "notifications", "show", "--help"])

        assert result.exit_code == 0

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_notification_settings=SETTINGS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", output_format, "network", "notifications", "show"]
            )

        assert result.exit_code == 0
        mock_client.get_notification_settings.assert_awaited_once()

    def test_table_output_shows_event_keys(self, runner: CliRunner):
        mock_client = _mock_client(get_notification_settings=SETTINGS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "notifications", "show"])

        assert result.exit_code == 0
        assert "network.updated" in result.output
        assert "device.new" in result.output

    def test_json_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(get_notification_settings=SETTINGS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "network", "notifications", "show"])

        parsed = json.loads(result.output)
        assert parsed["data"] == SETTINGS_RESPONSE["data"]
        assert parsed["schema"] == "eero.network.notifications.show/v1"

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_notification_settings=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "notifications", "show"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_notification_settings", EeroPremiumRequiredException("Notifications")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "notifications", "show"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        # commit 6 maps EeroAccessDeniedException directly; until then it falls
        # through the generic EeroAPIException branch's status_code == 403 check.
        mock_client = _mock_client_raising(
            "get_notification_settings", EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "notifications", "show"])

        assert result.exit_code == ExitCode.FORBIDDEN


class TestNotificationsUnread:
    """Tests for `network notifications unread`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "notifications", "unread", "--help"])

        assert result.exit_code == 0

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(has_unread_notifications=UNREAD_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", output_format, "network", "notifications", "unread"]
            )

        assert result.exit_code == 0
        mock_client.has_unread_notifications.assert_awaited_once()

    def test_table_output_shows_has_unread(self, runner: CliRunner):
        mock_client = _mock_client(has_unread_notifications=UNREAD_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "notifications", "unread"])

        assert result.exit_code == 0
        assert "Has Unread" in result.output

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(has_unread_notifications=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "notifications", "unread"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "has_unread_notifications", EeroPremiumRequiredException("Unread")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "notifications", "unread"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "has_unread_notifications", EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "notifications", "unread"])

        assert result.exit_code == ExitCode.FORBIDDEN


class TestNotificationsHistory:
    """Tests for `network notifications history`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "notifications", "history", "--help"])

        assert result.exit_code == 0
        assert "--cursor" in result.output

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_notification_history=HISTORY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", output_format, "network", "notifications", "history"]
            )

        assert result.exit_code == 0
        mock_client.get_notification_history.assert_awaited_once()

    def test_cursor_forwarded_as_timestamp(self, runner: CliRunner):
        mock_client = _mock_client(get_notification_history=HISTORY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            runner.invoke(cli, ["network", "notifications", "history", "--cursor", "abc123"])

        call_kwargs = mock_client.get_notification_history.call_args[1]
        assert call_kwargs["timestamp"] == "abc123"

    def test_json_output_includes_next_cursor_in_meta(self, runner: CliRunner):
        mock_client = _mock_client(get_notification_history=HISTORY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "network", "notifications", "history"])

        parsed = json.loads(result.output)
        assert parsed["meta"]["next_cursor"] == "2026-09-20T00:00:00Z"

    def test_json_output_omits_cursor_when_absent(self, runner: CliRunner):
        mock_client = _mock_client(get_notification_history=HISTORY_RESPONSE_NO_CURSOR)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "network", "notifications", "history"])

        parsed = json.loads(result.output)
        assert "next_cursor" not in parsed["meta"]

    def test_yaml_output_includes_next_cursor_in_meta(self, runner: CliRunner):
        mock_client = _mock_client(get_notification_history=HISTORY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "yaml", "network", "notifications", "history"])

        parsed = yaml.safe_load(result.output)
        assert parsed["meta"]["next_cursor"] == "2026-09-20T00:00:00Z"

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_notification_history=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "notifications", "history"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_notification_history", EeroPremiumRequiredException("History")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "notifications", "history"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_notification_history", EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "notifications", "history"])

        assert result.exit_code == ExitCode.FORBIDDEN


class TestExtractHelpers:
    """Unit tests for the notifications transformer accessors."""

    def test_extract_unread_flag_true(self):
        assert extract_unread_flag({"has_unread": True}) is True

    def test_extract_unread_flag_false(self):
        assert extract_unread_flag({"has_unread": False}) is False

    def test_extract_unread_flag_missing_returns_none(self):
        assert extract_unread_flag({}) is None
        assert extract_unread_flag(None) is None

    def test_extract_history_next_cursor_found(self):
        assert (
            extract_history_next_cursor({"next_timestamp": "2026-09-20T00:00:00Z"})
            == "2026-09-20T00:00:00Z"
        )

    def test_extract_history_next_cursor_absent(self):
        assert extract_history_next_cursor({"notifications": []}) is None
