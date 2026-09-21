"""Reject malicious ids and foreign-network links before any request.

Per the v8.0.1 migration plan §2.5 decision 2: eeroctl deliberately does
**not** pre-validate ids/paths/URLs typed by the caller -- it hands them to
the SDK verbatim and lets ``EeroValidationException`` map to exit 2 via
``handle_cli_error``/``run_with_client`` (plan §2.6). This module is the
"link-validation tests" called for in plan §5.2 and pins that contract
against the *real*, installed ``eero-api`` 8.0.1 -- never a
``MagicMock``/``AsyncMock`` client -- because the thing under test is the
SDK's own id-safety code (``eero/api/links.py``, ``eero/api/_params.py``),
not a mock's behaviour.

Two things are pinned here, at two different layers:

1. **SDK ground truth** (``TestSdkRejectsHostileIdsDirectly``,
   ``TestSdkRejectsCrossNetworkChildLinks``): the installed SDK really does
   raise ``EeroValidationException`` for every hostile id in the corpus
   below, and for a child link (device/forward/reservation/...) that
   belongs to a different network than the one addressed, or that carries a
   query/fragment -- in every case *before* the transport is touched. These
   tests call the SDK client directly and are not expected to fail.

2. **CLI reality check** (``TestEeroShowRejectsHostileIds`` and siblings):
   whether that SDK protection is actually reachable from the shipped
   ``eero <noun> show <id>`` commands. It mostly is not: every id-taking
   read command in this repo resolves its argument by fetching the full
   list and matching locally (``resolve_eero_identifier``, ``_find_device``,
   ``_find_profile``, the inline loop in ``forwards_show``) rather than
   forwarding the raw string to an id-validated SDK method. Each such gap is
   marked ``xfail(strict=True)`` with the exact file:line responsible, so a
   future fix that starts forwarding the id flips these to unexpected
   passes and fails the suite -- turning a silent gap into a checkpoint
   finding per this brief's instructions.
"""

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock

import pytest
from click.testing import CliRunner
from eero import EeroClient
from eero.exceptions import EeroValidationException

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli

# =====================================================================
# Corpus
# =====================================================================

# Verbatim from eero-api 8.0.1's own regression guard --
# tests/api/test_url_identifier_safety.py:58 (as extracted to
# /tmp/eero-api-v8.0.1/tests/api/test_url_identifier_safety.py for this
# migration). Ids designed to escape a single path segment, inject a query
# string, or break a `str.format` template.
HOSTILE_IDS = ("../../account", "x?y=1", "a/b", "{x}", "")

# Verbatim from test_url_identifier_safety.py:65 -- the subset still
# expected to raise for a method whose nested id is normalised via
# `id_from_url` before validation (not exercised by any eeroctl call site
# today, kept here for parity with the SDK's own corpus).
NORMALIZED_ID_HOSTILE_IDS = ("x?y=1", "{x}", "")

#: A device link a caller could plausibly paste from ``eero device list -o
#: json`` on network 999999, then pass to a command addressing network
#: 111111 with ``-n``. Rejected by `_require_nested_family`
#: (`eero/api/_params.py:171-216`, DIGEST.md §8): "the network segment must
#: equal `id_from_url(network)`... ('child', 'must belong to the addressed
#: network')" -- migration plan §1.5 row 1.
OTHER_NETWORK_DEVICE_URL = "https://api-user.e2ro.com/2.2/networks/999999/devices/aabbccddeeff"

#: A same-network device path carrying a fragment / query string. Rejected
#: by the same helper: "reject any query or fragment" (`_params.py:198-200`).
FRAGMENT_DEVICE_PATH = "/2.2/networks/111111/devices/aabbccddeeff#frag"
QUERY_DEVICE_PATH = "/2.2/networks/111111/devices/aabbccddeeff?x=1"

