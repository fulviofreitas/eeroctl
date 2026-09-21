"""Pytest configuration and fixtures for eeroctl tests."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner


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
