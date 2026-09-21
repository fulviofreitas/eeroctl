"""Mutation regression tests for eeroctl network commands.

Guards the contract between eeroctl mutation commands and the EeroClient methods
affected by the eero-api 4.1.2 routing/payload fix.  Each test patches
``run_with_client`` at the module where it is imported and asserts that the
correct EeroClient method is called with the expected positional arguments.

See PR42-PLAN.md §T1 for rationale.
"""

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _plain(text: str) -> str:
    """Strip ANSI escapes and line-wrap newlines from Rich console output.

    Rich wraps to the console width even under CliRunner (not a real tty)
    and re-applies styling per wrapped line, so a substring that happens to
    straddle a wrap point is broken up by escape codes and a newline. Tests
    that assert on longer strings normalize through this first.
    """
    return re.sub(r"\s+", " ", _ANSI_RE.sub("", text))


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_OK_RESPONSE = {"meta": {"code": 200, "error": None}, "data": {}}
_ERR_RESPONSE = {"meta": {"code": 500, "error": "boom"}, "data": {}}

# DNS writes read current state first, so DNS mocks need get_dns_settings.
# This state is automatic with no custom servers, so any set is a real change.
_DNS_STATE = {
    "meta": {"code": 200},
    "data": {
        "dns": {
            "mode": "automatic",
            "parent": {"ips": ["192.168.1.254"]},
            "custom": {"ips": []},
            "caching": False,
            "default_test_servers": [
                {
                    "name": "Cloudflare",
                    "ipv4": ["1.1.1.1", "1.0.0.1"],
                    "ipv6": ["2606:4700:4700::1111", "2606:4700:4700::1001"],
                },
                {
                    "name": "Google",
                    "ipv4": ["8.8.8.8", "8.8.4.4"],
                    "ipv6": ["2001:4860:4860::8888", "2001:4860:4860::8844"],
                },
                {"name": "Quad9", "ipv4": ["9.9.9.9", "149.112.112.112"], "ipv6": ["2620:fe::fe"]},
            ],
        },
        "ipv6": {"name_servers": {"mode": "automatic", "custom": []}},
    },
}

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


