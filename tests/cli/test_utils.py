"""Unit tests for eero.cli.utils module.

Tests cover:
- Configuration directory and file path functions
- Preferred network get/set functions
- with_client decorator
- run_with_client helper
"""

import json
import logging
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from eero.exceptions import (
    EeroAPIException,
    EeroAuthenticationException,
    EeroException,
    EeroNotFoundException,
    EeroPremiumRequiredException,
    EeroValidationException,
)

from eeroctl.context import EeroCliContext
from eeroctl.exit_codes import ExitCode
from eeroctl.utils import (
    DEFAULT_CONFIG,
    backup_legacy_cookie_file,
    build_client,
    confirm_action,
    ensure_config,
    get_auth_method,
    get_config_dir,
    get_config_file,
    get_cookie_file,
    get_default_output,
    get_preferred_network,
    get_session_token_override,
    looks_like_sdk_reference,
    prepare_client,
    run_with_client,
    set_auth_method,
    set_default_output,
    set_preferred_network,
    with_client,
    write_if_changed,
)

# ========================== Config Directory Tests ==========================


class TestGetConfigDir:
    """Tests for get_config_dir function."""

    def test_returns_path_object(self, tmp_path, monkeypatch):
        """Test function returns a Path object."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        result = get_config_dir()

        assert isinstance(result, Path)

    def test_creates_directory_if_not_exists(self, tmp_path, monkeypatch):
        """Test function creates the config directory."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config_dir = get_config_dir()

        assert config_dir.exists()
        assert config_dir.is_dir()

    def test_creates_directory_with_mode_0700(self, tmp_path, monkeypatch):
        """A newly created config dir is 0700: it holds cookies.json (a bearer token)."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config_dir = get_config_dir()

        assert (config_dir.stat().st_mode & 0o777) == 0o700

    def test_tightens_mode_of_a_pre_existing_directory(self, tmp_path, monkeypatch):
        """A pre-existing, more permissive directory is chmod'd to 0700."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        pre_existing = tmp_path / ".config" / "eeroctl"
        pre_existing.mkdir(parents=True)
        os.chmod(pre_existing, 0o755)

        config_dir = get_config_dir()

        assert (config_dir.stat().st_mode & 0o777) == 0o700

    @patch("os.name", "posix")
    def test_posix_path(self, tmp_path, monkeypatch):
        """Test config dir path on POSIX systems."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config_dir = get_config_dir()

        expected = tmp_path / ".config" / "eeroctl"
        assert config_dir == expected

    def test_windows_path(self, tmp_path, monkeypatch):
        """Test config dir path on Windows (skipped on non-Windows)."""

        if os.name != "nt":
            pytest.skip("Windows-only test")

        monkeypatch.setenv("APPDATA", str(tmp_path))

        config_dir = get_config_dir()

        expected = tmp_path / "eeroctl"
        assert config_dir == expected

    def test_eerctl_config_dir_env_var_overrides_default(self, tmp_path, monkeypatch):
        """EEROCTL_CONFIG_DIR overrides both the POSIX and Windows defaults."""
        override = tmp_path / "custom-config-dir"
        monkeypatch.setenv("EEROCTL_CONFIG_DIR", str(override))

        config_dir = get_config_dir()

        assert config_dir == override
        assert config_dir.exists()

    def test_eeroctl_config_dir_expands_user(self, tmp_path, monkeypatch):
        """EEROCTL_CONFIG_DIR supports a leading ~."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("EEROCTL_CONFIG_DIR", "~/custom-eeroctl")

        config_dir = get_config_dir()

        assert config_dir == tmp_path / "custom-eeroctl"


# ========================== Config File Tests ==========================


class TestGetCookieFile:
    """Tests for get_cookie_file function."""

    def test_returns_path_in_config_dir(self, tmp_path, monkeypatch):
        """Test cookie file is in config directory."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        cookie_file = get_cookie_file()

        assert cookie_file.parent == get_config_dir()
        assert cookie_file.name == "cookies.json"


class TestGetConfigFile:
    """Tests for get_config_file function."""

    def test_returns_path_in_config_dir(self, tmp_path, monkeypatch):
        """Test config file is in config directory."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config_file = get_config_file()

        assert config_file.parent == get_config_dir()
        assert config_file.name == "config.json"


# ========================== Preferred Network Tests ==========================


