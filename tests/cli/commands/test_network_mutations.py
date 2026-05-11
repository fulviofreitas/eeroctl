"""Mutation regression tests for eeroctl network commands.

Guards the contract between eeroctl mutation commands and the EeroClient methods
affected by the eero-api 4.1.2 routing/payload fix.  Each test patches
``run_with_client`` at the module where it is imported and asserts that the
correct EeroClient method is called with the expected positional arguments.

See PR42-PLAN.md §T1 for rationale.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.main import cli

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_OK_RESPONSE = {"meta": {"code": 200, "error": None}, "data": {}}
_ERR_RESPONSE = {"meta": {"code": 500, "error": "boom"}, "data": {}}

NID = "NID"


def _make_run_with_client(mock_client: MagicMock):
    """Return a coroutine that mimics run_with_client, injecting *mock_client*."""

    async def _run(func):
        await func(mock_client)

    return _run


def _make_mock_client(**method_return_values) -> MagicMock:
    """Build a MagicMock EeroClient whose named async methods return preset values."""
    client = MagicMock()
    for method_name, return_value in method_return_values.items():
        setattr(client, method_name, AsyncMock(return_value=return_value))
    return client


# ---------------------------------------------------------------------------
# TestNetworkRename
# ---------------------------------------------------------------------------


class TestNetworkRename:
    """Tests for ``eero network rename`` → ``client.set_network_name``."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Mock EeroClient with set_network_name returning a 200 response."""
        return _make_mock_client(set_network_name=_OK_RESPONSE)

    def test_network_rename_calls_set_network_name(self, runner: CliRunner, mock_client: MagicMock):
        """rename passes (name, network_id) to set_network_name and exits 0."""
        with patch(
            "eeroctl.commands.network.base.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(
                cli, ["network", "rename", "--name", "my-ssid", "--force", "--network-id", NID]
            )

        mock_client.set_network_name.assert_called_once_with("my-ssid", NID)
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# TestSQM
# ---------------------------------------------------------------------------


class TestSQM:
    """Tests for ``eero network sqm enable/disable`` → ``client.set_sqm_enabled``."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_client_true(self) -> MagicMock:
        """Mock client returning truthy response for set_sqm_enabled."""
        return _make_mock_client(set_sqm_enabled=_OK_RESPONSE)

    @pytest.fixture
    def mock_client_false(self) -> MagicMock:
        """Mock client returning truthy response for set_sqm_enabled (disable path)."""
        return _make_mock_client(set_sqm_enabled=_OK_RESPONSE)

    def test_sqm_enable_calls_set_sqm_enabled_with_boolean(
        self, runner: CliRunner, mock_client_true: MagicMock
    ):
        """sqm enable passes bare True boolean to set_sqm_enabled (locks eero-api 4.1.2 contract)."""
        with patch(
            "eeroctl.commands.network.sqm.run_with_client",
            side_effect=_make_run_with_client(mock_client_true),
        ):
            result = runner.invoke(
                cli, ["--network-id", NID, "network", "sqm", "enable", "--force"]
            )

        mock_client_true.set_sqm_enabled.assert_called_once_with(True, NID)
        assert result.exit_code == 0

    def test_sqm_disable_passes_false(self, runner: CliRunner, mock_client_false: MagicMock):
        """sqm disable passes bare False boolean to set_sqm_enabled."""
        with patch(
            "eeroctl.commands.network.sqm.run_with_client",
            side_effect=_make_run_with_client(mock_client_false),
        ):
            result = runner.invoke(
                cli, ["--network-id", NID, "network", "sqm", "disable", "--force"]
            )

        mock_client_false.set_sqm_enabled.assert_called_once_with(False, NID)
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# TestDNS
# ---------------------------------------------------------------------------


class TestDNS:
    """Tests for DNS mutation commands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Mock EeroClient with DNS methods returning OK responses."""
        return _make_mock_client(set_dns_caching=_OK_RESPONSE, set_dns_mode=_OK_RESPONSE)

    def test_dns_caching_enable_calls_set_dns_caching(
        self, runner: CliRunner, mock_client: MagicMock
    ):
        """dns caching enable passes (True, network_id) to set_dns_caching."""
        with patch(
            "eeroctl.commands.network.dns.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(
                cli,
                ["--network-id", NID, "network", "dns", "caching", "enable", "--force"],
            )

        mock_client.set_dns_caching.assert_called_once_with(True, NID)
        assert result.exit_code == 0

    def test_dns_mode_set_calls_set_dns_mode(self, runner: CliRunner, mock_client: MagicMock):
        """dns mode set google passes (mode, servers, network_id) to set_dns_mode."""
        with patch(
            "eeroctl.commands.network.dns.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(
                cli,
                ["--network-id", NID, "network", "dns", "mode", "set", "google", "--force"],
            )

        # servers=None because no --servers flag was provided for a non-custom mode
        mock_client.set_dns_mode.assert_called_once_with("google", None, NID)
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# TestGuestNetwork
# ---------------------------------------------------------------------------


class TestGuestNetwork:
    """Tests for ``eero network guest enable`` → ``client.set_guest_network``."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Mock EeroClient with set_guest_network returning a 200 response."""
        return _make_mock_client(set_guest_network=_OK_RESPONSE)

    def test_guest_network_enable_calls_set_guest_network(
        self, runner: CliRunner, mock_client: MagicMock
    ):
        """guest enable invokes set_guest_network on the client."""
        with patch(
            "eeroctl.commands.network.guest.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(
                cli, ["--network-id", NID, "network", "guest", "enable", "--force"]
            )

        mock_client.set_guest_network.assert_called_once()
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# TestSecurityToggles
# ---------------------------------------------------------------------------