def _make_sdk_client(**method_return_values) -> AsyncMock:
    """Build an AsyncMock EeroClient patched in at the SDK boundary.

    Unlike ``_make_mock_client`` (paired with a ``run_with_client`` patch
    per command module), this mocks ``eeroctl.utils.EeroClient`` itself --
    the single construction site every command funnels through
    (``build_client``) -- so it exercises the real ``run_with_client`` /
    ``build_client`` / ``write_if_changed`` path end to end, not just the
    command function body.
    """
    client = AsyncMock()
    for method_name, return_value in method_return_values.items():
        setattr(client, method_name, AsyncMock(return_value=return_value))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
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
    """Tests for ``eero network sqm enable/disable`` → ``client.set_sqm``.

    eero-api 8.0.1 removed `set_sqm_enabled`; `set_sqm` is its replacement
    (client.py:2174, migration plan §2.3).
    """

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_client_true(self) -> MagicMock:
        """Mock client returning truthy response for set_sqm.

        ``get_sqm_settings`` reports the opposite of the desired state, so
        the new read-first/skip-unchanged wiring (``write_if_changed``)
        still issues the write instead of skipping it as a no-op.
        """
        return _make_mock_client(
            get_sqm_settings={"meta": {"code": 200}, "data": {"enabled": False}},
            set_sqm=_OK_RESPONSE,
        )

    @pytest.fixture
    def mock_client_false(self) -> MagicMock:
        """Mock client returning truthy response for set_sqm (disable path)."""
        return _make_mock_client(
            get_sqm_settings={"meta": {"code": 200}, "data": {"enabled": True}},
            set_sqm=_OK_RESPONSE,
        )

    def test_sqm_enable_calls_set_sqm_with_boolean(
        self, runner: CliRunner, mock_client_true: MagicMock
    ):
        """sqm enable passes bare True boolean to set_sqm."""
        with patch(
            "eeroctl.commands.network.sqm.run_with_client",
            side_effect=_make_run_with_client(mock_client_true),
        ):
            result = runner.invoke(
                cli, ["--network-id", NID, "network", "sqm", "enable", "--force"]
            )

        mock_client_true.set_sqm.assert_called_once_with(True, NID)
        assert result.exit_code == 0

    def test_sqm_disable_passes_false(self, runner: CliRunner, mock_client_false: MagicMock):
        """sqm disable passes bare False boolean to set_sqm."""
        with patch(
            "eeroctl.commands.network.sqm.run_with_client",
            side_effect=_make_run_with_client(mock_client_false),
        ):
            result = runner.invoke(
                cli, ["--network-id", NID, "network", "sqm", "disable", "--force"]
            )

        mock_client_false.set_sqm.assert_called_once_with(False, NID)
        assert result.exit_code == 0

    def test_sqm_enable_is_now_high_risk_and_requires_reboot_phrase(
        self, runner: CliRunner, mock_client_true: MagicMock
    ):
        """SQM was lifted from MEDIUM to HIGH mesh-reboot (migration plan Q3)."""
        with patch(
            "eeroctl.commands.network.sqm.run_with_client",
            side_effect=_make_run_with_client(mock_client_true),
        ):
            result = runner.invoke(
                cli, ["--network-id", NID, "network", "sqm", "enable"], input="REBOOT\n"
            )

        assert "REBOOT" in result.output
        assert result.exit_code == 0
        mock_client_true.set_sqm.assert_called_once_with(True, NID)

    def test_sqm_enable_force_still_warns_about_the_reboot(
        self, runner: CliRunner, mock_client_true: MagicMock
    ):
        """--force skips the prompt but not the reboot warning.

        The warning must land on stderr -- not stdout, which stays clean
        for ``--output json | jq`` even on write commands -- so the streams
        are checked separately rather than via the combined ``.output``.
        """
        with patch(
            "eeroctl.commands.network.sqm.run_with_client",
            side_effect=_make_run_with_client(mock_client_true),
        ):
            result = runner.invoke(
                cli, ["--network-id", NID, "network", "sqm", "enable", "--force"]
            )

        assert result.exit_code == 0
        assert "reboots every eero" in result.stderr
        assert "reboots every eero" not in result.stdout


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
        return _make_mock_client(
            get_dns_settings=_DNS_STATE,
            set_dns_caching=_OK_RESPONSE,
            set_dns_mode=_OK_RESPONSE,
            set_custom_dns=_OK_RESPONSE,
            set_custom_dns_ipv4=_OK_RESPONSE,
            set_custom_dns_ipv6=_OK_RESPONSE,
            clear_custom_dns=_OK_RESPONSE,
        )

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

    def test_dns_mode_set_resolves_provider_from_catalogue(
        self, runner: CliRunner, mock_client: MagicMock
    ):
        """A provider name resolves CLI-side to its catalogue addresses.

        eero-api 7.0.0 removed the named presets from set_dns_mode, so eeroctl
        resolves them against data.dns.default_test_servers and writes the
        addresses. Providers default to IPv4 only.
        """
        with patch(
            "eeroctl.commands.network.dns.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(
                cli,
                ["--network-id", NID, "network", "dns", "mode", "set", "google", "--force"],
            )

        assert result.exit_code == 0
        mock_client.set_custom_dns_ipv4.assert_called_once_with(["8.8.8.8", "8.8.4.4"], NID)
        mock_client.set_dns_mode.assert_not_called()


# ---------------------------------------------------------------------------
# TestDNSWriteSafetyRails
# ---------------------------------------------------------------------------