class TestSetPreferredNetwork:
    """Tests for set_preferred_network function."""

    def test_creates_config_file_if_not_exists(self, tmp_path, monkeypatch):
        """Test creates config file when it doesn't exist."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config_file = get_config_file()

        set_preferred_network("net_12345")

        assert config_file.exists()
        with open(config_file) as f:
            data = json.load(f)
        assert data["preferred_network_id"] == "net_12345"

    def test_updates_existing_config(self, tmp_path, monkeypatch):
        """Test updates existing config file."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config_file = get_config_file()

        # Create initial config
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps({"other_setting": "value"}))

        set_preferred_network("net_67890")

        with open(config_file) as f:
            data = json.load(f)
        assert data["preferred_network_id"] == "net_67890"
        assert data["other_setting"] == "value"  # Preserved

    def test_overwrites_existing_network_id(self, tmp_path, monkeypatch):
        """Test overwrites existing network ID."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config_file = get_config_file()

        # Create initial config with network ID
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps({"preferred_network_id": "old_net"}))

        set_preferred_network("new_net")

        with open(config_file) as f:
            data = json.load(f)
        assert data["preferred_network_id"] == "new_net"


class TestGetPreferredNetwork:
    """Tests for get_preferred_network function."""

    def test_returns_none_when_no_config(self, tmp_path, monkeypatch):
        """Test returns None when config file doesn't exist."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        result = get_preferred_network()

        assert result is None

    def test_returns_none_when_not_set(self, tmp_path, monkeypatch):
        """Test returns None when network ID not in config."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config_file = get_config_file()
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps({"other": "value"}))

        result = get_preferred_network()

        assert result is None

    def test_returns_network_id_when_set(self, tmp_path, monkeypatch):
        """Test returns network ID when set."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config_file = get_config_file()
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps({"preferred_network_id": "net_abc"}))

        result = get_preferred_network()

        assert result == "net_abc"

    def test_handles_invalid_json(self, tmp_path, monkeypatch):
        """Test handles corrupted JSON gracefully."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config_file = get_config_file()
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text("not valid json")

        result = get_preferred_network()

        assert result is None


# ========================== build_client Tests ==========================


class TestBuildClient:
    """Tests for build_client, the single EeroClient construction site."""

    def test_passes_cookie_file_and_use_keyring_through(self, tmp_path, monkeypatch):
        """build_client forwards get_cookie_file()/get_use_keyring() to EeroClient."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with patch("eeroctl.utils.EeroClient") as mock_client_class:
            build_client()

        mock_client_class.assert_called_once_with(
            cookie_file=str(get_cookie_file()),
            use_keyring=get_auth_method() == "keyring",
            accept_language="en-US",
            get_retries=0,
            send_legacy_cookie=True,
        )

    def test_reflects_saved_cookie_file_auth_method(self, tmp_path, monkeypatch):
        """A saved cookie_file preference is reflected in the construction call."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        set_auth_method("cookie_file")

        with patch("eeroctl.utils.EeroClient") as mock_client_class:
            build_client()

        assert mock_client_class.call_args.kwargs["use_keyring"] is False

    def test_cli_ctx_constructor_options_are_forwarded(self, tmp_path, monkeypatch):
        """accept_language/get_retries/send_legacy_cookie come from cli_ctx when given."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        ctx = EeroCliContext(
            accept_language="fr-FR",
            get_retries=3,
            send_legacy_cookie=False,
        )

        with patch("eeroctl.utils.EeroClient") as mock_client_class:
            build_client(cli_ctx=ctx)

        mock_client_class.assert_called_once_with(
            cookie_file=str(get_cookie_file()),
            use_keyring=get_auth_method() == "keyring",
            accept_language="fr-FR",
            get_retries=3,
            send_legacy_cookie=False,
        )

    def test_without_cli_ctx_falls_back_to_config(self, tmp_path, monkeypatch):
        """With no cli_ctx (and no Click context), constructor options come from config."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setattr("eeroctl.utils.click.get_current_context", lambda silent=True: None)

        with patch("eeroctl.utils.EeroClient") as mock_client_class:
            build_client()

        assert mock_client_class.call_args.kwargs["accept_language"] == "en-US"
        assert mock_client_class.call_args.kwargs["get_retries"] == 0
        assert mock_client_class.call_args.kwargs["send_legacy_cookie"] is True

    def test_resolves_cli_ctx_from_current_click_context_when_omitted(self, tmp_path, monkeypatch):
        """When cli_ctx is omitted, build_client picks it up via click.get_current_context."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        ctx = EeroCliContext(accept_language="de-DE", get_retries=2, send_legacy_cookie=False)
        fake_click_ctx = type("FakeClickCtx", (), {"obj": ctx})()
        monkeypatch.setattr(
            "eeroctl.utils.click.get_current_context", lambda silent=True: fake_click_ctx
        )

        with patch("eeroctl.utils.EeroClient") as mock_client_class:
            build_client()

        assert mock_client_class.call_args.kwargs["accept_language"] == "de-DE"
        assert mock_client_class.call_args.kwargs["get_retries"] == 2
        assert mock_client_class.call_args.kwargs["send_legacy_cookie"] is False

    def test_returns_the_constructed_client(self, tmp_path, monkeypatch):
        """build_client returns whatever EeroClient(...) produced, un-entered."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        sentinel = object()

        with patch("eeroctl.utils.EeroClient", return_value=sentinel):
            result = build_client()

        assert result is sentinel

    def test_use_keyring_override_wins_over_saved_preference(self, tmp_path, monkeypatch):
        """An explicit use_keyring= override beats get_use_keyring()."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        set_auth_method("keyring")  # get_use_keyring() would be True

        with patch("eeroctl.utils.EeroClient") as mock_client_class:
            build_client(use_keyring=False)

        assert mock_client_class.call_args.kwargs["use_keyring"] is False

    def test_cookie_file_override_wins_over_configured_path(self, tmp_path, monkeypatch):
        """An explicit cookie_file= override beats get_cookie_file()."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        override = tmp_path / "other-cookies.json"

        with patch("eeroctl.utils.EeroClient") as mock_client_class:
            build_client(cookie_file=override)

        assert mock_client_class.call_args.kwargs["cookie_file"] == str(override)

    def test_backs_up_the_cookie_file_before_constructing_the_client(self, tmp_path, monkeypatch):
        """backup_legacy_cookie_file runs before EeroClient(...) is called."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        call_order = []

        def fake_backup(cookie_file):
            call_order.append("backup")
            return None

        def fake_client(**kwargs):
            call_order.append("construct")

        with (
            patch(
                "eeroctl.utils.backup_legacy_cookie_file", side_effect=fake_backup
            ) as mock_backup,
            patch("eeroctl.utils.EeroClient", side_effect=fake_client),
        ):
            build_client()

        assert call_order == ["backup", "construct"]
        mock_backup.assert_called_once_with(get_cookie_file())

    def test_skips_backup_when_resolved_cookie_file_is_none(self, monkeypatch):
        """A None-resolving cookie file (e.g. EEROCTL_SESSION_TOKEN mode) skips the backup.

        Simulated here by making ``get_cookie_file()`` itself return None;
        the dedicated EEROCTL_SESSION_TOKEN tests below exercise the real
        public-API path that reaches the same branch.
        """
        monkeypatch.setattr("eeroctl.utils.get_cookie_file", lambda: None)

        with (
            patch("eeroctl.utils.backup_legacy_cookie_file") as mock_backup,
            patch("eeroctl.utils.EeroClient") as mock_client_class,
        ):
            build_client(use_keyring=True)

        mock_backup.assert_not_called()
        mock_client_class.assert_called_once_with(
            cookie_file=None,
            use_keyring=True,
            accept_language="en-US",
            get_retries=0,
            send_legacy_cookie=True,
        )

    def test_session_token_env_forces_ephemeral_construction(self, tmp_path, monkeypatch):
        """EEROCTL_SESSION_TOKEN forces cookie_file=None, use_keyring=False.

        This overrides any use_keyring=/cookie_file= the caller passed, and
        the pre-v8 backup never runs since no file is touched.
        """
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setenv("EEROCTL_SESSION_TOKEN", "a-token")
        # A real, existing schema-1 file that would otherwise get backed up.
        get_cookie_file().write_text(json.dumps({"session_id": "tok"}))

        with (
            patch("eeroctl.utils.backup_legacy_cookie_file") as mock_backup,
            patch("eeroctl.utils.EeroClient") as mock_client_class,
        ):
            build_client(use_keyring=True, cookie_file=tmp_path / "explicit.json")

        mock_backup.assert_not_called()
        mock_client_class.assert_called_once_with(
            cookie_file=None,
            use_keyring=False,
            accept_language="en-US",
            get_retries=0,
            send_legacy_cookie=True,
        )


