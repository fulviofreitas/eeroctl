"""Stdout/stderr stream-isolation regression tests for the phase B/C1 batch.

wb's phase B/C1 commits predate f840919/0fc0380 (which fixed stream
isolation for the earlier phase-A/B write commands) -- several
``require_write_confirmation``/``write_if_changed`` call sites in this
batch still passed ``console=cli_ctx.console`` (stdout) instead of
``cli_ctx.err_console``, so the mesh-reboot warning, the unverified-write
note, and the "Write accepted"/"Verify with ..." messages leaked onto
stdout and broke ``--output json | jq``. This test parametrises over one
representative MEDIUM write (`network forwards create`) and one HIGH,
mesh-reboot write (`network security mlo set`) from that batch and
asserts stdout stays JSON-safe while stderr carries the note.

Mocks at the SDK boundary (`patch("eeroctl.utils.EeroClient", ...)`).
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.main import cli


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


_MEDIUM_WRITE_ARGS = [
    "network",
    "forwards",
    "create",
    "--config-json",
    '{"name": "SSH", "external_port": 22}',
    "--force",
]

_HIGH_WRITE_ARGS = [
    "network",
    "security",
    "mlo",
    "set",
    "multi",
    "--force",
]


def _medium_write_client() -> AsyncMock:
    return _client(create_forward={"meta": {"code": 201}, "data": {}})


def _high_write_client() -> AsyncMock:
    return _client(
        get_network={
            "meta": {"code": 200},
            "data": {"url": "/2.2/networks/net1", "mlo_mode": "disabled"},
        },
        set_mlo_mode={"meta": {"code": 200}, "data": {}},
    )


class TestPhaseBC1StdoutSafety:
    @pytest.mark.parametrize(
        ("args", "make_client"),
        [
            pytest.param(_MEDIUM_WRITE_ARGS, _medium_write_client, id="medium-forwards-create"),
            pytest.param(_HIGH_WRITE_ARGS, _high_write_client, id="high-mlo-set-mesh-reboot"),
        ],
    )
    def test_output_json_leaves_stdout_json_safe(
        self, runner: CliRunner, args: list, make_client
    ) -> None:
        """`--output json --force`: prompts/status lines never touch stdout.

        Either stdout is empty (neither command renders a JSON envelope of
        its own today) or, if it does carry bytes, they must be valid
        JSON -- never the confirmation prompt, the mesh-reboot warning, or
        the "Write accepted"/"Verify with ..." status lines.
        """
        mock_client = make_client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", *args])

        assert result.exit_code == 0, result.output
        if result.stdout:
            json.loads(result.stdout)
        assert "Write accepted" not in result.stdout
        assert "verify with" not in result.stdout.lower()
        assert "reboot" not in result.stdout.lower()

    @pytest.mark.parametrize(
        ("args", "make_client"),
        [
            pytest.param(_MEDIUM_WRITE_ARGS, _medium_write_client, id="medium-forwards-create"),
            pytest.param(_HIGH_WRITE_ARGS, _high_write_client, id="high-mlo-set-mesh-reboot"),
        ],
    )
    def test_write_status_note_lands_on_stderr(
        self, runner: CliRunner, args: list, make_client
    ) -> None:
        """The "Write accepted"/"Verify with ..." note is still shown to the
        user -- just on stderr, not stdout."""
        mock_client = make_client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, list(args))

        assert result.exit_code == 0, result.output
        assert "verify with" in result.stderr.lower() or "write accepted" in result.stderr.lower()