class TestDNSWriteSafetyRails:
    """Tests that DNS writes are gated as network-reboot operations.

    A DNS write reboots every eero on the network, so these commands require a
    typed confirmation phrase rather than a Y/N prompt.
    """

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Mock EeroClient with DNS write methods returning 200 responses."""
        return _make_mock_client(
            get_dns_settings=_DNS_STATE,
            set_dns_caching=_OK_RESPONSE,
            set_dns_mode=_OK_RESPONSE,
            set_custom_dns=_OK_RESPONSE,
            set_custom_dns_ipv4=_OK_RESPONSE,
            set_custom_dns_ipv6=_OK_RESPONSE,
            clear_custom_dns=_OK_RESPONSE,
        )

    def _invoke(self, runner, mock_client, args, **kwargs):
        """Run a DNS command against the mocked client."""
        with patch(
            "eeroctl.commands.network.dns.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            return runner.invoke(cli, ["--network-id", NID, *args], **kwargs)

    # -- typed confirmation -------------------------------------------------

    @pytest.mark.parametrize(
        "args",
        [
            ["network", "dns", "mode", "set", "google"],
            ["network", "dns", "caching", "enable"],
            ["network", "dns", "caching", "disable"],
        ],
    )
    def test_prompt_asks_for_reboot_phrase(self, runner, mock_client, args):
        """The prompt asks for REBOOT, not an auto-derived string."""
        result = self._invoke(runner, mock_client, args, input="REBOOT\n")

        assert "REBOOT" in result.output
        assert "CHANGEDNSMODE" not in result.output
        assert "ENABLEDNSCACHING" not in result.output

    def test_correct_phrase_proceeds(self, runner, mock_client):
        """Typing REBOOT allows the write."""
        result = self._invoke(
            runner, mock_client, ["network", "dns", "caching", "enable"], input="REBOOT\n"
        )

        assert result.exit_code == 0
        mock_client.set_dns_caching.assert_called_once_with(True, NID)

    def test_wrong_phrase_is_a_safety_rail_failure(self, runner, mock_client):
        """A mistyped phrase exits 8 and performs no write."""
        result = self._invoke(
            runner, mock_client, ["network", "dns", "caching", "enable"], input="reboot\n"
        )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_dns_caching.assert_not_called()

    # -- reboot warning -----------------------------------------------------

    @pytest.mark.parametrize(
        "args",
        [
            ["network", "dns", "mode", "set", "google", "--force"],
            ["network", "dns", "caching", "enable", "--force"],
            ["network", "dns", "caching", "disable", "--force"],
        ],
    )
    def test_force_still_warns_about_the_reboot(self, runner, mock_client, args):
        """--force skips the prompt but must not silence the warning."""
        result = self._invoke(runner, mock_client, args)

        assert result.exit_code == 0
        assert "reboots every eero" in result.output

    def test_non_interactive_with_force_warns_and_proceeds(self, runner, mock_client):
        """Scripted callers get the warning too."""
        result = self._invoke(
            runner,
            mock_client,
            ["--non-interactive", "network", "dns", "caching", "enable", "--force"],
        )

        assert result.exit_code == 0
        assert "reboots every eero" in result.output

    # -- --force placement --------------------------------------------------

    def test_global_force_bypasses_prompt(self, runner, mock_client):
        """The root --force is honoured, not just the per-command flag."""
        result = self._invoke(
            runner, mock_client, ["--force", "network", "dns", "caching", "enable"]
        )

        assert result.exit_code == 0
        mock_client.set_dns_caching.assert_called_once_with(True, NID)

    # -- non-interactive ----------------------------------------------------

    @pytest.mark.parametrize(
        "args",
        [
            ["network", "dns", "mode", "set", "google"],
            ["network", "dns", "caching", "enable"],
        ],
    )
    def test_non_interactive_without_force_fails_cleanly(self, runner, mock_client, args):
        """Never hangs on a prompt, never silently proceeds: exit 8, no write."""
        result = self._invoke(runner, mock_client, ["--non-interactive", *args])

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.set_dns_caching.assert_not_called()
        mock_client.set_dns_mode.assert_not_called()

    # -- success check ------------------------------------------------------

    def test_error_response_is_not_reported_as_success(self, runner):
        """A non-2xx meta.code fails rather than passing a truthiness check."""
        client = _make_mock_client(set_dns_caching=_ERR_RESPONSE)

        result = self._invoke(runner, client, ["network", "dns", "caching", "enable", "--force"])

        assert result.exit_code != 0
        assert "DNS caching enabled" not in result.output

    def test_fabricated_400_is_not_reported_as_success(self, runner):
        """The truthy {"meta": {"code": 400}} the SDK used to fabricate must fail."""
        client = _make_mock_client(set_dns_mode={"meta": {"code": 400}, "data": {}})

        result = self._invoke(
            runner, client, ["network", "dns", "mode", "set", "google", "--force"]
        )

        assert result.exit_code != 0
        assert "DNS mode set" not in result.output

    def test_response_without_meta_is_not_reported_as_success(self, runner):
        """An unrecognised shape is a failure, not an assumed success."""
        client = _make_mock_client(set_dns_caching={})

        result = self._invoke(runner, client, ["network", "dns", "caching", "enable", "--force"])

        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# TestDNSPresetResolution
# ---------------------------------------------------------------------------


class TestDNSPresetResolution:
    """Provider names resolve against the network's own catalogue.

    eero-api 7.0.0 removed named presets from set_dns_mode, so eeroctl resolves
    them from data.dns.default_test_servers instead of a hardcoded list.
    """

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Mock EeroClient serving the provider catalogue."""
        return _make_mock_client(
            get_dns_settings=_DNS_STATE,
            set_dns_mode=_OK_RESPONSE,
            set_custom_dns=_OK_RESPONSE,
            set_custom_dns_ipv4=_OK_RESPONSE,
            set_custom_dns_ipv6=_OK_RESPONSE,
            clear_custom_dns=_OK_RESPONSE,
        )

    def _invoke(self, runner, client, args):
        """Run a DNS command against the mocked client."""
        with patch(
            "eeroctl.commands.network.dns.run_with_client",
            side_effect=_make_run_with_client(client),
        ):
            return runner.invoke(cli, ["--network-id", NID, *args])

    @pytest.mark.parametrize("name", ["google", "Google", "GOOGLE"])
    def test_provider_match_is_case_insensitive(self, runner, mock_client, name):
        """The API serves Title-Case names; users type lowercase."""
        result = self._invoke(
            runner, mock_client, ["network", "dns", "mode", "set", name, "--force"]
        )

        assert result.exit_code == 0
        mock_client.set_custom_dns_ipv4.assert_called_once_with(["8.8.8.8", "8.8.4.4"], NID)

    def test_quad9_resolves_without_being_enumerated(self, runner, mock_client):
        """A provider eeroctl hardcodes nowhere still works.

        This is the point of resolving from the catalogue.
        """
        result = self._invoke(
            runner, mock_client, ["network", "dns", "mode", "set", "quad9", "--force"]
        )

        assert result.exit_code == 0
        mock_client.set_custom_dns_ipv4.assert_called_once_with(["9.9.9.9", "149.112.112.112"], NID)

    def test_provider_family_both_writes_ipv6_too(self, runner, mock_client):
        """--family both opts into the IPv6 half of the catalogue entry."""
        result = self._invoke(
            runner,
            mock_client,
            ["network", "dns", "mode", "set", "google", "--family", "both", "--force"],
        )

        assert result.exit_code == 0
        mock_client.set_custom_dns.assert_called_once_with(
            ["8.8.8.8", "8.8.4.4", "2001:4860:4860::8888", "2001:4860:4860::8844"], NID
        )

    def test_unknown_provider_lists_available_names(self, runner, mock_client):
        """A typo exits 2 and names what the catalogue actually served."""
        result = self._invoke(
            runner, mock_client, ["network", "dns", "mode", "set", "cloudfare", "--force"]
        )

        assert result.exit_code == ExitCode.USAGE_ERROR
        assert "Cloudflare" in result.output
        assert "Quad9" in result.output
        mock_client.set_custom_dns_ipv4.assert_not_called()

    def test_missing_catalogue_falls_back_for_known_providers(self, runner):
        """Without a catalogue, the three SDK-legacy providers still work."""
        state = {"meta": {"code": 200}, "data": {"dns": {"mode": "automatic"}, "ipv6": {}}}
        client = _make_mock_client(get_dns_settings=state, set_custom_dns_ipv4=_OK_RESPONSE)

        result = self._invoke(
            runner, client, ["network", "dns", "mode", "set", "cloudflare", "--force"]
        )

        assert result.exit_code == 0
        client.set_custom_dns_ipv4.assert_called_once_with(["1.1.1.1", "1.0.0.1"], NID)

    def test_missing_catalogue_fails_for_unknown_provider(self, runner):
        """quad9 has no built-in fallback, so it fails rather than being invented."""
        state = {"meta": {"code": 200}, "data": {"dns": {"mode": "automatic"}, "ipv6": {}}}
        client = _make_mock_client(get_dns_settings=state, set_custom_dns_ipv4=_OK_RESPONSE)

        result = self._invoke(runner, client, ["network", "dns", "mode", "set", "quad9", "--force"])

        assert result.exit_code == ExitCode.USAGE_ERROR
        client.set_custom_dns_ipv4.assert_not_called()