CHILD_LINK_HOSTILE_CASES = (
    pytest.param(OTHER_NETWORK_DEVICE_URL, id="device-url-on-other-network"),
    pytest.param(FRAGMENT_DEVICE_PATH, id="device-path-with-fragment"),
    pytest.param(QUERY_DEVICE_PATH, id="device-path-with-query"),
)

#: Positive-control id forms for network 111111 -- a bare id, a
#: host-relative path, and a full URL, per `eero/api/links.py:223-276`
#: (three-branch `resource_url`) / `_params.py:161-168` (bare-id vs.
#: path/URL child dispatch).
GOOD_DEVICE_MAC = "aabbccddeeff"
GOOD_DEVICE_PATH = "/2.2/networks/111111/devices/aabbccddeeff"
GOOD_DEVICE_URL = "https://api-user.e2ro.com/2.2/networks/111111/devices/aabbccddeeff"


# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture
def real_client() -> EeroClient:
    """A real, un-entered ``EeroClient`` with a session token already set.

    ``cookie_file=None, use_keyring=False`` selects the SDK's in-memory-only
    storage backend (no filesystem or OS-keyring I/O in these tests --
    eero-api 8.0.1 ``client.py:49-59``). A token is seeded via the public
    ``set_session_token`` so ``get_auth_token()`` succeeds and every code
    path under test -- id validation -- runs before any request would be
    dispatched anyway; whether the token is "real" is irrelevant to that.
    """
    client = EeroClient(cookie_file=None, use_keyring=False)
    asyncio.run(client.set_session_token("test-session-token"))
    return client


