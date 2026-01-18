"""Unit tests for eero.cli.utils module.

Tests cover:
- Configuration directory and file path functions
- Preferred network get/set functions
- with_client decorator
- run_with_client helper
"""

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from eeroctl.utils import (
    confirm_action,
    get_config_dir,
    get_config_file,
    get_cookie_file,
    get_preferred_network,
    run_with_client,
    set_preferred_network,
    with_client,
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

    @patch("os.name", "posix")
    def test_posix_path(self, tmp_path, monkeypatch):
        """Test config dir path on POSIX systems."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config_dir = get_config_dir()

        expected = tmp_path / ".config" / "eero-api"
        assert config_dir == expected

    def test_windows_path(self, tmp_path, monkeypatch):
        """Test config dir path on Windows (skipped on non-Windows)."""

        if os.name != "nt":
            pytest.skip("Windows-only test")

        monkeypatch.setenv("APPDATA", str(tmp_path))

        config_dir = get_config_dir()

        expected = tmp_path / "eero-api"
        assert config_dir == expected


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
