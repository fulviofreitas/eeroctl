"""Unit tests for `network wpa3 set` and `network security fast-transition
enable|disable`.

Migration plan §4 phase C row 30. Mocks at the SDK boundary
(`patch("eeroctl.utils.EeroClient", ...)`).
"""

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli

_WPA3_ENVELOPE = {
    "meta": {"code": 200},
    "data": {"band_2_4_ghz": "WPA2", "band_5_ghz": "WPA2_WPA3"},
}

_FAST_TRANSITION_ENVELOPE = {
    "meta": {"code": 200},
    "data": {"enabled": False},
}


def _client(**method_return_values) -> AsyncMock:
    client = AsyncMock()
    for name, value in method_return_values.items():
        setattr(client, name, AsyncMock(return_value=value))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestWpa3PerBandSet:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["network", "wpa3", "set", "--help"])

        assert result.exit_code == 0
        assert "--band-2-4" in result.output
        assert "--band-5" in result.output

    def test_no_band_given_exits_usage_error_before_any_prompt(self, runner: CliRunner) -> None:
        mock_client = _client(get_wpa3_per_band=_WPA3_ENVELOPE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "wpa3", "set"])

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.get_wpa3_per_band.assert_not_called()
        mock_client.set_wpa3_per_band.assert_not_called()

    def test_invalid_mode_rejected(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["network", "wpa3", "set", "--band-2-4", "bogus"])

        assert result.exit_code != 0

    def test_requires_reboot_phrase(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_wpa3_per_band=_WPA3_ENVELOPE,
            set_wpa3_per_band={"meta": {"code": 200}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["network", "wpa3", "set", "--band-2-4", "WPA3"],
                input="REBOOT\n",
            )

        assert result.exit_code == 0
        mock_client.set_wpa3_per_band.assert_awaited_once_with(
            None, band_2_4_ghz="WPA3", band_5_ghz=None
        )

    def test_phrase_mismatch_fails(self, runner: CliRunner) -> None:
        mock_client = _client(get_wpa3_per_band=_WPA3_ENVELOPE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["network", "wpa3", "set", "--band-2-4", "WPA3"],
                input="nope\n",
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_wpa3_per_band.assert_not_called()

    def test_force_skips_prompt(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_wpa3_per_band=_WPA3_ENVELOPE,
            set_wpa3_per_band={"meta": {"code": 200}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "wpa3", "set", "--band-2-4", "WPA3", "--force"])

        assert result.exit_code == 0
        mock_client.set_wpa3_per_band.assert_awaited_once()

    def test_skips_write_when_only_unchanged_band_given(self, runner: CliRunner) -> None:
        # band_2_4_ghz is already "WPA2" in the envelope; --force would also
        # bypass the skip-unchanged short-circuit (write_if_changed's
        # documented contract), so answer the REBOOT prompt instead.
        mock_client = _client(get_wpa3_per_band=_WPA3_ENVELOPE, set_wpa3_per_band=AsyncMock())

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "wpa3", "set", "--band-2-4", "WPA2"], input="REBOOT\n"
            )

        assert result.exit_code == 0
        assert "already configured" in result.output.lower()
        mock_client.set_wpa3_per_band.assert_not_called()

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client(get_wpa3_per_band=_WPA3_ENVELOPE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["--non-interactive", "network", "wpa3", "set", "--band-2-4", "WPA3"],
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_wpa3_per_band.assert_not_called()


class TestFastTransitionToggle:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_enable_requires_reboot_phrase(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_fast_transition=_FAST_TRANSITION_ENVELOPE,
            set_fast_transition={"meta": {"code": 200}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["network", "security", "fast-transition", "enable"],
                input="REBOOT\n",
            )

        assert result.exit_code == 0
        mock_client.set_fast_transition.assert_awaited_once_with(True, None)

    def test_phrase_mismatch_fails(self, runner: CliRunner) -> None:
        mock_client = _client(get_fast_transition=_FAST_TRANSITION_ENVELOPE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["network", "security", "fast-transition", "enable"],
                input="nope\n",
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_fast_transition.assert_not_called()

    def test_force_writes(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_fast_transition=_FAST_TRANSITION_ENVELOPE,
            set_fast_transition={"meta": {"code": 200}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "security", "fast-transition", "enable", "--force"]
            )

        assert result.exit_code == 0
        mock_client.set_fast_transition.assert_awaited_once_with(True, None)

    def test_skips_write_when_already_disabled(self, runner: CliRunner) -> None:
        # --force would also bypass the skip-unchanged short-circuit
        # (write_if_changed's documented contract), so answer the REBOOT
        # prompt instead.
        mock_client = _client(
            get_fast_transition=_FAST_TRANSITION_ENVELOPE,  # enabled: False
            set_fast_transition=AsyncMock(),
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["network", "security", "fast-transition", "disable"],
                input="REBOOT\n",
            )

        assert result.exit_code == 0
        assert "already configured" in result.output.lower()
        mock_client.set_fast_transition.assert_not_called()

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client(get_fast_transition=_FAST_TRANSITION_ENVELOPE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["--non-interactive", "network", "security", "fast-transition", "disable"],
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_fast_transition.assert_not_called()
