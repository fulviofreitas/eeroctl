"""Pytest configuration and fixtures for eeroctl tests."""

import inspect
import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Type

import pytest
from click.testing import CliRunner
from eero.exceptions import EeroException


@pytest.fixture
def cli_runner() -> CliRunner:
    """Provide a Click CLI test runner."""
    return CliRunner()


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
