"""Pytest configuration and fixtures for eeroctl tests."""

import inspect
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Optional, Type
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner
from eero.exceptions import EeroException

#: The full `EEROCTL_*` environment-variable surface documented in the v8
#: migration plan §3.4 (Q6): one `auto_envvar_prefix="EEROCTL"` var per
#: global Click option, plus the two explicit ones (`EEROCTL_CONFIG_DIR`,
#: `EEROCTL_SESSION_TOKEN`). Only `EEROCTL_SESSION_TOKEN` is implemented
#: today (`utils.py:114`, referenced by the not-yet-landed
#: `utils.prepare_client`), but scrubbing the whole documented list now
#: means `mock_client`/`mock_client_raising` stay hermetic as the rest land
#: without this file needing another edit.
_EEROCTL_ENV_VARS = (
    "EEROCTL_OUTPUT",
    "EEROCTL_NETWORK_ID",
    "EEROCTL_FORCE",
    "EEROCTL_NON_INTERACTIVE",
    "EEROCTL_DEBUG",
    "EEROCTL_QUIET",
    "EEROCTL_NO_COLOR",
    "EEROCTL_ACCEPT_LANGUAGE",
    "EEROCTL_GET_RETRIES",
    "EEROCTL_NO_LEGACY_COOKIE",
    "EEROCTL_CONFIG_DIR",
    "EEROCTL_SESSION_TOKEN",
)


