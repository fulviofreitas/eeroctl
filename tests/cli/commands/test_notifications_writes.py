"""Unit tests for `network notifications set|mark-read`.

Migration plan §4 phase C, `network notifications set` row. Mocks at the SDK
boundary (`patch("eeroctl.utils.EeroClient", ...)`).
"""

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli

_SETTINGS_ENVELOPE = {
    "meta": {"code": 200},
    "data": {"weekly_digest": True, "device_offline": False},
}


def _client(**method_return_values) -> AsyncMock:
    client = AsyncMock()
    for name, value in method_return_values.items():
        setattr(client, name, AsyncMock(return_value=value))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestNotificationsSet:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_requires_at_least_one_pair(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["network", "notifications", "set", "--force"])

        assert result.exit_code == ExitCode.USAGE_ERROR

    def test_invalid_pair_exits_usage_error(self, runner: CliRunner) -> None:
        mock_client = _client(get_notification_settings=_SETTINGS_ENVELOPE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "notifications", "set", "--set", "not-a-pair", "--force"]
            )

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.set_notification_settings.assert_not_called()

    def test_unknown_key_exits_usage_error(self, runner: CliRunner) -> None:
        mock_client = _client(get_notification_settings=_SETTINGS_ENVELOPE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "notifications",
                    "set",
                    "--set",
                    "not_a_real_setting=true",
                    "--force",
                ],
            )

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.set_notification_settings.assert_not_called()

    def test_updates_known_key(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_notification_settings=_SETTINGS_ENVELOPE,
            set_notification_settings={"meta": {"code": 200}, "data": {}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["network", "notifications", "set", "--set", "weekly_digest=false", "--force"],
            )

        assert result.exit_code == 0
        mock_client.set_notification_settings.assert_awaited_once_with(
            {"weekly_digest": False, "device_offline": False}, None
        )

    def test_skips_write_when_unchanged(self, runner: CliRunner) -> None:
        # --force would also bypass write_if_changed's skip-unchanged
        # short-circuit, so answer the Y/N prompt instead.
        mock_client = _client(
            get_notification_settings=_SETTINGS_ENVELOPE,  # weekly_digest: True
            set_notification_settings=AsyncMock(),
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["network", "notifications", "set", "--set", "weekly_digest=true"],
                input="y\n",
            )

        assert result.exit_code == 0
        assert "already configured" in result.output.lower()
        mock_client.set_notification_settings.assert_not_called()

    def test_non_interactive_without_force_still_succeeds_since_low_risk(
        self, runner: CliRunner
    ) -> None:
        # LOW risk never requires confirmation, so --non-interactive without
        # --force is fine here (unlike every MEDIUM/HIGH write elsewhere).
        mock_client = _client(
            get_notification_settings=_SETTINGS_ENVELOPE,
            set_notification_settings={"meta": {"code": 200}, "data": {}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--non-interactive",
                    "network",
                    "notifications",
                    "set",
                    "--set",
                    "weekly_digest=false",
                ],
            )

        assert result.exit_code == 0
        mock_client.set_notification_settings.assert_awaited_once()


class TestNotificationsMarkRead:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_marks_read(self, runner: CliRunner) -> None:
        mock_client = _client(mark_notifications_read={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "notifications", "mark-read", "--force"])

        assert result.exit_code == 0
        mock_client.mark_notifications_read.assert_awaited_once_with(None)

    def test_non_interactive_without_force_still_succeeds_since_low_risk(
        self, runner: CliRunner
    ) -> None:
        # LOW risk never requires confirmation, so --non-interactive without
        # --force is fine here (unlike every MEDIUM/HIGH write above).
        mock_client = _client(mark_notifications_read={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--non-interactive", "network", "notifications", "mark-read"]
            )

        assert result.exit_code == 0
        mock_client.mark_notifications_read.assert_awaited_once_with(None)