# ========================== backup_legacy_cookie_file Tests ==========================


class TestBackupLegacyCookieFile:
    """Tests for backup_legacy_cookie_file (v8 migration plan §8.2)."""

    def test_schema1_file_is_backed_up_with_identical_content_and_mode_0600(self, tmp_path):
        cookie_file = tmp_path / "cookies.json"
        content = json.dumps(
            {
                "session_id": "tok",
                "refresh_token": "refresh-tok",
                "session_expiry": "2099-12-31T23:59:59",
            }
        )
        cookie_file.write_text(content)

        result = backup_legacy_cookie_file(cookie_file)

        backup_path = tmp_path / "cookies.json.pre-v8.bak"
        assert result == backup_path
        assert backup_path.exists()
        assert backup_path.read_text() == content
        assert (backup_path.stat().st_mode & 0o777) == 0o600

    def test_schema2_file_is_not_backed_up(self, tmp_path):
        cookie_file = tmp_path / "cookies.json"
        cookie_file.write_text(json.dumps({"session_id": "tok", "schema_version": 2}))

        result = backup_legacy_cookie_file(cookie_file)

        assert result is None
        assert not (tmp_path / "cookies.json.pre-v8.bak").exists()

    def test_missing_file_is_a_noop(self, tmp_path):
        cookie_file = tmp_path / "cookies.json"

        result = backup_legacy_cookie_file(cookie_file)

        assert result is None
        assert not (tmp_path / "cookies.json.pre-v8.bak").exists()

    def test_idempotent_on_second_run(self, tmp_path):
        """A second call never overwrites the existing backup."""
        cookie_file = tmp_path / "cookies.json"
        cookie_file.write_text(json.dumps({"session_id": "tok"}))

        first = backup_legacy_cookie_file(cookie_file)
        backup_path = tmp_path / "cookies.json.pre-v8.bak"
        original_backup_content = backup_path.read_text()
        original_mtime_ns = backup_path.stat().st_mtime_ns

        # The live file changing (as the SDK's migration would do) must not
        # cause the second call to touch the existing backup.
        cookie_file.write_text(json.dumps({"session_id": "tok-rewritten"}))
        second = backup_legacy_cookie_file(cookie_file)

        assert first == backup_path
        assert second is None
        assert backup_path.read_text() == original_backup_content
        assert backup_path.stat().st_mtime_ns == original_mtime_ns

    def test_ignores_sdk_temp_file_siblings(self, tmp_path):
        """A `.cookies.json.<random>.tmp` sibling is never touched or matched."""
        cookie_file = tmp_path / "cookies.json"
        cookie_file.write_text(json.dumps({"session_id": "tok"}))
        tmp_sibling = tmp_path / ".cookies.json.abc123.tmp"
        tmp_sibling.write_text("must never be read or overwritten")

        result = backup_legacy_cookie_file(cookie_file)

        assert result == tmp_path / "cookies.json.pre-v8.bak"
        assert tmp_sibling.read_text() == "must never be read or overwritten"

    def test_invalid_json_is_a_noop(self, tmp_path):
        cookie_file = tmp_path / "cookies.json"
        cookie_file.write_text("{not valid json")

        result = backup_legacy_cookie_file(cookie_file)

        assert result is None
        assert not (tmp_path / "cookies.json.pre-v8.bak").exists()

    def test_non_object_json_is_a_noop(self, tmp_path):
        cookie_file = tmp_path / "cookies.json"
        cookie_file.write_text(json.dumps(["not", "an", "object"]))

        result = backup_legacy_cookie_file(cookie_file)

        assert result is None

    def test_directory_at_path_is_a_noop(self, tmp_path):
        cookie_file = tmp_path / "cookies.json"
        cookie_file.mkdir()

        result = backup_legacy_cookie_file(cookie_file)

        assert result is None

    def test_logs_the_path_only_never_the_token(self, tmp_path, caplog):
        cookie_file = tmp_path / "cookies.json"
        cookie_file.write_text(json.dumps({"session_id": "super-secret-token"}))

        with caplog.at_level(logging.INFO, logger="eeroctl"):
            backup_legacy_cookie_file(cookie_file)

        assert "super-secret-token" not in caplog.text
        assert str(tmp_path / "cookies.json.pre-v8.bak") in caplog.text

    def test_partial_write_failure_leaves_no_backup_file(self, tmp_path, monkeypatch):
        """A write failure mid-backup must not leave a truncated file behind."""
        cookie_file = tmp_path / "cookies.json"
        cookie_file.write_text(json.dumps({"session_id": "tok"}))

        import eeroctl.utils as utils_module

        real_fdopen = utils_module.os.fdopen

        class _FailingWriter:
            def __init__(self, real_file):
                self._real_file = real_file

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                self._real_file.close()
                return False

            def write(self, data):
                raise OSError("simulated disk full")

        def failing_fdopen(fd, mode="r", *args, **kwargs):
            return _FailingWriter(real_fdopen(fd, mode, *args, **kwargs))

        monkeypatch.setattr(utils_module.os, "fdopen", failing_fdopen)

        result = backup_legacy_cookie_file(cookie_file)

        assert result is None
        assert not (tmp_path / "cookies.json.pre-v8.bak").exists()