def _clean_eeroctl_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scrub every documented `EEROCTL_*` var so tests are hermetic."""
    for var in _EEROCTL_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def _new_mock_client() -> AsyncMock:
    """Build the base `AsyncMock` shape every command test needs.

    A working async context manager returning itself (`build_client`'s
    callers all do ``async with build_client(...) as client:``), and
    ``is_authenticated = True`` so auth-gated commands proceed straight to
    the mocked facade call instead of the `EeroAuthenticationException`
    path in `with_client`/`run_with_client`.
    """
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.is_authenticated = True
    return client


@pytest.fixture
def cli_runner() -> CliRunner:
    """Provide a Click CLI test runner."""
    return CliRunner()


@pytest.fixture(autouse=True)
def _reset_debug_logging_state():
    """Undo --debug's logger mutations between tests.

    ``main._configure_debug_logging`` (invoked on every ``cli()`` call,
    including via ``CliRunner``) sets ``propagate = False`` and attaches a
    handler to the ``eero``/``eeroctl`` loggers while ``--debug`` is active,
    to avoid double-printed log lines; it rebuilds that state fresh on
    every call, but a test that never invokes ``cli()`` at all still needs
    a clean baseline. Those are real, singleton ``logging.Logger`` objects
    shared across the whole pytest process, so without this reset, any
    test that runs after a ``--debug`` test would silently stop being
    visible to ``caplog``-based assertions (caplog captures via the root
    logger, which a non-propagating logger never reaches).
    """

    def _reset() -> None:
        for name in ("eero", "eeroctl"):
            target_logger = logging.getLogger(name)
            target_logger.handlers.clear()
            target_logger.propagate = True
            target_logger.setLevel(logging.NOTSET)

    _reset()
    yield
    _reset()


@pytest.fixture
def mock_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[AsyncMock]:
    """A shared `AsyncMock` `EeroClient`, wired in for the test's duration.

    Drop-in replacement for the hand-rolled::

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            ...

    pattern duplicated across ``tests/cli/commands/test_device.py`` and the
    phase-A command modules (``test_entitlements.py``, ``test_events.py``,
    ``test_permissions.py``, ``test_notifications.py``). Patches
    ``eeroctl.utils.EeroClient`` -- the single construction site
    ``build_client`` calls (``utils.py:129``) -- so every command under test
    gets this object back from ``async with build_client(...) as client:``
    without the test needing its own ``with patch(...)`` block. Configure
    per-method behaviour on the yielded mock before invoking the CLI, e.g.
    ``mock_client.get_devices = AsyncMock(return_value=DEVICES_RESPONSE)``.

    Also scrubs the documented `EEROCTL_*` environment surface (see
    ``_EEROCTL_ENV_VARS``) so a stray var in the outer environment can never
    leak into a test that uses this fixture -- required once
    ``utils.prepare_client`` starts reading ``EEROCTL_SESSION_TOKEN``.
    """
    _clean_eeroctl_env(monkeypatch)
    client = _new_mock_client()
    with patch("eeroctl.utils.EeroClient", return_value=client):
        yield client


@pytest.fixture
def mock_client_raising(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> Callable[[str, BaseException], AsyncMock]:
    """Factory version of :func:`mock_client` for exception-path tests.

    Drop-in replacement for the hand-rolled ``_mock_client_raising`` helper
    duplicated across the phase-A command test modules. Usage::

        def test_premium_required_maps_to_exit_11(self, runner, mock_client_raising):
            client = mock_client_raising(
                "get_entitlement_features", EeroPremiumRequiredException("x")
            )
            result = runner.invoke(cli, ["network", "entitlements", "show"])
            ...

    Each call builds a fresh :func:`_new_mock_client`, sets *method_name* to
    raise *exc*, and patches ``eeroctl.utils.EeroClient`` to return it for
    the rest of the test -- calling it again mid-test replaces the active
    patch with a new client/method, matching how the hand-rolled helper was
    always re-invoked per assertion rather than reused. The patch is torn
    down via ``request.addfinalizer`` regardless of how many times (zero or
    more) the factory was called, so an unused fixture request is a no-op.

    Scrubs the documented `EEROCTL_*` environment surface once, up front,
    same as :func:`mock_client`.
    """
    _clean_eeroctl_env(monkeypatch)

    def _build(method_name: str, exc: BaseException) -> AsyncMock:
        client = _new_mock_client()
        setattr(client, method_name, AsyncMock(side_effect=exc))
        patcher = patch("eeroctl.utils.EeroClient", return_value=client)
        patcher.start()
        request.addfinalizer(patcher.stop)
        return client

    return _build


@pytest.fixture
def schema2_cookie_file(tmp_path: Path) -> Path:
    """A cookie file in the current (eero-api 8, schema 2) credential shape.

    ``{"session_id": ..., "schema_version": 2}`` — the only fields schema 2
    ever writes (migration plan §2.1; DIGEST.md §3, const.py:86).
    """
    path = tmp_path / "cookies.json"
    path.write_text(json.dumps({"session_id": "tok", "schema_version": 2}))
    return path


@pytest.fixture
def schema1_cookie_file(tmp_path: Path) -> Path:
    """A cookie file in the legacy (pre-v8, schema 1) credential shape.

    Schema 1 had no ``schema_version`` key at all and carried
    ``refresh_token``/``session_expiry``, both dropped by schema 2.
    """
    path = tmp_path / "cookies.json"
    path.write_text(
        json.dumps(
            {
                "session_id": "tok",
                "refresh_token": "refresh-tok",
                "session_expiry": "2099-12-31T23:59:59",
            }
        )
    )
    return path


@pytest.fixture
def api_error() -> Callable[..., EeroException]:
    """Factory that builds a v8 SDK exception through its real constructor.

    Prefers the class's own ``from_response`` classmethod when one exists
    (the shape the transport uses when it has no client-side context — see
    eero-api ``exceptions.py``) and falls back to the class's direct
    ``__init__`` otherwise, so tests exercise the exact construction path
    eeroctl actually meets, rather than hand-rolled attribute assignment
    that could drift from the real SDK shape.

    Usage: ``api_error(cls, status_code, error_code, envelope=None)``.
    """

    def _build(
        cls: Type[EeroException],
        status_code: Optional[int],
        error_code: Optional[str],
        envelope: Optional[Dict[str, Any]] = None,
        message: str = "error",
    ) -> EeroException:
        from_response = getattr(cls, "from_response", None)
        if from_response is not None:
            params = inspect.signature(from_response).parameters
            kwargs: Dict[str, Any] = {"envelope": envelope, "error_code": error_code}
            if "status_code" in params:
                kwargs["status_code"] = status_code
            built: EeroException = from_response(message, **kwargs)
            return built

        init_params = inspect.signature(cls.__init__).parameters
        if "status_code" in init_params:
            return cls(status_code, message, envelope=envelope, error_code=error_code)
        return cls(message, envelope=envelope, error_code=error_code)

    return _build