# ---------------------------------------------------------------------------
# TestDNSServerValidation
# ---------------------------------------------------------------------------


class TestDNSServerValidation:
    """--servers is validated before the confirmation prompt.

    Validation running first matters: a user must never be asked to approve a
    network reboot for input that will be rejected anyway.
    """

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Mock EeroClient for validation tests."""
        return _make_mock_client(
            get_dns_settings=_DNS_STATE,
            set_custom_dns=_OK_RESPONSE,
            set_custom_dns_ipv4=_OK_RESPONSE,
            set_custom_dns_ipv6=_OK_RESPONSE,
        )

    def _invoke(self, runner, client, args, **kwargs):
        """Run a DNS command against the mocked client."""
        with patch(
            "eeroctl.commands.network.dns.run_with_client",
            side_effect=_make_run_with_client(client),
        ):
            return runner.invoke(cli, ["--network-id", NID, *args], **kwargs)

    def test_three_ipv4_servers_rejected_before_prompt(self, runner, mock_client):
        """Over-limit input exits 2 without ever prompting."""
        result = self._invoke(
            runner,
            mock_client,
            [
                "network",
                "dns",
                "mode",
                "set",
                "custom",
                "-s",
                "1.1.1.1",
                "-s",
                "1.0.0.1",
                "-s",
                "8.8.8.8",
            ],
            input="REBOOT\n",
        )

        assert result.exit_code == ExitCode.USAGE_ERROR
        assert "at most 2 IPv4" in result.output
        assert "REBOOT" not in result.output
        mock_client.set_custom_dns.assert_not_called()

    def test_two_per_family_is_accepted(self, runner, mock_client):
        """The cap is per family, so 2 IPv4 plus 2 IPv6 is fine."""
        result = self._invoke(
            runner,
            mock_client,
            [
                "network",
                "dns",
                "mode",
                "set",
                "custom",
                "--force",
                "-s",
                "1.1.1.1",
                "-s",
                "1.0.0.1",
                "-s",
                "2606:4700:4700::1111",
                "-s",
                "2606:4700:4700::1001",
            ],
        )

        assert result.exit_code == 0
        mock_client.set_custom_dns.assert_called_once()

    def test_malformed_literal_rejected(self, runner, mock_client):
        """A non-IP value exits 2."""
        result = self._invoke(
            runner,
            mock_client,
            ["network", "dns", "mode", "set", "custom", "-s", "not-an-ip"],
            input="REBOOT\n",
        )

        assert result.exit_code == ExitCode.USAGE_ERROR
        assert "not a valid IP address" in result.output

    def test_zone_identifier_rejected(self, runner, mock_client):
        """A zone-scoped address is not valid for a DNS server."""
        result = self._invoke(
            runner,
            mock_client,
            ["network", "dns", "mode", "set", "custom", "-s", "fe80::1%eth0"],
            input="REBOOT\n",
        )

        assert result.exit_code == ExitCode.USAGE_ERROR
        assert "zone identifier" in result.output

    def test_family_ipv6_routes_to_ipv6_setter(self, runner, mock_client):
        """--family ipv6 writes only the IPv6 half."""
        result = self._invoke(
            runner,
            mock_client,
            [
                "network",
                "dns",
                "mode",
                "set",
                "custom",
                "--force",
                "--family",
                "ipv6",
                "-s",
                "2606:4700:4700::1111",
            ],
        )

        assert result.exit_code == 0
        mock_client.set_custom_dns_ipv6.assert_called_once_with(["2606:4700:4700::1111"], NID)


# ---------------------------------------------------------------------------
# TestDNSNoOpSkip
# ---------------------------------------------------------------------------


_DNS_STATE_CLOUDFLARE = {
    "meta": {"code": 200},
    "data": {
        "dns": {
            "mode": "custom",
            "custom": {"ips": ["1.1.1.1", "1.0.0.1"]},
            "caching": False,
            "default_test_servers": _DNS_STATE["data"]["dns"]["default_test_servers"],
        },
        "ipv6": {
            "name_servers": {
                "mode": "custom",
                # Stored expanded, as the API does.
                "custom": ["2606:4700:4700:0:0:0:0:1111", "2606:4700:4700:0:0:0:0:1001"],
            }
        },
    },
}


class TestDNSNoOpSkip:
    """Writes are skipped when the configuration already matches.

    Without this, a scheduled job reboots the mesh on every run.
    """

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Mock already configured with Cloudflare on both families."""
        return _make_mock_client(
            get_dns_settings=_DNS_STATE_CLOUDFLARE,
            set_custom_dns=_OK_RESPONSE,
            set_custom_dns_ipv4=_OK_RESPONSE,
            clear_custom_dns=_OK_RESPONSE,
        )

    def _invoke(self, runner, client, args, **kwargs):
        """Run a DNS command against the mocked client."""
        with patch(
            "eeroctl.commands.network.dns.run_with_client",
            side_effect=_make_run_with_client(client),
        ):
            return runner.invoke(cli, ["--network-id", NID, *args], **kwargs)

    def test_unchanged_config_skips_write_and_prompt(self, runner, mock_client):
        """Already-applied config exits 0 with no write and no prompt."""
        result = self._invoke(runner, mock_client, ["network", "dns", "mode", "set", "cloudflare"])

        assert result.exit_code == 0
        assert "already configured" in result.output
        assert "REBOOT" not in result.output
        mock_client.set_custom_dns_ipv4.assert_not_called()

    def test_force_rewrites_unchanged_config_with_warning(self, runner, mock_client):
        """--force forces the rewrite and says so.

        Pins the accepted trade-off: --force means both "skip the prompt" and
        "write anyway", so a scheduled caller has no idempotent path.
        """
        result = self._invoke(
            runner, mock_client, ["network", "dns", "mode", "set", "cloudflare", "--force"]
        )

        assert result.exit_code == 0
        assert "rewriting anyway" in result.output
        mock_client.set_custom_dns_ipv4.assert_called_once()

    def test_ipv6_comparison_ignores_expanded_form(self, runner, mock_client):
        """Stored IPv6 is expanded, the catalogue is compressed.

        A string comparison would always differ and reboot the mesh every run.
        """
        result = self._invoke(
            runner,
            mock_client,
            ["network", "dns", "mode", "set", "cloudflare", "--family", "both"],
        )

        assert result.exit_code == 0
        assert "already configured" in result.output
        mock_client.set_custom_dns.assert_not_called()

    def test_changed_config_proceeds_to_prompt(self, runner, mock_client):
        """A genuine change still asks for confirmation."""
        result = self._invoke(
            runner, mock_client, ["network", "dns", "mode", "set", "google"], input="REBOOT\n"
        )

        assert result.exit_code == 0
        mock_client.set_custom_dns_ipv4.assert_called_once_with(["8.8.8.8", "8.8.4.4"], NID)