# ========================== with_client Decorator Tests ==========================


class TestWithClientDecorator:
    """Tests for with_client decorator."""

    def test_decorator_preserves_function_name(self):
        """Test decorator preserves function name and docstring."""

        @with_client
        async def my_special_function(client):
            """My docstring."""
            pass

        assert my_special_function.__name__ == "my_special_function"

    def test_decorator_returns_sync_wrapper(self):
        """Test decorator returns a synchronous wrapper function."""

        @with_client
        async def async_func(client):
            return "result"

        # The wrapper should be a regular function (not async)
        import asyncio

        assert not asyncio.iscoroutinefunction(async_func)

    def test_preserves_function_metadata(self):
        """Test decorator preserves function name and docstring."""

        @with_client
        async def documented_function(client):
            """This is documentation."""
            pass

        assert documented_function.__name__ == "documented_function"
        # Note: functools.wraps should preserve __doc__

    def test_passes_through_arguments(self, tmp_path, monkeypatch):
        """Test decorator passes through additional arguments."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        received_args = []

        @with_client
        async def my_command(arg1, arg2, client, kwarg1=None):
            received_args.extend([arg1, arg2, kwarg1])
            return "done"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            my_command("a", "b", kwarg1="c")

        assert received_args == ["a", "b", "c"]

    def test_goes_through_build_client(self, tmp_path, monkeypatch):
        """with_client constructs its client via build_client, not EeroClient directly."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        @with_client
        async def my_command(client):
            return "done"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("eeroctl.utils.build_client", return_value=mock_client) as mock_build:
            my_command()

        mock_build.assert_called_once_with()

    def test_calls_prepare_client_after_entering(self, tmp_path, monkeypatch):
        """prepare_client runs after __aenter__, before the wrapped function."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        call_order = []

        @with_client
        async def my_command(client):
            call_order.append("command")
            return "done"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        async def fake_prepare(client):
            call_order.append("prepare")

        with (
            patch("eeroctl.utils.build_client", return_value=mock_client),
            patch("eeroctl.utils.prepare_client", side_effect=fake_prepare) as mock_prepare,
        ):
            my_command()

        mock_prepare.assert_called_once_with(mock_client)
        assert call_order == ["prepare", "command"]

    def test_validation_exception_from_prepare_client_exits_2(self, tmp_path, monkeypatch):
        """A malformed EEROCTL_SESSION_TOKEN (via prepare_client) exits 2."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        @with_client
        async def my_command(client):
            return "done"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("eeroctl.utils.build_client", return_value=mock_client),
            patch(
                "eeroctl.utils.prepare_client",
                side_effect=EeroValidationException("token", "must be printable ASCII"),
            ),
            pytest.raises(SystemExit) as excinfo,
        ):
            my_command()

        assert excinfo.value.code == ExitCode.USAGE_ERROR


