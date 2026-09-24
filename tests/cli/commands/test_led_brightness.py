"""Unit tests for the `eero eero led brightness` read-first skip.

Migration plan §4 phase B row 27: `led on`/`led off` already had the
read-first/skip-unchanged path; `led brightness` did not. Covers the gap.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.main import cli

_EERO_ENVELOPE = {
    "meta": {"code": 200},
    "data": {"url": "/2.2/networks/net1/eeros/123", "location": "Office"},
}


def _make_run_with_client(mock_client: MagicMock):
    async def _run(func):
        await func(mock_client)

    return _run


def _mock_client(**method_return_values) -> MagicMock:
    client = MagicMock()
    for method_name, return_value in method_return_values.items():
        setattr(client, method_name, AsyncMock(return_value=return_value))
    return client


class TestLedBrightnessReadFirst:
    """Tests for `eero led brightness`'s write_if_changed integration."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_skips_write_when_already_at_target(self, runner: CliRunner) -> None:
        mock_client = _mock_client(
            get_eero=_EERO_ENVELOPE,
            get_led_status={"meta": {"code": 200}, "data": {"led_brightness": 50}},
        )

        with patch(
            "eeroctl.commands.eero.led.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(cli, ["eero", "led", "brightness", "123", "50"])

        assert result.exit_code == 0
        assert "already configured" in result.output.lower()
        mock_client.set_led_brightness.assert_not_called()

    def test_writes_when_brightness_differs(self, runner: CliRunner) -> None:
        mock_client = _mock_client(
            get_eero=_EERO_ENVELOPE,
            get_led_status={"meta": {"code": 200}, "data": {"led_brightness": 50}},
            set_led_brightness={"meta": {"code": 200}, "data": {"led_brightness": 75}},
        )

        with patch(
            "eeroctl.commands.eero.led.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(cli, ["eero", "led", "brightness", "123", "75"])

        assert result.exit_code == 0
        assert "accepted" in result.output.lower()
        mock_client.set_led_brightness.assert_awaited_once()
        call_args = mock_client.set_led_brightness.call_args
        assert call_args[0][1] == 75

    def test_force_writes_even_when_unchanged(self, runner: CliRunner) -> None:
        mock_client = _mock_client(
            get_eero=_EERO_ENVELOPE,
            get_led_status={"meta": {"code": 200}, "data": {"led_brightness": 50}},
            set_led_brightness={"meta": {"code": 200}, "data": {"led_brightness": 50}},
        )

        with patch(
            "eeroctl.commands.eero.led.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(cli, ["--force", "eero", "led", "brightness", "123", "50"])

        assert result.exit_code == 0
        mock_client.set_led_brightness.assert_awaited_once()
