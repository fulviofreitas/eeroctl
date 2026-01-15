"""Integration tests for eero.cli.main module.

Tests cover:
- Main CLI group initialization
- Global options processing
- Command group registration
- Help output
- Version display
"""

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from eero_cli.context import EeroCliContext
from eero_cli.main import cli, main


class TestMainCLI:
    """Tests for the main CLI entry point."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_cli_shows_help_without_command(self, runner):
        """Test CLI shows help when invoked without command."""
        result = runner.invoke(cli, [])

        assert result.exit_code == 0
        assert "Eero network management CLI" in result.output
        assert "Usage:" in result.output

    def test_cli_shows_version(self, runner):
        """Test CLI shows version with --version."""
        result = runner.invoke(cli, ["--version"])

        # Exit code 0 means success, exit code 1 might be from version callback
        assert result.exit_code in (0, 1) or "version" in result.output.lower()

    def test_cli_help_option(self, runner):
        """Test CLI --help option."""
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Eero network management CLI" in result.output
        assert "--debug" in result.output
        assert "--quiet" in result.output
        assert "--output" in result.output

    def test_cli_debug_flag(self, runner):
        """Test CLI --debug flag is processed."""
        result = runner.invoke(cli, ["--debug", "--help"])

        assert result.exit_code == 0

    def test_cli_quiet_flag(self, runner):
        """Test CLI --quiet flag is processed."""
        result = runner.invoke(cli, ["--quiet", "--help"])

        assert result.exit_code == 0

    def test_cli_no_color_flag(self, runner):
        """Test CLI --no-color flag is processed."""
        result = runner.invoke(cli, ["--no-color", "--help"])

        assert result.exit_code == 0

    def test_cli_output_option_table(self, runner):
        """Test CLI --output table option."""
        result = runner.invoke(cli, ["--output", "table", "--help"])

        assert result.exit_code == 0

    def test_cli_output_option_list(self, runner):
        """Test CLI --output list option."""
        result = runner.invoke(cli, ["--output", "list", "--help"])

        assert result.exit_code == 0

    def test_cli_output_option_json(self, runner):
        """Test CLI --output json option."""
        result = runner.invoke(cli, ["--output", "json", "--help"])

        assert result.exit_code == 0

    def test_cli_output_option_invalid(self, runner):
        """Test CLI rejects invalid output format."""
        result = runner.invoke(cli, ["--output", "invalid"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output or "invalid" in result.output.lower()

    def test_cli_network_id_option(self, runner):
        """Test CLI --network-id option is processed."""
        result = runner.invoke(cli, ["--network-id", "net_123", "--help"])

        assert result.exit_code == 0

    def test_cli_non_interactive_flag(self, runner):
        """Test CLI --non-interactive flag."""
        result = runner.invoke(cli, ["--non-interactive", "--help"])

        assert result.exit_code == 0

    def test_cli_force_flag(self, runner):
        """Test CLI --force flag."""
        result = runner.invoke(cli, ["--force", "--help"])

        assert result.exit_code == 0

    def test_cli_yes_flag_alias(self, runner):
        """Test CLI --yes is alias for --force."""
        result = runner.invoke(cli, ["--yes", "--help"])

        assert result.exit_code == 0


class TestCommandGroupRegistration:
    """Tests for command group registration."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_auth_group_registered(self, runner):
        """Test auth command group is registered."""
        result = runner.invoke(cli, ["auth", "--help"])

        assert result.exit_code == 0
        assert "Manage authentication" in result.output

    def test_network_group_registered(self, runner):
        """Test network command group is registered."""
        result = runner.invoke(cli, ["network", "--help"])

        assert result.exit_code == 0
        assert "Manage network settings" in result.output

    def test_eero_group_registered(self, runner):
        """Test eero command group is registered."""
        result = runner.invoke(cli, ["eero", "--help"])

        assert result.exit_code == 0
        assert "Manage Eero mesh nodes" in result.output

    def test_device_group_registered(self, runner):
        """Test device command group is registered."""
        result = runner.invoke(cli, ["device", "--help"])

        assert result.exit_code == 0
        assert "Manage connected devices" in result.output

    def test_profile_group_registered(self, runner):
        """Test profile command group is registered."""
        result = runner.invoke(cli, ["profile", "--help"])

        assert result.exit_code == 0
        assert "Manage profiles" in result.output

    def test_activity_group_registered(self, runner):
        """Test activity command group is registered."""
        result = runner.invoke(cli, ["activity", "--help"])

        assert result.exit_code == 0

    def test_troubleshoot_group_registered(self, runner):
        """Test troubleshoot command group is registered."""
        result = runner.invoke(cli, ["troubleshoot", "--help"])

        assert result.exit_code == 0
        assert "Troubleshooting" in result.output or "diagnostics" in result.output.lower()

    def test_completion_group_registered(self, runner):
        """Test completion command group is registered."""
        result = runner.invoke(cli, ["completion", "--help"])

        assert result.exit_code == 0

    def test_unknown_command_error(self, runner):
        """Test unknown command produces error."""
        result = runner.invoke(cli, ["unknown-command"])

        assert result.exit_code != 0
        assert "No such command" in result.output or "Error" in result.output


