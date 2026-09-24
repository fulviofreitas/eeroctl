"""Unit tests for commit 24's phase-A activity insights reads.

Tests cover:
- activity devices                (get_devices_insights)
- activity device <id>            (get_device_insights)
- activity profiles               (get_profiles_insights)
- activity profile <id>[--devices] (get_profile_insights /
  get_profile_devices_insights)
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner
from eero.exceptions import EeroAccessDeniedException, EeroPremiumRequiredException

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli

# Reuse the mock-client helpers defined in test_events.py rather than
# redefining them per module (standing rule from the batch-1 test audit); a
# shared conftest fixture lands after the group-1 stack is pushed.
from .test_events import _mock_client, _mock_client_raising

INSIGHTS_RESPONSE = {
    "meta": {"code": 200},
    "data": {"series": [{"insight_type": "inspected", "sum": 10}]},
}
EMPTY_RESPONSE = {"meta": {"code": 200}, "data": {}}
DEVICES_RESPONSE = {
    "meta": {"code": 200},
    "data": {"devices": [{"url": "/2.2/devices/1", "mac": "AA:BB:CC", "nickname": "Laptop"}]},
}
PROFILES_RESPONSE = {
    "meta": {"code": 200},
    "data": {"profiles": [{"url": "/2.2/profiles/1", "name": "Kids"}]},
}

WINDOW_ARGS = [
    "--start",
    "2026-09-01T00:00:00Z",
    "--end",
    "2026-09-21T00:00:00Z",
    "--cadence",
    "daily",
    "--insight-type",
    "inspected",
]


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI runner."""
    return CliRunner()