class TestSecurityToggles:
    """Tests for security toggle commands dispatched via _make_security_toggle factory."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def _invoke_security(
        self, runner: CliRunner, subcommand: str, method_name: str, expected_value: bool
    ):
        """Shared helper: patch run_with_client, invoke security subcommand, assert call."""
        mock_client = _make_mock_client(**{method_name: _OK_RESPONSE})
        with patch(
            "eeroctl.commands.network.security.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(
                cli,
                ["--network-id", NID, "network", "security", subcommand, "enable", "--force"],
            )
        getattr(mock_client, method_name).assert_called_once_with(expected_value, NID)
        assert result.exit_code == 0
        return result

    def test_security_toggle_wpa3_enable_calls_set_wpa3(self, runner: CliRunner):
        """wpa3 enable passes (True, network_id) to set_wpa3."""
        self._invoke_security(runner, "wpa3", "set_wpa3", True)

    def test_security_toggle_band_steering_enable_calls_set_band_steering(self, runner: CliRunner):
        """band-steering enable passes (True, network_id) to set_band_steering."""
        self._invoke_security(runner, "band-steering", "set_band_steering", True)

    def test_security_toggle_upnp_enable_calls_set_upnp(self, runner: CliRunner):
        """upnp enable passes (True, network_id) to set_upnp."""
        self._invoke_security(runner, "upnp", "set_upnp", True)

    def test_security_toggle_ipv6_enable_calls_set_ipv6(self, runner: CliRunner):
        """ipv6 enable passes (True, network_id) to set_ipv6."""
        self._invoke_security(runner, "ipv6", "set_ipv6", True)

    def test_security_toggle_thread_enable_calls_set_thread_enabled(self, runner: CliRunner):
        """thread enable maps CLI subcommand 'thread' to client method set_thread_enabled."""
        self._invoke_security(runner, "thread", "set_thread_enabled", True)


# ---------------------------------------------------------------------------
# TestMutationSuccessAndFailure
# ---------------------------------------------------------------------------


class TestMutationSuccessAndFailure:
    """Integration-level success/failure path tests using set_network_name as representative."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_mutation_success_meta_200_returns_exit_zero(self, runner: CliRunner):
        """When the mock returns meta.code 200, rename exits 0."""
        mock_client = _make_mock_client(set_network_name=_OK_RESPONSE)
        with patch(
            "eeroctl.commands.network.base.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(
                cli,
                ["network", "rename", "--name", "new-name", "--force", "--network-id", NID],
            )

        assert result.exit_code == 0

    def test_mutation_failure_meta_non_200_returns_nonzero(self, runner: CliRunner):
        """When the mock returns meta.code 500, rename exits non-zero."""
        mock_client = _make_mock_client(set_network_name=_ERR_RESPONSE)
        with patch(
            "eeroctl.commands.network.base.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(
                cli,
                ["network", "rename", "--name", "new-name", "--force", "--network-id", NID],
            )

        assert result.exit_code != 0
