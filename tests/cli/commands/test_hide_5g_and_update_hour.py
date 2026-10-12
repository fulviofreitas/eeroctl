"""Unit tests for `network security hide-5g` and `eero updates hour set`.

Both wrap writes eero-api 8.3.0 added to the `EeroClient` facade
(`set_hide_5g`, `set_preferred_update_hour`). Mocks at the SDK boundary
(`patch("eeroctl.utils.EeroClient", ...)`).
"""

from typing import Any, Dict
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli
from eeroctl.transformers.network import extract_hide_5g


def _network(**data: Any) -> Dict[str, Any]:
    return {"meta": {"code": 200}, "data": {"url": "/2.2/networks/net1", **data}}


# Live shape: `temporary_flags` is `{}` when nothing is hidden.
_NOT_HIDDEN = _network(temporary_flags={}, updates={"preferred_update_hour": 19})
_HIDDEN = _network(
    temporary_flags={"hide_5g": {"value": True, "expiration": "2026-10-12T20:00:00Z"}}
)


def _client(**method_return_values) -> AsyncMock:
    client = AsyncMock()
    for name, value in method_return_values.items():
        setattr(client, name, AsyncMock(return_value=value))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestExtractHide5g:
    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            ({"temporary_flags": {}}, False),
            ({"temporary_flags": {"hide_5g": {"value": True}}}, True),
            ({"temporary_flags": {"hide_5g": {"value": False}}}, False),
            ({}, None),
            ({"temporary_flags": None}, None),
        ],
    )
    def test_extract(self, data: Dict[str, Any], expected: Any) -> None:
        assert extract_hide_5g(data) is expected


class TestHide5gToggle:
    def test_enable_requires_disconnect_phrase(self, runner: CliRunner) -> None:
        mock_client = _client(get_network=_NOT_HIDDEN, set_hide_5g={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "security", "hide-5g", "enable"], input="DISCONNECT\n"
            )

        assert result.exit_code == 0
        mock_client.set_hide_5g.assert_awaited_once_with(True, None)

    def test_enable_wrong_phrase_does_not_write(self, runner: CliRunner) -> None:
        mock_client = _client(get_network=_NOT_HIDDEN, set_hide_5g=AsyncMock())

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "security", "hide-5g", "enable"], input="y\n")

        assert result.exit_code != 0
        mock_client.set_hide_5g.assert_not_called()

    def test_disable_calls_set_hide_5g(self, runner: CliRunner) -> None:
        mock_client = _client(get_network=_HIDDEN, set_hide_5g={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "security", "hide-5g", "disable", "--force"])

        assert result.exit_code == 0
        mock_client.set_hide_5g.assert_awaited_once_with(False, None)

    def test_disable_skips_write_when_not_hidden(self, runner: CliRunner) -> None:
        mock_client = _client(get_network=_NOT_HIDDEN, set_hide_5g=AsyncMock())

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "security", "hide-5g", "disable"], input="y\n")

        assert result.exit_code == 0
        assert "already configured" in result.output.lower()
        mock_client.set_hide_5g.assert_not_called()

    def test_enable_skips_write_when_already_hidden(self, runner: CliRunner) -> None:
        mock_client = _client(get_network=_HIDDEN, set_hide_5g=AsyncMock())

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "security", "hide-5g", "enable"], input="DISCONNECT\n"
            )

        assert result.exit_code == 0
        assert "already configured" in result.output.lower()
        mock_client.set_hide_5g.assert_not_called()

    def test_unknown_state_writes(self, runner: CliRunner) -> None:
        """No `temporary_flags` in the envelope: state unknown, so write."""
        mock_client = _client(get_network=_network(), set_hide_5g={"meta": {"code": 200}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "security", "hide-5g", "disable", "--force"])

        assert result.exit_code == 0
        mock_client.set_hide_5g.assert_awaited_once_with(False, None)

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client(get_network=_NOT_HIDDEN)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--non-interactive", "network", "security", "hide-5g", "enable"]
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_hide_5g.assert_not_called()


class TestUpdatesHourSet:
    def test_sets_hour(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_network=_NOT_HIDDEN, set_preferred_update_hour={"meta": {"code": 200}}
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["eero", "updates", "hour", "set", "3"], input="y\n")

        assert result.exit_code == 0
        mock_client.set_preferred_update_hour.assert_awaited_once_with(3, None)

    def test_skips_write_when_unchanged(self, runner: CliRunner) -> None:
        mock_client = _client(get_network=_NOT_HIDDEN, set_preferred_update_hour=AsyncMock())

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["eero", "updates", "hour", "set", "19"], input="y\n")

        assert result.exit_code == 0
        assert "already configured" in result.output.lower()
        mock_client.set_preferred_update_hour.assert_not_called()

    @pytest.mark.parametrize("hour", ["24", "-1", "noon"])
    def test_out_of_range_exits_usage_error_before_any_client_call(
        self, runner: CliRunner, hour: str
    ) -> None:
        with patch("eeroctl.utils.EeroClient") as client_cls:
            result = runner.invoke(cli, ["eero", "updates", "hour", "set", "--", hour])

        assert result.exit_code == ExitCode.USAGE_ERROR
        client_cls.assert_not_called()

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client(get_network=_NOT_HIDDEN)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--non-interactive", "eero", "updates", "hour", "set", "3"]
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_preferred_update_hour.assert_not_called()

    def test_show_includes_preferred_hour(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_updates={
                "meta": {"code": 200},
                "data": {"has_update": False, "preferred_update_hour": 19},
            }
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["eero", "updates", "show"])

        assert result.exit_code == 0
        assert "Preferred Update Hour" in result.output
        assert "19" in result.output