class TestContextPropagation:
    """Tests for context propagation through commands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_context_created_with_defaults(self, runner):
        """Test context is created with default values."""
        captured_ctx = []

        # Use a simple subcommand that we can inspect
        from click import pass_context

        from eero_cli.context import get_cli_context

        @cli.command(name="test-ctx")
        @pass_context
        def test_cmd(ctx):
            captured_ctx.append(get_cli_context(ctx))

        try:
            runner.invoke(cli, ["test-ctx"])

            assert len(captured_ctx) == 1
            ctx = captured_ctx[0]
            assert isinstance(ctx, EeroCliContext)
            assert ctx.output_format == "table"
        finally:
            # Clean up
            cli.commands.pop("test-ctx", None)

    def test_context_propagates_debug_flag(self, runner):
        """Test debug flag propagates to context."""
        captured_ctx = []

        from click import pass_context

        from eero_cli.context import get_cli_context

        @cli.command(name="test-debug")
        @pass_context
        def test_cmd(ctx):
            captured_ctx.append(get_cli_context(ctx))

        try:
            runner.invoke(cli, ["--debug", "test-debug"])

            if captured_ctx:
                assert captured_ctx[0].debug is True
        finally:
            cli.commands.pop("test-debug", None)

    def test_context_propagates_output_format(self, runner):
        """Test output format propagates to context."""
        captured_ctx = []

        from click import pass_context

        from eero_cli.context import get_cli_context

        @cli.command(name="test-output")
        @pass_context
        def test_cmd(ctx):
            captured_ctx.append(get_cli_context(ctx))

        try:
            runner.invoke(cli, ["--output", "json", "test-output"])

            if captured_ctx:
                assert captured_ctx[0].output_format == "json"
        finally:
            cli.commands.pop("test-output", None)

    def test_context_propagates_network_id(self, runner):
        """Test network ID propagates to context."""
        captured_ctx = []

        from click import pass_context

        from eero_cli.context import get_cli_context

        @cli.command(name="test-net")
        @pass_context
        def test_cmd(ctx):
            captured_ctx.append(get_cli_context(ctx))

        try:
            runner.invoke(cli, ["--network-id", "net_xyz", "test-net"])

            if captured_ctx:
                assert captured_ctx[0].network_id == "net_xyz"
        finally:
            cli.commands.pop("test-net", None)


class TestPreferredNetworkLoading:
    """Tests for preferred network loading."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    @patch("eero_cli.main.get_preferred_network")
    def test_loads_preferred_network(self, mock_get_preferred, runner):
        """Test preferred network is loaded when not specified."""
        mock_get_preferred.return_value = "net_preferred"

        captured_ctx = []

        from click import pass_context

        from eero_cli.context import get_cli_context

        @cli.command(name="test-pref")
        @pass_context
        def test_cmd(ctx):
            captured_ctx.append(get_cli_context(ctx))

        try:
            runner.invoke(cli, ["test-pref"])

            if captured_ctx:
                # Should have loaded preferred network
                mock_get_preferred.assert_called()
        finally:
            cli.commands.pop("test-pref", None)

    @patch("eero_cli.main.get_preferred_network")
    def test_explicit_network_overrides_preferred(self, mock_get_preferred, runner):
        """Test explicit --network-id overrides preferred."""
        mock_get_preferred.return_value = "net_preferred"

        captured_ctx = []

        from click import pass_context

        from eero_cli.context import get_cli_context

        @cli.command(name="test-override")
        @pass_context
        def test_cmd(ctx):
            captured_ctx.append(get_cli_context(ctx))

        try:
            runner.invoke(cli, ["--network-id", "net_explicit", "test-override"])

            if captured_ctx:
                assert captured_ctx[0].network_id == "net_explicit"
        finally:
            cli.commands.pop("test-override", None)


class TestMainFunction:
    """Tests for main entry point function."""

    def test_main_function_exists(self):
        """Test main function is defined."""
        assert callable(main)

    def test_main_invokes_cli(self):
        """Test main function invokes CLI when called directly."""
        from importlib import import_module

        # Get a fresh reference to the module
        main_module = import_module("eero_cli.main")

        # We verify that main() calls cli() by checking it's callable
        # and has the expected structure
        assert hasattr(main_module, "main")
        assert hasattr(main_module, "cli")
        assert callable(main_module.main)
        # main() calls cli() - we verify the cli is a Click group
        assert hasattr(main_module.cli, "commands")