# ========================== run_with_client Tests ==========================


class TestRunWithClient:
    """Tests for run_with_client helper function."""

    @pytest.mark.asyncio
    async def test_executes_function_with_client(self, tmp_path, monkeypatch):
        """Test helper executes function with client."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        executed = []

        async def my_func(client):
            executed.append(client)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            await run_with_client(my_func)

        assert len(executed) == 1

    def test_run_with_client_is_async(self):
        """Test run_with_client is an async function."""
        import asyncio

        assert asyncio.iscoroutinefunction(run_with_client)

    @pytest.mark.asyncio
    async def test_goes_through_build_client(self, tmp_path, monkeypatch):
        """run_with_client constructs its client via build_client, not EeroClient directly."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        async def my_func(client):
            pass

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("eeroctl.utils.build_client", return_value=mock_client) as mock_build:
            await run_with_client(my_func)

        mock_build.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_calls_prepare_client_after_entering(self, tmp_path, monkeypatch):
        """prepare_client runs after __aenter__, before func."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        call_order = []

        async def my_func(client):
            call_order.append("func")

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        async def fake_prepare(client):
            call_order.append("prepare")

        with (
            patch("eeroctl.utils.build_client", return_value=mock_client),
            patch("eeroctl.utils.prepare_client", side_effect=fake_prepare) as mock_prepare,
        ):
            await run_with_client(my_func)

        mock_prepare.assert_called_once_with(mock_client)
        assert call_order == ["prepare", "func"]

    @pytest.mark.asyncio
    async def test_forwards_cli_ctx_to_build_client(self, tmp_path, monkeypatch):
        """A cli_ctx passed to run_with_client is forwarded to build_client."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        async def my_func(client):
            pass

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        sentinel_ctx = object()

        with patch("eeroctl.utils.build_client", return_value=mock_client) as mock_build:
            await run_with_client(my_func, cli_ctx=sentinel_ctx)

        mock_build.assert_called_once_with(sentinel_ctx)


class TestRunWithClientErrorMapping:
    """Tests that SDK exceptions escaping a command map to exit codes.

    ``run_with_client`` is the single boundary every command routes through, so
    this mapping applies repo-wide, not just to DNS.
    """

    @staticmethod
    def _client():
        """Build a mock EeroClient usable as an async context manager."""
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        # Must return falsy: a truthy __aexit__ suppresses the exception under test.
        client.__aexit__ = AsyncMock(return_value=False)
        return client

    async def _run_raising(self, tmp_path, monkeypatch, exc):
        """Run ``run_with_client`` with a coroutine that raises *exc*."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        async def my_func(client):
            raise exc

        with patch("eeroctl.utils.EeroClient", return_value=self._client()):
            with pytest.raises(SystemExit) as excinfo:
                await run_with_client(my_func)
        return excinfo.value.code

    @pytest.mark.asyncio
    async def test_validation_exception_maps_to_usage_error(self, tmp_path, monkeypatch):
        """EeroValidationException exits 2, not an unhandled traceback."""
        exc = EeroValidationException("dns_servers", "at most 2 IPv4 servers are supported")

        code = await self._run_raising(tmp_path, monkeypatch, exc)

        assert code == ExitCode.USAGE_ERROR

    @pytest.mark.asyncio
    async def test_api_403_maps_to_forbidden(self, tmp_path, monkeypatch):
        """A 403 from the API exits 4."""
        code = await self._run_raising(tmp_path, monkeypatch, EeroAPIException(403, "nope"))

        assert code == ExitCode.FORBIDDEN

    @pytest.mark.asyncio
    async def test_not_found_maps_to_not_found(self, tmp_path, monkeypatch):
        """A not-found exits 5."""
        exc = EeroNotFoundException("Network", "NID")

        code = await self._run_raising(tmp_path, monkeypatch, exc)

        assert code == ExitCode.NOT_FOUND

    @pytest.mark.asyncio
    async def test_premium_required_maps_to_premium(self, tmp_path, monkeypatch):
        """A premium-required exits 11."""
        exc = EeroPremiumRequiredException("Activity data")

        code = await self._run_raising(tmp_path, monkeypatch, exc)

        assert code == ExitCode.PREMIUM_REQUIRED

    @pytest.mark.asyncio
    async def test_generic_eero_exception_maps_to_generic_error(self, tmp_path, monkeypatch):
        """A bare EeroException exits 1."""
        code = await self._run_raising(tmp_path, monkeypatch, EeroException("boom"))

        assert code == ExitCode.GENERIC_ERROR

    @pytest.mark.asyncio
    async def test_auth_exception_keeps_its_bespoke_message(self, tmp_path, monkeypatch):
        """Authentication exits AUTH_REQUIRED (3), matching with_client,
        handle_cli_error and auth login -- not the pre-v8 bare 1.

        Guards against the new handler swallowing the more specific one.
        """
        exc = EeroAuthenticationException("expired")

        code = await self._run_raising(tmp_path, monkeypatch, exc)

        assert code == ExitCode.AUTH_REQUIRED
        assert code == 3

    @pytest.mark.asyncio
    async def test_sys_exit_from_command_still_propagates(self, tmp_path, monkeypatch):
        """sys.exit() inside the coroutine must not be swallowed.

        This is why the handler catches EeroException rather than Exception:
        SystemExit derives from BaseException, and a bare catch would turn every
        deliberate exit code into a generic error.
        """
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        async def my_func(client):
            raise SystemExit(ExitCode.SAFETY_RAIL)

        with patch("eeroctl.utils.EeroClient", return_value=self._client()):
            with pytest.raises(SystemExit) as excinfo:
                await run_with_client(my_func)

        assert excinfo.value.code == ExitCode.SAFETY_RAIL

    @pytest.mark.asyncio
    async def test_non_sdk_exception_is_not_swallowed(self, tmp_path, monkeypatch):
        """A genuine bug surfaces as itself, not as a tidy CLI error."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        async def my_func(client):
            raise KeyError("a real bug")

        with patch("eeroctl.utils.EeroClient", return_value=self._client()):
            with pytest.raises(KeyError):
                await run_with_client(my_func)


