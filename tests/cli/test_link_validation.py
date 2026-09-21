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
   ``eero <noun> show <id>`` commands.

   As of ``fix(cli): pass id, path and URL inputs to the SDK unchanged``,
   ``resolve_eero_identifier`` (``commands/eero/base.py``), ``device_show``
   and ``profile_show`` all short-circuit to the id-validated SDK method
   (``get_eero``/``get_device``/``get_profile``) verbatim, via the shared
   ``looks_like_sdk_reference`` helper (``utils.py``), whenever the input
   looks like a path/URL/hostile id -- so ``TestEeroShowRejectsHostileIds``,
   ``TestDeviceShowRejectsHostileIds``, ``TestProfileShowRejectsHostileIds``
   and ``TestLedShowRejectsHostileIds`` (``led_show`` shares
   ``resolve_eero_identifier``) are no longer ``xfail``: they assert the
   real, fixed behaviour.

   ``TestForwardsShowRejectsHostileIds`` stays ``xfail(strict=True)``: the
   facade exposes no singular id-validated *read* for a port forward (only
   ``get_forwards`` -- a list -- plus ``update_forward``/``delete_forward``,
   which are writes and therefore unsafe to call from a read command just to
   borrow their id validation). Documented, not fixed, per migration plan
   §2.5's "forward to the id-taking SDK method ... else document" rule; see
   ``commands/network/forwards.py::forwards_show``'s docstring.
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

    ``resolve_eero_identifier`` (``commands/eero/base.py``) now attempts a
    direct, id-validated ``client.get_eero(...)`` call, verbatim, whenever
    ``identifier.isdigit()`` OR ``looks_like_sdk_reference(identifier)``
    (``utils.py``) -- every string in the SDK's hostile-id corpus matches
    the latter (each contains one of ``/ ? # { }`` or is empty), so it is
    forwarded to the SDK's own ``_IDENTIFIER_RE`` check, which raises
    ``EeroValidationException`` before any request. ``EeroNotFoundException``
    is the only exception the resolver still swallows to fall through to the
    list+match branch -- every other exception, including
    ``EeroValidationException``, propagates to ``run_with_client`` and maps
    to exit 2.
    """

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

    ``device_show`` (``commands/device.py``) now checks
    ``looks_like_sdk_reference(device_identifier)`` before doing anything
    else: when it matches, the raw identifier is forwarded verbatim to
    ``client.get_device(...)`` instead of listing devices and matching
    locally via ``_find_device``. Every hostile corpus string and every
    foreign-network/query/fragment child link matches, so each reaches the
    SDK's own validation (``_IDENTIFIER_RE`` / ``_require_nested_family``)
    before any request, and ``EeroValidationException`` propagates to exit
    2. Plain names/MACs (e.g. ``"iPhone"``, ``"aabbccddeeff"``) still don't
    match and keep going through the list+match resolver unchanged.
    """

    @pytest.mark.parametrize("hostile_id", HOSTILE_IDS)
    def test_rejects_hostile_id_before_any_request(
        self, runner, wired_client, guarded_transport, hostile_id
    ):
        result = runner.invoke(cli, ["-n", "111111", "device", "show", hostile_id])
        assert result.exit_code == ExitCode.USAGE_ERROR, result.output
        assert "invalid" in result.output.lower(), result.output
        guarded_transport.assert_not_awaited()

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

    Same fix shape as device show: ``profile_show`` (``commands/profile.py``)
    checks ``looks_like_sdk_reference(profile_identifier)`` first and, when
    it matches, forwards the raw identifier verbatim to
    ``client.get_profile(...)`` instead of listing profiles and matching
    locally via ``_find_profile``.
    """

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

    XFAIL, still: unlike eero/device/profile show, ``forwards_show`` has no
    id-validated SDK *read* to forward to -- the facade only exposes
    ``get_forwards`` (a list) plus ``update_forward``/``delete_forward``
    (writes; unsafe to call from a read command just to borrow their id
    validation). It always calls ``client.get_forwards(...)`` first
    (``commands/network/forwards.py``) and matches locally with an inline
    loop comparing ``str(fwd.get("id")) == forward_id`` -- a plain string
    comparison, never an SDK call. Documented, not fixed, per migration plan
    §2.5's "forward to the id-taking SDK method ... else document" rule.
    """

    @pytest.mark.xfail(
        reason=(
            "forwards_show (commands/network/forwards.py) always lists "
            "forwards first and matches forward_id locally with a plain "
            "string comparison; there is no singular id-validated SDK read "
            "for a port forward to forward the raw id to (only the list, "
            "plus update/delete -- writes), so a hostile id is reported "
            "'not found' (exit 5) rather than rejected as invalid (exit 2). "
            "Documented gap, not fixed -- see forwards_show's docstring."
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

    ``led_show`` resolves its argument through the very same
    ``resolve_eero_identifier`` as ``eero show`` (``commands/eero/led.py``),
    so it inherits that resolver's fix identically -- see
    ``TestEeroShowRejectsHostileIds``.
    """

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
# `device show` demonstrates the transport guard is a real trap (not a
# fixture that silently no-ops) for every identifier shape -- bare id,
# host-relative path, or full URL alike. As of the fix, `device_show`
# forwards a path/URL identifier straight to `get_device` (Section 4 below
# pins that with a mocked client method assertion); this section only
# asserts that *some* request reaches the transport and the command
# reports NOT_FOUND for an empty response, independent of which endpoint
# was hit.
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


# =====================================================================
# Section 4 -- id-scoped method receives the raw string verbatim, and a
# plain name still resolves via the list
#
# Uses a mocked ``EeroClient`` (patched at ``eeroctl.utils.build_client``,
# the CLI's single construction site) rather than the real SDK: these
# assert *what eeroctl calls* for a given input shape, not what the SDK
# does with it -- SDK acceptance/rejection is already pinned against the
# real client in Section 1.
# =====================================================================


def _mock_client(**method_returns: Any) -> AsyncMock:
    client = AsyncMock()
    for name, value in method_returns.items():
        setattr(client, name, AsyncMock(return_value=value))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestPathFormsForwardVerbatimToIdScopedMethod:
    """A `/2.2/<resource>/<id>`-shaped input is awaited by the id-scoped SDK
    method with the exact string the caller typed -- never trimmed, never
    normalised, and the list endpoint is never called."""

    def test_eero_show_forwards_path_to_get_eero(self, runner, monkeypatch):
        path = "/2.2/eeros/123"
        mock_client = _mock_client(
            get_eero={"meta": {"code": 200}, "data": {"id": "123", "url": path}},
        )
        monkeypatch.setattr("eeroctl.utils.build_client", lambda *a, **k: mock_client)

        result = runner.invoke(cli, ["-n", "111111", "eero", "show", path])

        mock_client.get_eero.assert_awaited_once_with(path, "111111")
        mock_client.get_eeros.assert_not_called()
        assert result.exit_code == ExitCode.SUCCESS, result.output

    def test_device_show_forwards_path_to_get_device(self, runner, monkeypatch):
        path = "/2.2/networks/111111/devices/aabbccddeeff"
        mock_client = _mock_client(
            get_device={"meta": {"code": 200}, "data": {"id": "aabbccddeeff", "url": path}},
        )
        monkeypatch.setattr("eeroctl.utils.build_client", lambda *a, **k: mock_client)

        result = runner.invoke(cli, ["-n", "111111", "device", "show", path])

        mock_client.get_device.assert_awaited_once_with(path, "111111")
        mock_client.get_devices.assert_not_called()
        assert result.exit_code == ExitCode.SUCCESS, result.output

    def test_profile_show_forwards_path_to_get_profile(self, runner, monkeypatch):
        path = "/2.2/networks/111111/profiles/p1"
        mock_client = _mock_client(
            get_profile={
                "meta": {"code": 200},
                "data": {"id": "p1", "url": path, "name": "Kids"},
            },
        )
        monkeypatch.setattr("eeroctl.utils.build_client", lambda *a, **k: mock_client)

        result = runner.invoke(cli, ["-n", "111111", "profile", "show", path])

        mock_client.get_profile.assert_awaited_once_with(path, "111111")
        mock_client.get_profiles.assert_not_called()
        assert result.exit_code == ExitCode.SUCCESS, result.output

    def test_led_show_forwards_path_to_get_eero(self, runner, monkeypatch):
        path = "/2.2/eeros/123"
        mock_client = _mock_client(
            get_eero={"meta": {"code": 200}, "data": {"id": "123", "url": path}},
            get_led_status={"meta": {"code": 200}, "data": {"led_on": True}},
        )
        monkeypatch.setattr("eeroctl.utils.build_client", lambda *a, **k: mock_client)

        result = runner.invoke(cli, ["-n", "111111", "eero", "led", "show", path])

        mock_client.get_eero.assert_awaited_once_with(path, "111111")
        mock_client.get_eeros.assert_not_called()
        assert result.exit_code == ExitCode.SUCCESS, result.output


class TestPlainNamesStillResolveViaTheList:
    """Plain names/serials/MACs are unaffected by the fix: they still go
    through the existing list-and-match resolvers, never straight to the
    id-scoped method."""

    def test_eero_show_resolves_name_via_list(self, runner, monkeypatch):
        mock_client = _mock_client(
            get_eeros={
                "meta": {"code": 200},
                "data": [{"id": "123", "url": "/2.2/eeros/123", "name": "Living Room"}],
            },
        )
        monkeypatch.setattr("eeroctl.utils.build_client", lambda *a, **k: mock_client)

        result = runner.invoke(cli, ["-n", "111111", "eero", "show", "Living Room"])

        mock_client.get_eeros.assert_awaited_once()
        mock_client.get_eero.assert_not_called()
        assert result.exit_code == ExitCode.SUCCESS, result.output

    def test_device_show_resolves_name_via_list(self, runner, monkeypatch):
        mock_client = _mock_client(
            get_devices={
                "meta": {"code": 200},
                "data": [
                    {
                        "url": "/2.2/networks/111111/devices/aabbccddeeff",
                        "nickname": "iPhone",
                    }
                ],
            },
            get_device={
                "meta": {"code": 200},
                "data": {"id": "aabbccddeeff", "nickname": "iPhone"},
            },
        )
        monkeypatch.setattr("eeroctl.utils.build_client", lambda *a, **k: mock_client)

        result = runner.invoke(cli, ["-n", "111111", "device", "show", "iPhone"])

        mock_client.get_devices.assert_awaited_once()
        assert result.exit_code == ExitCode.SUCCESS, result.output

    def test_profile_show_resolves_name_via_list(self, runner, monkeypatch):
        mock_client = _mock_client(
            get_profiles={
                "meta": {"code": 200},
                "data": [{"url": "/2.2/networks/111111/profiles/p1", "name": "Kids"}],
            },
            get_profile={"meta": {"code": 200}, "data": {"id": "p1", "name": "Kids"}},
        )
        monkeypatch.setattr("eeroctl.utils.build_client", lambda *a, **k: mock_client)

        result = runner.invoke(cli, ["-n", "111111", "profile", "show", "Kids"])

        mock_client.get_profiles.assert_awaited_once()
        assert result.exit_code == ExitCode.SUCCESS, result.output