# ---------------------------------------------------------------------------
# TestDNSClear
# ---------------------------------------------------------------------------


class TestDNSClear:
    """Tests for the non-destructive clear."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Mock currently on custom DNS, so a clear is a real change."""
        return _make_mock_client(
            get_dns_settings=_DNS_STATE_CLOUDFLARE, clear_custom_dns=_OK_RESPONSE
        )

    def _invoke(self, runner, client, args, **kwargs):
        """Run a DNS command against the mocked client."""
        with patch(
            "eeroctl.commands.network.dns.run_with_client",
            side_effect=_make_run_with_client(client),
        ):
            return runner.invoke(cli, ["--network-id", NID, *args], **kwargs)

    def test_clear_calls_clear_custom_dns_for_both_families(self, runner, mock_client):
        """No --family clears both."""
        result = self._invoke(runner, mock_client, ["network", "dns", "clear", "--force"])

        assert result.exit_code == 0
        mock_client.clear_custom_dns.assert_called_once_with(None, NID)

    def test_clear_family_ipv4(self, runner, mock_client):
        """--family ipv4 is passed through to the SDK."""
        result = self._invoke(
            runner, mock_client, ["network", "dns", "clear", "--family", "ipv4", "--force"]
        )

        assert result.exit_code == 0
        mock_client.clear_custom_dns.assert_called_once_with("ipv4", NID)

    def test_clear_requires_confirmation(self, runner, mock_client):
        """clear is a write and reboots the mesh, so it prompts like any other."""
        result = self._invoke(runner, mock_client, ["network", "dns", "clear"], input="REBOOT\n")

        assert result.exit_code == 0
        assert "reboots every eero" in result.output
        mock_client.clear_custom_dns.assert_called_once()

    def test_clear_non_interactive_without_force_fails(self, runner, mock_client):
        """Exit 8, no write, no hang."""
        result = self._invoke(runner, mock_client, ["--non-interactive", "network", "dns", "clear"])

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.clear_custom_dns.assert_not_called()

    def test_clear_says_servers_are_retained(self, runner, mock_client):
        """The success message must not imply servers were discarded."""
        result = self._invoke(runner, mock_client, ["network", "dns", "clear", "--force"])

        assert "retained" in result.output

    def test_clear_skips_when_already_automatic(self, runner):
        """No-op skip applies to clear too."""
        client = _make_mock_client(get_dns_settings=_DNS_STATE, clear_custom_dns=_OK_RESPONSE)

        result = self._invoke(runner, client, ["network", "dns", "clear"])

        assert result.exit_code == 0
        assert "already automatic" in result.output
        client.clear_custom_dns.assert_not_called()


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
        """Mock EeroClient with set_guest_network returning a 200 response.

        ``get_network`` reports the guest network as disabled, the opposite
        of what ``guest enable`` requests, so ``write_if_changed`` does not
        skip the write as a no-op.
        """
        return _make_mock_client(
            get_network={
                "meta": {"code": 200},
                "data": {"url": "/2.2/networks/1", "guest_network": {"enabled": False}},
            },
            set_guest_network=_OK_RESPONSE,
        )

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
        """Shared helper: patch run_with_client, invoke security subcommand, assert call.

        ``get_security_settings`` reports the opposite of the desired state
        so ``write_if_changed`` does not skip the write as a no-op.
        """
        mock_client = _make_mock_client(
            get_security_settings={"meta": {"code": 200}, "data": {}},
            **{method_name: _OK_RESPONSE},
        )
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

    @pytest.mark.parametrize("subcommand", ["wpa3", "band-steering", "upnp", "ipv6"])
    def test_mesh_reboot_toggles_require_reboot_phrase(self, runner: CliRunner, subcommand: str):
        """wpa3/band-steering/upnp/ipv6 were lifted to HIGH mesh-reboot (Q3, decided)."""
        method_name = {
            "wpa3": "set_wpa3",
            "band-steering": "set_band_steering",
            "upnp": "set_upnp",
            "ipv6": "set_ipv6",
        }[subcommand]
        mock_client = _make_mock_client(
            get_security_settings={"meta": {"code": 200}, "data": {}},
            **{method_name: _OK_RESPONSE},
        )
        with patch(
            "eeroctl.commands.network.security.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(
                cli,
                ["--network-id", NID, "network", "security", subcommand, "enable"],
                input="REBOOT\n",
            )

        assert "REBOOT" in result.output
        assert result.exit_code == 0
        getattr(mock_client, method_name).assert_called_once_with(True, NID)

    def test_thread_toggle_stays_medium_risk(self, runner: CliRunner):
        """thread was not lifted to HIGH; a plain Y/N confirms it."""
        mock_client = _make_mock_client(
            get_security_settings={"meta": {"code": 200}, "data": {}},
            set_thread_enabled=_OK_RESPONSE,
        )
        with patch(
            "eeroctl.commands.network.security.run_with_client",
            side_effect=_make_run_with_client(mock_client),
        ):
            result = runner.invoke(
                cli,
                ["--network-id", NID, "network", "security", "thread", "enable"],
                input="y\n",
            )

        assert result.exit_code == 0
        mock_client.set_thread_enabled.assert_called_once_with(True, NID)


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


