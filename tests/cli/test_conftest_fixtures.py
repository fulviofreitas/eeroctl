"""Self-test for the shared `mock_client`/`mock_client_raising` fixtures.

Pins the contract the phase-A and command test modules will migrate onto
(second half of the `mock_client` cleanup, landed after the group-1 stack
and phase-A batches are pushed): a working async context manager,
``is_authenticated = True``, the ``eeroctl.utils.EeroClient`` patch applied
for the test's duration, and a scrubbed `EEROCTL_*` environment.
"""

import os
from unittest.mock import AsyncMock

import pytest
from click.testing import CliRunner
from eero.exceptions import EeroPremiumRequiredException

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli
from eeroctl.utils import build_client

from ..conftest import _EEROCTL_ENV_VARS


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestMockClientShape:
    def test_has_working_async_context_manager(self, mock_client: AsyncMock):
        assert mock_client.__aenter__.return_value is mock_client
        assert mock_client.__aexit__.return_value is False

    def test_is_authenticated(self, mock_client: AsyncMock):
        assert mock_client.is_authenticated is True

    def test_is_an_async_mock(self, mock_client: AsyncMock):
        assert isinstance(mock_client, AsyncMock)


class TestMockClientWiring:
    def test_build_client_returns_the_fixture(self, mock_client: AsyncMock):
        """`eeroctl.utils.EeroClient` is patched, so `build_client()` -- the
        single construction site every command calls -- hands back exactly
        the object the test configured."""
        assert build_client() is mock_client

    def test_configured_method_is_reachable_through_the_cli(
        self, runner: CliRunner, mock_client: AsyncMock
    ):
        mock_client.get_networks = AsyncMock(
            return_value={"meta": {"code": 200}, "data": {"networks": {"data": []}}}
        )

        result = runner.invoke(cli, ["network", "list"])

        assert result.exit_code == 0, result.output
        mock_client.get_networks.assert_awaited_once()


class TestMockClientEnvironmentIsClean:
    @pytest.fixture
    def preset_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set every documented EEROCTL_* var *before* mock_client runs."""
        for var in _EEROCTL_ENV_VARS:
            monkeypatch.setenv(var, "polluted")

    def test_mock_client_scrubs_preexisting_eeroctl_env(
        self, preset_env: None, mock_client: AsyncMock
    ):
        for var in _EEROCTL_ENV_VARS:
            assert var not in os.environ, var

    def test_mock_client_raising_scrubs_preexisting_eeroctl_env(
        self, preset_env: None, mock_client_raising
    ):
        mock_client_raising("get_networks", RuntimeError("boom"))
        for var in _EEROCTL_ENV_VARS:
            assert var not in os.environ, var


class TestMockClientRaising:
    def test_returns_a_client_whose_named_method_raises(self, mock_client_raising):
        exc = EeroPremiumRequiredException("Entitlements")

        client = mock_client_raising("get_entitlement_features", exc)

        assert client.get_entitlement_features.side_effect is exc

    def test_patches_eeroctl_utils_eeroclient(self, mock_client_raising):
        client = mock_client_raising("get_networks", RuntimeError("boom"))

        assert build_client() is client

    def test_exception_surfaces_through_the_cli(self, runner: CliRunner, mock_client_raising):
        mock_client_raising("get_insights", EeroPremiumRequiredException("Activity"))

        result = runner.invoke(
            cli, ["activity", "history", "--start", "2026-07-01", "--end", "2026-07-22"]
        )

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED, result.output

    def test_second_call_replaces_the_first_patch(self, mock_client_raising):
        first = mock_client_raising("get_networks", RuntimeError("first"))
        second = mock_client_raising("get_networks", RuntimeError("second"))

        assert build_client() is second
        assert build_client() is not first