class TestActivityDevices:
    """Tests for `activity devices`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["activity", "devices", "--help"])

        assert result.exit_code == 0
        assert "--cadence" in result.output
        assert "--insight-type" in result.output

    def test_requires_cadence(self, runner: CliRunner):
        result = runner.invoke(
            cli,
            [
                "activity",
                "devices",
                "--start",
                "2026-09-01T00:00:00Z",
                "--insight-type",
                "inspected",
            ],
        )

        assert result.exit_code == 2

    def test_requires_insight_type(self, runner: CliRunner):
        result = runner.invoke(cli, ["activity", "devices", "--cadence", "daily"])

        assert result.exit_code == 2

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_devices_insights=INSIGHTS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", output_format, "activity", "devices", *WINDOW_ARGS]
            )

        assert result.exit_code == 0
        mock_client.get_devices_insights.assert_awaited_once()

    def test_cadence_and_insight_type_forwarded(self, runner: CliRunner):
        mock_client = _mock_client(get_devices_insights=INSIGHTS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            runner.invoke(cli, ["activity", "devices", *WINDOW_ARGS])

        call_kwargs = mock_client.get_devices_insights.call_args[1]
        assert call_kwargs["cadence"] == "daily"
        assert call_kwargs["insight_type"] == "inspected"
        assert call_kwargs["start"] == "2026-09-01T00:00:00Z"
        assert call_kwargs["end"] == "2026-09-21T00:00:00Z"

    def test_json_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(get_devices_insights=INSIGHTS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "activity", "devices", *WINDOW_ARGS])

        parsed = json.loads(result.output)
        assert parsed["data"] == INSIGHTS_RESPONSE["data"]
        assert parsed["schema"] == "eero.activity.devices/v1"

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_devices_insights=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["activity", "devices", *WINDOW_ARGS])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_devices_insights", EeroPremiumRequiredException("Devices")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["activity", "devices", *WINDOW_ARGS])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        # commit 6 maps EeroAccessDeniedException directly; until then it falls
        # through the generic EeroAPIException branch's status_code == 403 check.
        # Uses run_with_client (the phase-A convention), unlike history/categories.
        mock_client = _mock_client_raising(
            "get_devices_insights", EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["activity", "devices", *WINDOW_ARGS])

        assert result.exit_code == ExitCode.FORBIDDEN


class TestActivityDevice:
    """Tests for `activity device <id>`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["activity", "device", "--help"])

        assert result.exit_code == 0

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(
            get_devices=DEVICES_RESPONSE, get_device_insights=INSIGHTS_RESPONSE
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", output_format, "activity", "device", "Laptop", *WINDOW_ARGS]
            )

        assert result.exit_code == 0
        mock_client.get_device_insights.assert_awaited_once()

    def test_not_found_exits_5(self, runner: CliRunner):
        mock_client = _mock_client(get_devices={"meta": {"code": 200}, "data": {"devices": []}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["activity", "device", "nonexistent", *WINDOW_ARGS])

        assert result.exit_code == ExitCode.NOT_FOUND

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client(get_devices=DEVICES_RESPONSE)
        mock_client.get_device_insights = AsyncMock(
            side_effect=EeroPremiumRequiredException("Device")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["activity", "device", "Laptop", *WINDOW_ARGS])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED


class TestActivityProfiles:
    """Tests for `activity profiles`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["activity", "profiles", "--help"])

        assert result.exit_code == 0

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_profiles_insights=INSIGHTS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", output_format, "activity", "profiles", *WINDOW_ARGS]
            )

        assert result.exit_code == 0
        mock_client.get_profiles_insights.assert_awaited_once()

    def test_json_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(get_profiles_insights=INSIGHTS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "activity", "profiles", *WINDOW_ARGS])

        parsed = json.loads(result.output)
        assert parsed["data"] == INSIGHTS_RESPONSE["data"]
        assert parsed["schema"] == "eero.activity.profiles/v1"

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_profiles_insights=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["activity", "profiles", *WINDOW_ARGS])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_profiles_insights", EeroPremiumRequiredException("Profiles")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["activity", "profiles", *WINDOW_ARGS])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED


class TestActivityProfile:
    """Tests for `activity profile <id>[--devices]`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["activity", "profile", "--help"])

        assert result.exit_code == 0
        assert "--devices" in result.output

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(
            get_profiles=PROFILES_RESPONSE, get_profile_insights=INSIGHTS_RESPONSE
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", output_format, "activity", "profile", "Kids", *WINDOW_ARGS]
            )

        assert result.exit_code == 0
        mock_client.get_profile_insights.assert_awaited_once()

    def test_devices_flag_calls_profile_devices_insights(self, runner: CliRunner):
        mock_client = _mock_client(
            get_profiles=PROFILES_RESPONSE, get_profile_devices_insights=INSIGHTS_RESPONSE
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["activity", "profile", "Kids", "--devices", *WINDOW_ARGS])

        assert result.exit_code == 0
        mock_client.get_profile_devices_insights.assert_awaited_once()

    def test_json_output_passes_data_through(self, runner: CliRunner):
        mock_client = _mock_client(
            get_profiles=PROFILES_RESPONSE, get_profile_insights=INSIGHTS_RESPONSE
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", "json", "activity", "profile", "Kids", *WINDOW_ARGS]
            )

        parsed = json.loads(result.output)
        assert parsed["data"] == INSIGHTS_RESPONSE["data"]
        assert parsed["schema"] == "eero.activity.profile/v1"

    def test_devices_flag_json_schema(self, runner: CliRunner):
        mock_client = _mock_client(
            get_profiles=PROFILES_RESPONSE, get_profile_devices_insights=INSIGHTS_RESPONSE
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["--output", "json", "activity", "profile", "Kids", "--devices", *WINDOW_ARGS],
            )

        parsed = json.loads(result.output)
        assert parsed["schema"] == "eero.activity.profile.devices/v1"

    def test_not_found_exits_5(self, runner: CliRunner):
        mock_client = _mock_client(get_profiles={"meta": {"code": 200}, "data": {"profiles": []}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["activity", "profile", "nonexistent", *WINDOW_ARGS])

        assert result.exit_code == ExitCode.NOT_FOUND

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client(get_profiles=PROFILES_RESPONSE)
        mock_client.get_profile_insights = AsyncMock(
            side_effect=EeroPremiumRequiredException("Profile")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["activity", "profile", "Kids", *WINDOW_ARGS])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED


class TestActivityHistoryCategoriesUnaffected:
    """`activity history`/`categories` still work unrewired (see commit 24's
    docstring note in activity.py for why they were left as-is).
    """

    def test_history_still_works(self, runner: CliRunner):
        mock_client = _mock_client(get_insights=INSIGHTS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["activity", "history", "--start", "2026-07-01", "--end", "2026-07-22"],
            )

        assert result.exit_code == 0

    def test_categories_still_accepts_weekly_cadence(self, runner: CliRunner):
        """Pre-existing quirk (not fixed by this commit): --cadence weekly is
        still CLI-accepted even though the SDK would reject it server-side.
        """
        mock_client = _mock_client(get_insights=INSIGHTS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "activity",
                    "categories",
                    "--start",
                    "2026-07-01",
                    "--end",
                    "2026-07-22",
                    "--cadence",
                    "weekly",
                ],
            )

        assert result.exit_code == 0