@pytest.fixture
def guarded_transport(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Fail loudly if any command attempts a real HTTP request.

    ``BaseAPI._request`` (``eero/api/base.py:416``) is the single method
    every verb helper (``get``/``post``/``put``/``delete``, via
    ``_request_with_get_retry`` at ``base.py:715-761``) funnels through, so
    patching it here traps every HTTP attempt from any facade method,
    regardless of which one is called.
    """
    guard = AsyncMock(side_effect=AssertionError("network call attempted"))
    monkeypatch.setattr("eero.api.base.BaseAPI._request", guard)
    return guard


@pytest.fixture
def wired_client(monkeypatch: pytest.MonkeyPatch, real_client: EeroClient) -> EeroClient:
    """Point ``build_client`` (the CLI's single construction site) at
    ``real_client`` instead of a freshly constructed one, for every command
    invoked in a test using this fixture."""
    monkeypatch.setattr("eeroctl.utils.build_client", lambda *args, **kwargs: real_client)
    return real_client


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _empty_envelope() -> Dict[str, Any]:
    return {"meta": {"code": 200}, "data": []}


# =====================================================================
# Section 1 -- SDK ground truth (real client, no CLI, no xfail)
#
# These pin the assumption every xfail below depends on: the installed
# eero-api 8.0.1 really does reject the corpus, before any request, when a
# caller hands it directly to an id-validated method. If eero-api ever
# weakens `_IDENTIFIER_RE` or `_require_nested_family`, these go red -- not
# just the xfails.
# =====================================================================


class TestSdkRejectsHostileIdsDirectly:
    """``EeroClient.get_eero`` rejects every id in the SDK's own hostile
    corpus before touching the transport (``eero/api/links.py:65-70``,
    bare-id branch of ``resource_url`` at ``links.py:276``)."""

    @pytest.mark.parametrize("hostile_id", HOSTILE_IDS)
    async def test_get_eero_rejects_hostile_id(self, real_client, guarded_transport, hostile_id):
        async with real_client:
            with pytest.raises(EeroValidationException):
                await real_client.get_eero(hostile_id, "111111")
        guarded_transport.assert_not_awaited()

    @pytest.mark.parametrize("hostile_id", NORMALIZED_ID_HOSTILE_IDS)
    async def test_get_led_status_rejects_hostile_id(
        self, real_client, guarded_transport, hostile_id
    ):
        async with real_client:
            with pytest.raises(EeroValidationException):
                await real_client.get_led_status(hostile_id, "111111")
        guarded_transport.assert_not_awaited()


class TestSdkRejectsCrossNetworkChildLinks:
    """``EeroClient.get_device`` rejects a device link naming a different
    network, or carrying a query/fragment, via ``_require_nested_family``
    (``eero/api/_params.py:171-216``) before touching the transport."""

    @pytest.mark.parametrize("child_link", [c.values[0] for c in CHILD_LINK_HOSTILE_CASES])
    async def test_get_device_rejects_hostile_child_link(
        self, real_client, guarded_transport, child_link
    ):
        async with real_client:
            with pytest.raises(EeroValidationException):
                await real_client.get_device(child_link, "111111")
        guarded_transport.assert_not_awaited()

    async def test_get_device_accepts_same_network_child_link_forms(self, real_client, monkeypatch):
        """Ground truth for the positive controls in Section 3: all three
        id forms for the *correct* network reach the transport rather than
        being rejected -- so the transport guard used elsewhere in this
        module is a real trap, not a fixture that silently no-ops."""
        guard = AsyncMock(return_value={"meta": {"code": 200}, "data": {}})
        monkeypatch.setattr("eero.api.base.BaseAPI._request", guard)
        async with real_client:
            for good_id in (GOOD_DEVICE_MAC, GOOD_DEVICE_PATH, GOOD_DEVICE_URL):
                guard.reset_mock()
                await real_client.get_device(good_id, "111111")
                guard.assert_awaited_once()


# =====================================================================
# Section 2 -- CLI reality check (xfail: the resolvers swallow the id)
# =====================================================================


class TestEeroShowRejectsHostileIds:
    """``eero eero show <id>``.

    XFAIL: ``resolve_eero_identifier`` (``commands/eero/base.py:27-76``)
    only attempts a direct, id-validated ``client.get_eero(...)`` call when
    ``identifier.isdigit()`` (``base.py:43``). Every string in the SDK's
    hostile-id corpus is non-digit, so all of them fall through to the
    list-then-match branch (``base.py:54-76``): ``client.get_eeros(...)`` is
    called (no id involved at all), then the hostile string is compared,
    in Python, against each eero's serial/name/location. It is never
    checked against the SDK's ``_IDENTIFIER_RE``. The command reports "not
    found" (exit 5) instead of "invalid" (exit 2), and reaches the
    transport for the *list* call before any rejection could occur.
    """

    @pytest.mark.xfail(
        reason=(
            "resolve_eero_identifier only validates a *digit* id directly "
            "against the SDK (commands/eero/base.py:43); every hostile, "
            "non-digit corpus string falls through to the list+match branch "
            "(base.py:54-76) and is reported as 'not found' (exit 5), never "
            "rejected as invalid (exit 2). See module docstring."
        ),
        strict=True,
    )
    @pytest.mark.parametrize("hostile_id", HOSTILE_IDS)
    def test_rejects_hostile_id_before_any_request(
        self, runner, wired_client, guarded_transport, hostile_id
    ):
        result = runner.invoke(cli, ["-n", "111111", "eero", "show", hostile_id])
        assert result.exit_code == ExitCode.USAGE_ERROR, result.output
        assert "invalid" in result.output.lower(), result.output
        guarded_transport.assert_not_awaited()


class TestDeviceShowRejectsHostileIds:
    """``eero device show <id>``.

    XFAIL: ``device_show`` always calls ``client.get_devices(...)`` first
    (``commands/device.py:192``) and matches locally via ``_find_device``
    (``device.py:30-58``, an equality/``.lower()`` comparison, never an SDK
    call) before it ever calls an id-scoped SDK method. A hostile string is
    therefore never validated -- it is "not found" (exit 5), and the
    transport is reached for the list call regardless of the id's shape.
    """

    @pytest.mark.xfail(
        reason=(
            "device_show (commands/device.py:177-224) always lists devices "
            "first and matches the raw identifier locally via _find_device "
            "(device.py:30-58); a hostile id is never handed to an "
            "id-validated SDK method, so it is reported 'not found' (exit "
            "5) rather than rejected as invalid (exit 2)."
        ),
        strict=True,
    )
    @pytest.mark.parametrize("hostile_id", HOSTILE_IDS)
    def test_rejects_hostile_id_before_any_request(
        self, runner, wired_client, guarded_transport, hostile_id
    ):
        result = runner.invoke(cli, ["-n", "111111", "device", "show", hostile_id])
        assert result.exit_code == ExitCode.USAGE_ERROR, result.output
        assert "invalid" in result.output.lower(), result.output
        guarded_transport.assert_not_awaited()

    @pytest.mark.xfail(
        reason=(
            "Same gap as the hostile-id case above: _find_device (device.py"
            ":30-58) matches the child link against dev['id'] as a plain "
            "string, so a same-shaped-but-foreign-network device URL is "
            "just 'not found' (exit 5); it never reaches _require_nested_"
            "family (eero-api _params.py:171-216) because device_show never "
            "calls client.get_device() with the raw CLI argument -- only "
            "with an id it already found in the list (device.py:222)."
        ),
        strict=True,
    )
    @pytest.mark.parametrize("child_link", CHILD_LINK_HOSTILE_CASES)
    def test_rejects_foreign_network_device_link(
        self, runner, wired_client, guarded_transport, child_link
    ):
        result = runner.invoke(cli, ["-n", "111111", "device", "show", child_link])
        assert result.exit_code == ExitCode.USAGE_ERROR, result.output
        assert "invalid" in result.output.lower(), result.output
        guarded_transport.assert_not_awaited()


class TestProfileShowRejectsHostileIds:
    """``eero profile show <id>``.

    XFAIL: same shape as device show. ``profile_show`` always calls
    ``client.get_profiles(...)`` first (``commands/profile.py:206``) and
    matches locally via ``_find_profile`` (``profile.py:34-50``).
    """

    @pytest.mark.xfail(
        reason=(
            "profile_show (commands/profile.py:191-238) always lists "
            "profiles first and matches the raw identifier locally via "
            "_find_profile (profile.py:34-50); a hostile id is never "
            "handed to an id-validated SDK method, so it is reported 'not "
            "found' (exit 5) rather than rejected as invalid (exit 2)."
        ),
        strict=True,
    )
    @pytest.mark.parametrize("hostile_id", HOSTILE_IDS)
    def test_rejects_hostile_id_before_any_request(
        self, runner, wired_client, guarded_transport, hostile_id
    ):
        result = runner.invoke(cli, ["-n", "111111", "profile", "show", hostile_id])
        assert result.exit_code == ExitCode.USAGE_ERROR, result.output
        assert "invalid" in result.output.lower(), result.output
        guarded_transport.assert_not_awaited()


class TestForwardsShowRejectsHostileIds:
    """``eero network forwards show <id>``.

    XFAIL: ``forwards_show`` always calls ``client.get_forwards(...)``
    first (``commands/network/forwards.py:97``) and matches locally with an
    inline loop comparing ``str(fwd.get("id")) == forward_id``
    (``forwards.py:102-105``) -- a plain string comparison, never an SDK
    call.
    """

    @pytest.mark.xfail(
        reason=(
            "forwards_show (commands/network/forwards.py:86-122) always "
            "lists forwards first and matches forward_id locally with a "
            "plain string comparison (forwards.py:102-105); a hostile id "
            "is never handed to an id-validated SDK method, so it is "
            "reported 'not found' (exit 5) rather than rejected as invalid "
            "(exit 2)."
        ),
        strict=True,
    )
    @pytest.mark.parametrize("hostile_id", HOSTILE_IDS)
    def test_rejects_hostile_id_before_any_request(
        self, runner, wired_client, guarded_transport, hostile_id
    ):
        result = runner.invoke(cli, ["-n", "111111", "network", "forwards", "show", hostile_id])
        assert result.exit_code == ExitCode.USAGE_ERROR, result.output
        assert "invalid" in result.output.lower(), result.output
        guarded_transport.assert_not_awaited()


class TestLedShowRejectsHostileIds:
    """``eero eero led show <id>``.

    XFAIL: ``led_show`` resolves its argument through the very same
    ``resolve_eero_identifier`` as ``eero show`` (``commands/eero/led.py
    :21,52``), so it has the identical digit-only-shortcut gap documented
    on ``TestEeroShowRejectsHostileIds``.
    """

    @pytest.mark.xfail(
        reason=(
            "led_show (commands/eero/led.py:39-83) resolves via the same "
            "resolve_eero_identifier as eero show (commands/eero/base.py:"
            "27-76); every hostile, non-digit corpus string falls through "
            "to list+match and is reported 'not found' (exit 5), never "
            "rejected as invalid (exit 2)."
        ),
        strict=True,
    )
    @pytest.mark.parametrize("hostile_id", HOSTILE_IDS)
    def test_rejects_hostile_id_before_any_request(
        self, runner, wired_client, guarded_transport, hostile_id
    ):
        result = runner.invoke(cli, ["-n", "111111", "eero", "led", "show", hostile_id])
        assert result.exit_code == ExitCode.USAGE_ERROR, result.output
        assert "invalid" in result.output.lower(), result.output
        guarded_transport.assert_not_awaited()


# =====================================================================
# Section 3 -- CLI positive controls
#
# `device show` is used because it unconditionally calls the SDK's list
# endpoint as its very first action (commands/device.py:192) for *every*
# identifier shape -- bare id, host-relative path, or full URL alike -- so
# it can demonstrate the transport guard is a real trap (not a fixture that
# silently no-ops) without depending on the digit-only shortcut that only
# `eero show`/`eero led show` have. We assert only that the transport was
# reached, never that the SDK *accepted* the identifier as a device link:
# as Section 2 documents, device_show never hands a raw path/URL to an
# id-validated SDK method, so there is nothing here for `_IDENTIFIER_RE` /
# `_require_nested_family` to accept or reject -- that acceptance path is
# pinned directly against the SDK in
# ``TestSdkRejectsCrossNetworkChildLinks.
# test_get_device_accepts_same_network_child_link_forms`` above instead.
# =====================================================================


class TestDeviceShowReachesTransportForEveryIdForm:
    @pytest.mark.parametrize(
        "device_identifier",
        [
            pytest.param(GOOD_DEVICE_MAC, id="bare-mac"),
            pytest.param(GOOD_DEVICE_PATH, id="host-relative-path"),
            pytest.param(GOOD_DEVICE_URL, id="full-url"),
        ],
    )
    def test_reaches_list_endpoint(self, runner, wired_client, monkeypatch, device_identifier):
        guard = AsyncMock(return_value=_empty_envelope())
        monkeypatch.setattr("eero.api.base.BaseAPI._request", guard)

        result = runner.invoke(cli, ["-n", "111111", "device", "show", device_identifier])

        guard.assert_awaited_once()
        assert result.exit_code == ExitCode.NOT_FOUND, result.output


class TestEeroShowReachesIdScopedEndpointForBareNumericId:
    """The one read path in this repo where the CLI *does* forward the raw
    argument to an id-validated SDK method: ``resolve_eero_identifier``'s
    digit shortcut (``commands/eero/base.py:43-49``)."""

    def test_bare_numeric_id_calls_get_eero_directly(self, runner, wired_client, monkeypatch):
        guard = AsyncMock(
            return_value={
                "meta": {"code": 200},
                "data": {"id": "123", "url": "/2.2/eeros/123", "serial": "SERIAL123"},
            }
        )
        monkeypatch.setattr("eero.api.base.BaseAPI._request", guard)

        result = runner.invoke(cli, ["-n", "111111", "eero", "show", "123"])

        guard.assert_awaited_once()
        assert result.exit_code == ExitCode.SUCCESS, result.output