# ---------------------------------------------------------------------------
# TestSkipUnchangedAndReadCommandHints
# ---------------------------------------------------------------------------


class TestSkipUnchangedAndReadCommandHints:
    """Integration coverage for the ``write_if_changed`` skip-unchanged path
    and the per-command ``read_command`` hint (migration plan §3.2 item 4,
    §3.3), for every network-domain command wired to it.

    Uses the SDK-boundary mock (``eeroctl.utils.EeroClient``), not a
    ``run_with_client`` patch, so the real ``build_client`` /
    ``run_with_client`` / ``write_if_changed`` plumbing is exercised.
    """

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    # -- network sqm enable ---------------------------------------------

    def test_sqm_enable_already_configured_skips_the_write(self, runner: CliRunner):
        """Confirmed via the typed REBOOT phrase, not --force: --force also
        forces write_if_changed to write regardless of skip-unchanged (its
        documented contract), which would mask the skip path this test
        exists to cover."""
        mock_client = _make_sdk_client(
            get_sqm_settings={"meta": {"code": 200}, "data": {"enabled": True}},
            set_sqm=_OK_RESPONSE,
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--network-id", NID, "network", "sqm", "enable"], input="REBOOT\n"
            )

        assert result.exit_code == 0
        mock_client.set_sqm.assert_not_awaited()
        plain_output = _plain(result.output)
        assert "already" in plain_output.lower()
        assert "eero network sqm show" in plain_output

    def test_sqm_enable_changed_state_writes_and_hints_read_command(self, runner: CliRunner):
        mock_client = _make_sdk_client(
            get_sqm_settings={"meta": {"code": 200}, "data": {"enabled": False}},
            set_sqm=_OK_RESPONSE,
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--network-id", NID, "network", "sqm", "enable", "--force"]
            )

        assert result.exit_code == 0
        mock_client.set_sqm.assert_awaited_once_with(True, NID)
        assert "verify with `eero network sqm show`" in _plain(result.output).lower()

    # -- network security wpa3 (one representative toggle) --------------

    def test_security_wpa3_enable_already_configured_skips_the_write(self, runner: CliRunner):
        """Confirmed via the typed REBOOT phrase, not --force (see the sqm
        test above for why --force is unsuitable for a skip-path test)."""
        mock_client = _make_sdk_client(
            get_security_settings={"meta": {"code": 200}, "data": {"wpa3": True}},
            set_wpa3=_OK_RESPONSE,
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["--network-id", NID, "network", "security", "wpa3", "enable"],
                input="REBOOT\n",
            )

        assert result.exit_code == 0
        mock_client.set_wpa3.assert_not_awaited()
        plain_output = _plain(result.output)
        assert "already" in plain_output.lower()
        assert "eero network security show" in plain_output

    def test_security_wpa3_enable_changed_state_writes_and_hints_read_command(
        self, runner: CliRunner
    ):
        mock_client = _make_sdk_client(
            get_security_settings={"meta": {"code": 200}, "data": {"wpa3": False}},
            set_wpa3=_OK_RESPONSE,
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--network-id", NID, "network", "security", "wpa3", "enable", "--force"]
            )

        assert result.exit_code == 0
        mock_client.set_wpa3.assert_awaited_once_with(True, NID)
        assert "verify with `eero network security show`" in _plain(result.output).lower()

    # -- network guest enable/disable ------------------------------------

    def test_guest_enable_already_configured_skips_the_write(self, runner: CliRunner):
        """Confirmed via a plain Y, not --force (see the sqm test above for
        why --force is unsuitable for a skip-path test)."""
        mock_client = _make_sdk_client(
            get_network={
                "meta": {"code": 200},
                "data": {"url": "/2.2/networks/1", "guest_network": {"enabled": True}},
            },
            set_guest_network=_OK_RESPONSE,
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--network-id", NID, "network", "guest", "enable"], input="y\n"
            )

        assert result.exit_code == 0
        mock_client.set_guest_network.assert_not_awaited()
        plain_output = _plain(result.output)
        assert "already" in plain_output.lower()
        assert "eero network guest show" in plain_output

    def test_guest_disable_changed_state_writes_and_hints_read_command(self, runner: CliRunner):
        mock_client = _make_sdk_client(
            get_network={
                "meta": {"code": 200},
                "data": {"url": "/2.2/networks/1", "guest_network": {"enabled": True}},
            },
            set_guest_network=_OK_RESPONSE,
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--network-id", NID, "network", "guest", "disable", "--force"]
            )

        assert result.exit_code == 0
        mock_client.set_guest_network.assert_awaited_once()
        assert "verify with `eero network guest show`" in _plain(result.output).lower()

    # -- --force placement stream isolation (item 2) ---------------------

    def test_sqm_enable_force_warning_is_on_stderr_stdout_clean(self, runner: CliRunner):
        """--force skips the prompt but not the reboot warning -- and the
        warning must be on stderr, not stdout (so `--output json | jq`
        keeps working on any command that also prints structured data)."""
        mock_client = _make_sdk_client(
            get_sqm_settings={"meta": {"code": 200}, "data": {"enabled": False}},
            set_sqm=_OK_RESPONSE,
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--network-id", NID, "network", "sqm", "enable", "--force"]
            )

        assert result.exit_code == 0
        assert "reboots every eero" in result.stderr
        assert "reboots every eero" not in result.stdout