# ========================== confirm_action Tests ==========================


class TestConfirmAction:
    """Tests for confirm_action helper function."""

    def test_returns_true_on_confirm(self, monkeypatch):
        """Test returns True when user confirms."""
        import click

        monkeypatch.setattr(click, "confirm", lambda msg: True)

        result = confirm_action("Do this?")

        assert result is True

    def test_returns_false_on_decline(self, monkeypatch):
        """Test returns False when user declines."""
        import click

        monkeypatch.setattr(click, "confirm", lambda msg: False)

        result = confirm_action("Do this?")

        assert result is False

    def test_passes_message_to_click(self, monkeypatch):
        """Test passes message to click.confirm."""
        import click

        received_messages = []

        def capture_confirm(msg):
            received_messages.append(msg)
            return True

        monkeypatch.setattr(click, "confirm", capture_confirm)

        confirm_action("Custom message")

        assert received_messages == ["Custom message"]


# ========================== Ensure Config Tests ==========================


class TestEnsureConfig:
    """Tests for ensure_config function."""

    def test_creates_config_with_defaults(self, tmp_path, monkeypatch):
        """Test creates config file with default values."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config = ensure_config()

        assert config == DEFAULT_CONFIG
        config_file = get_config_file()
        assert config_file.exists()

    def test_preserves_existing_values(self, tmp_path, monkeypatch):
        """Test preserves existing config values."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config_file = get_config_file()
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps({"preferred_network_id": "net_123"}))

        config = ensure_config()

        assert config["preferred_network_id"] == "net_123"
        assert config["default_output"] == "table"  # Added default
        assert config["auth_method"] == "keyring"  # Added default

    def test_adds_missing_keys(self, tmp_path, monkeypatch):
        """Test adds missing keys to existing config."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config_file = get_config_file()
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps({"custom_key": "value"}))

        ensure_config()

        # Custom key preserved
        with open(config_file) as f:
            saved = json.load(f)
        assert saved["custom_key"] == "value"
        assert saved["default_output"] == "table"


# ========================== Auth Method Tests ==========================


class TestAuthMethod:
    """Tests for auth_method get/set functions."""

    def test_get_default_auth_method(self, tmp_path, monkeypatch):
        """Test default auth method is keyring."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        result = get_auth_method()

        assert result == "keyring"

    def test_set_auth_method_keyring(self, tmp_path, monkeypatch):
        """Test setting auth method to keyring."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        set_auth_method("keyring")

        assert get_auth_method() == "keyring"

    def test_set_auth_method_cookie_file(self, tmp_path, monkeypatch):
        """Test setting auth method to cookie_file."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        set_auth_method("cookie_file")

        assert get_auth_method() == "cookie_file"

    def test_set_invalid_auth_method_raises(self, tmp_path, monkeypatch):
        """Test setting invalid auth method raises ValueError."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with pytest.raises(ValueError, match="Invalid auth method"):
            set_auth_method("invalid")


# ========================== Default Output Tests ==========================


class TestDefaultOutput:
    """Tests for default_output get/set functions."""

    def test_get_default_output(self, tmp_path, monkeypatch):
        """Test default output format is table."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        result = get_default_output()

        assert result == "table"

    def test_set_default_output_json(self, tmp_path, monkeypatch):
        """Test setting default output to json."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        set_default_output("json")

        assert get_default_output() == "json"

    def test_set_default_output_list(self, tmp_path, monkeypatch):
        """Test setting default output to list."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        set_default_output("list")

        assert get_default_output() == "list"

    def test_set_invalid_output_raises(self, tmp_path, monkeypatch):
        """Test setting invalid output format raises ValueError."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with pytest.raises(ValueError, match="Invalid output format"):
            set_default_output("invalid")


# ========================== write_if_changed Tests ==========================


class TestWriteIfChanged:
    """Tests for the write_if_changed helper (migration plan §3.2 item 4)."""

    @pytest.fixture
    def mock_console(self):
        """Create a mock console."""
        from unittest.mock import MagicMock

        console = MagicMock()
        console.print = MagicMock()
        return console

    @pytest.mark.asyncio
    async def test_skips_write_when_state_already_matches(self, mock_console):
        """Equal current/desired state: no write, returns False."""
        read = AsyncMock(return_value=True)
        write = AsyncMock(return_value={"meta": {"code": 200}})

        result = await write_if_changed(read, True, write, console=mock_console)

        assert result is False
        write.assert_not_awaited()
        printed = " ".join(str(c.args[0]) for c in mock_console.print.call_args_list)
        assert "already configured" in printed.lower()

    @pytest.mark.asyncio
    async def test_writes_once_when_state_differs(self, mock_console):
        """Different current/desired state: write is called exactly once."""
        read = AsyncMock(return_value=False)
        write = AsyncMock(return_value={"meta": {"code": 200}})

        result = await write_if_changed(read, True, write, console=mock_console)

        assert result is True
        write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_force_writes_even_when_unchanged(self, mock_console):
        """--force still writes, even though the state already matches."""
        read = AsyncMock(return_value=True)
        write = AsyncMock(return_value={"meta": {"code": 200}})

        result = await write_if_changed(read, True, write, force=True, console=mock_console)

        assert result is True
        write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_never_calls_write_more_than_once(self, mock_console):
        """A write is never retried, even implicitly -- called exactly once."""
        read = AsyncMock(return_value=False)
        write = AsyncMock(return_value={"meta": {"code": 200}})

        await write_if_changed(read, True, write, console=mock_console)

        assert write.await_count == 1

    @pytest.mark.asyncio
    async def test_2xx_response_is_accepted(self, mock_console):
        """A 201 (not just 200) is still treated as accepted."""
        read = AsyncMock(return_value=False)
        write = AsyncMock(return_value={"meta": {"code": 201}})

        result = await write_if_changed(read, True, write, console=mock_console)

        assert result is True

    @pytest.mark.asyncio
    async def test_none_result_is_accepted(self, mock_console):
        """A write returning None (no envelope) is treated as accepted."""
        read = AsyncMock(return_value=False)
        write = AsyncMock(return_value=None)

        result = await write_if_changed(read, True, write, console=mock_console)

        assert result is True

    @pytest.mark.asyncio
    async def test_non_2xx_response_exits_1_with_not_applied_message(self, mock_console):
        """A non-2xx meta.code exits 1 (GENERIC_ERROR) with a 'not applied' message."""
        read = AsyncMock(return_value=False)
        write = AsyncMock(return_value={"meta": {"code": 500}})

        with pytest.raises(SystemExit) as exc_info:
            await write_if_changed(read, True, write, console=mock_console)

        assert exc_info.value.code == ExitCode.GENERIC_ERROR
        printed = " ".join(str(c.args[0]) for c in mock_console.print.call_args_list)
        assert "not applied" in printed.lower()

    @pytest.mark.asyncio
    async def test_missing_meta_code_is_not_accepted(self, mock_console):
        """A dict response with no meta.code is not accepted (ambiguous shape)."""
        read = AsyncMock(return_value=False)
        write = AsyncMock(return_value={"meta": {}})

        with pytest.raises(SystemExit) as exc_info:
            await write_if_changed(read, True, write, console=mock_console)

        assert exc_info.value.code == ExitCode.GENERIC_ERROR

    @pytest.mark.asyncio
    async def test_custom_compare_predicate_is_used(self, mock_console):
        """A custom compare (e.g. set equality) overrides plain ==."""
        read = AsyncMock(return_value={"1.1.1.1", "8.8.8.8"})
        write = AsyncMock(return_value={"meta": {"code": 200}})

        result = await write_if_changed(
            read,
            {"8.8.8.8", "1.1.1.1"},
            write,
            compare=lambda current, desired: current == desired,
            console=mock_console,
        )

        assert result is False
        write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_read_command_appears_in_acceptance_message(self, mock_console):
        """The suggested verification command is included in the success message."""
        read = AsyncMock(return_value=False)
        write = AsyncMock(return_value={"meta": {"code": 200}})

        await write_if_changed(
            read, True, write, console=mock_console, read_command="eero network sqm show"
        )

        printed = " ".join(str(c.args[0]) for c in mock_console.print.call_args_list)
        assert "eero network sqm show" in printed


# ========================== looks_like_sdk_reference Tests ==========================


class TestLooksLikeSdkReference:
    """Tests for `looks_like_sdk_reference`.

    Pins the exact rule commands use to decide whether to forward an
    identifier verbatim to an id-validated SDK method, or resolve it
    locally via list-and-match (migration plan §2.5 decision 2/3).
    """

    @pytest.mark.parametrize(
        "value",
        [
            pytest.param("../../account", id="path-traversal"),
            pytest.param("a/b", id="multi-segment"),
        ],
    )
    def test_hostile_corpus_strings_containing_slash_look_like_references(self, value):
        """Of the SDK's hostile-id corpus, only the strings containing `/`
        must be forwarded -- so the SDK's own validation can reject them.
        `?`/`#`/`{`/`}` were dropped from the trigger set (Low finding
        follow-on): they are legal in real nicknames, so forwarding them
        would stop those names resolving by name at all.
        """
        assert looks_like_sdk_reference(value) is True

    @pytest.mark.parametrize(
        "value",
        [
            pytest.param("x?y=1", id="query-string"),
            pytest.param("{x}", id="format-template"),
            pytest.param("", id="empty-string"),
        ],
    )
    def test_hostile_corpus_strings_without_slash_no_longer_look_like_references(self, value):
        """These no longer trigger forwarding: they take the list-and-match
        path like any other non-matching name and are reported "not found"
        (exit 5) once nothing matches -- they never reach the id-scoped SDK
        method, so nothing hostile becomes reachable by not forwarding them.
        """
        assert looks_like_sdk_reference(value) is False

    @pytest.mark.parametrize(
        "value",
        [
            pytest.param("/2.2/eeros/123", id="host-relative-path"),
            pytest.param(
                "https://api-user.e2ro.com/2.2/networks/111111/devices/aabbccddeeff",
                id="absolute-url",
            ),
        ],
    )
    def test_path_and_url_forms_look_like_references(self, value):
        assert looks_like_sdk_reference(value) is True

    @pytest.mark.parametrize(
        "value",
        [
            pytest.param("Kids", id="plain-name"),
            pytest.param("Living Room", id="name-with-space-not-a-query-char"),
            pytest.param("aabbccddeeff", id="bare-mac"),
            pytest.param("SERIAL123", id="bare-serial"),
            pytest.param("123", id="bare-numeric-id"),
            pytest.param("Guest #2", id="nickname-with-hash"),
            pytest.param("Kid's room?", id="nickname-with-question-mark"),
            pytest.param("{Curly}", id="nickname-with-braces"),
        ],
    )
    def test_plain_names_serials_and_macs_do_not_look_like_references(self, value):
        """Names/serials/MACs must keep resolving via the existing
        list-and-match path -- this is the "names must keep working"
        requirement from the fix, extended by the Low finding follow-on to
        cover realistic nicknames containing `? # { }`.
        """
        assert looks_like_sdk_reference(value) is False

    def test_nickname_containing_slash_still_looks_like_a_reference(self):
        """`"Kid's iPad w/ case"` contains a literal `/` (in `"w/"`), so it
        still matches under the `contains "/"` rule and is forwarded --
        the slash check is the anti-path-traversal mechanism and was not
        weakened to accommodate this specific string. See
        `tests/cli/test_link_validation.py::TestNicknameContainingSlashStillForwards`.
        """
        assert looks_like_sdk_reference("Kid's iPad w/ case") is True


# ========================== get_session_token_override Tests ==========================


class TestGetSessionTokenOverride:
    """Tests for get_session_token_override (EEROCTL_SESSION_TOKEN, §3.4)."""

    def test_returns_none_when_unset(self, monkeypatch):
        monkeypatch.delenv("EEROCTL_SESSION_TOKEN", raising=False)

        assert get_session_token_override() is None

    def test_returns_none_when_empty(self, monkeypatch):
        monkeypatch.setenv("EEROCTL_SESSION_TOKEN", "")

        assert get_session_token_override() is None

    def test_returns_the_value_when_set(self, monkeypatch):
        monkeypatch.setenv("EEROCTL_SESSION_TOKEN", "a-real-token")

        assert get_session_token_override() == "a-real-token"


# ========================== prepare_client Tests ==========================


class TestPrepareClient:
    """Tests for prepare_client (EEROCTL_SESSION_TOKEN, §3.4)."""

    @pytest.mark.asyncio
    async def test_sets_the_session_token_when_env_var_present(self, monkeypatch):
        monkeypatch.setenv("EEROCTL_SESSION_TOKEN", "a-real-token")
        client = AsyncMock()

        await prepare_client(client)

        client.set_session_token.assert_awaited_once_with("a-real-token")

    @pytest.mark.asyncio
    async def test_does_nothing_when_env_var_absent(self, monkeypatch):
        monkeypatch.delenv("EEROCTL_SESSION_TOKEN", raising=False)
        client = AsyncMock()

        await prepare_client(client)

        client.set_session_token.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_propagates_validation_exception(self, monkeypatch):
        """A malformed token's EeroValidationException is not swallowed here."""
        monkeypatch.setenv("EEROCTL_SESSION_TOKEN", "bad\r\nvalue")
        client = AsyncMock()
        client.set_session_token = AsyncMock(
            side_effect=EeroValidationException("token", "must be printable ASCII")
        )

        with pytest.raises(EeroValidationException):
            await prepare_client(client)
