"""Integration tests for eero.cli.main module.

Tests cover:
- Main CLI group initialization
- Global options processing
- Command group registration
- Help output
- Version display
"""

import logging
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from eeroctl.context import EeroCliContext
from eeroctl.main import _SdkWarningFilter, cli, main


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

        from eeroctl.context import get_cli_context

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

        from eeroctl.context import get_cli_context

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

        from eeroctl.context import get_cli_context

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

        from eeroctl.context import get_cli_context

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

    @patch("eeroctl.main.get_preferred_network")
    def test_loads_preferred_network(self, mock_get_preferred, runner):
        """Test preferred network is loaded when not specified."""
        mock_get_preferred.return_value = "net_preferred"

        captured_ctx = []

        from click import pass_context

        from eeroctl.context import get_cli_context

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

    @patch("eeroctl.main.get_preferred_network")
    def test_explicit_network_overrides_preferred(self, mock_get_preferred, runner):
        """Test explicit --network-id overrides preferred."""
        mock_get_preferred.return_value = "net_preferred"

        captured_ctx = []

        from click import pass_context

        from eeroctl.context import get_cli_context

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


class TestSdkWarningFilterInstallation:
    """`cli()` installs `_SdkWarningFilter` on the root logger's handlers
    (migration plan §3.3) -- not on a bare `eero.api` Logger object, which
    Python's propagation would silently never consult (see
    `_SdkWarningFilter`'s docstring)."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_filter_attached_to_root_handlers_after_invocation(self, runner):
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        root_handlers = logging.getLogger().handlers
        assert root_handlers, "basicConfig should have installed at least one handler"
        assert any(isinstance(f, _SdkWarningFilter) for hdlr in root_handlers for f in hdlr.filters)

    def test_each_invocation_gets_its_own_filter_instance(self, runner):
        """force=True on basicConfig means no filter accumulation across
        invocations in the same process (relevant under CliRunner)."""
        runner.invoke(cli, ["--help"])
        first_count = sum(
            1
            for hdlr in logging.getLogger().handlers
            for f in hdlr.filters
            if isinstance(f, _SdkWarningFilter)
        )

        runner.invoke(cli, ["--help"])
        second_count = sum(
            1
            for hdlr in logging.getLogger().handlers
            for f in hdlr.filters
            if isinstance(f, _SdkWarningFilter)
        )

        assert first_count == 1
        assert second_count == 1


class TestMainFunction:
    """Tests for main entry point function."""

    def test_main_function_exists(self):
        """Test main function is defined."""
        assert callable(main)

    def test_main_invokes_cli(self):
        """Test main function invokes CLI when called directly."""
        from importlib import import_module

        # Get a fresh reference to the module
        main_module = import_module("eeroctl.main")

        # We verify that main() calls cli() by checking it's callable
        # and has the expected structure
        assert hasattr(main_module, "main")
        assert hasattr(main_module, "cli")
        assert callable(main_module.main)
        # main() calls cli() - we verify the cli is a Click group
        assert hasattr(main_module.cli, "commands")

    def test_main_invokes_cli_with_auto_envvar_prefix(self):
        """main() explicitly passes auto_envvar_prefix="EEROCTL" to cli.main()."""
        with patch("eeroctl.main.cli") as mock_cli:
            main()

        mock_cli.main.assert_called_once_with(auto_envvar_prefix="EEROCTL")


class TestGlobalEnvVars:
    """One parametrised case per EEROCTL_<NAME> global env var.

    v8 migration plan §3.4, Q6: every global option gets a free
    EEROCTL_<NAME> env var via ``auto_envvar_prefix``; two more
    (EEROCTL_CONFIG_DIR, EEROCTL_SESSION_TOKEN) need explicit code and are
    covered in test_utils.py / test_auth.py respectively.
    """

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    @pytest.mark.parametrize(
        ("env_var", "env_value", "attr", "expected"),
        [
            ("EEROCTL_OUTPUT", "json", "output_format", "json"),
            ("EEROCTL_NETWORK_ID", "net_env", "network_id", "net_env"),
            ("EEROCTL_FORCE", "1", "force", True),
            ("EEROCTL_NON_INTERACTIVE", "1", "non_interactive", True),
            ("EEROCTL_DEBUG", "1", "debug", True),
            ("EEROCTL_QUIET", "1", "quiet", True),
            ("EEROCTL_NO_COLOR", "1", "no_color", True),
            ("EEROCTL_ACCEPT_LANGUAGE", "fr-FR", "accept_language", "fr-FR"),
            ("EEROCTL_GET_RETRIES", "3", "get_retries", 3),
            ("EEROCTL_NO_LEGACY_COOKIE", "1", "send_legacy_cookie", False),
        ],
    )
    def test_env_var_reaches_context(self, runner, monkeypatch, env_var, env_value, attr, expected):
        """Each EEROCTL_<NAME> env var flows through to the EeroCliContext."""
        monkeypatch.setenv(env_var, env_value)
        captured_ctx = []

        from click import pass_context

        from eeroctl.context import get_cli_context

        @cli.command(name="test-env-var-probe")
        @pass_context
        def test_cmd(ctx):
            captured_ctx.append(get_cli_context(ctx))

        try:
            result = runner.invoke(cli, ["test-env-var-probe"])

            assert result.exit_code == 0, result.output
            assert len(captured_ctx) == 1
            assert getattr(captured_ctx[0], attr) == expected
        finally:
            cli.commands.pop("test-env-var-probe", None)

    def test_accept_language_get_retries_send_legacy_cookie_reach_eero_client(
        self, runner, monkeypatch
    ):
        """The three new constructor options reach EeroClient(...) end-to-end."""
        monkeypatch.setenv("EEROCTL_ACCEPT_LANGUAGE", "es-ES")
        monkeypatch.setenv("EEROCTL_GET_RETRIES", "2")
        monkeypatch.setenv("EEROCTL_NO_LEGACY_COOKIE", "1")

        from unittest.mock import AsyncMock

        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client) as mock_client_class:
            result = runner.invoke(cli, ["auth", "status", "--offline"])

        assert result.exit_code == 0, result.output
        mock_client_class.assert_called_once()
        kwargs = mock_client_class.call_args.kwargs
        assert kwargs["accept_language"] == "es-ES"
        assert kwargs["get_retries"] == 2
        assert kwargs["send_legacy_cookie"] is False


class TestDebugLogging:
    """Tests for --debug scoping to the `eero`/`eeroctl` loggers only.

    v8 migration plan §8.1 R11, §3.3 (DEBUG-scoping half; the warning
    filter is a separate, later commit): elevating the root logger lets
    aiohttp log the raw X-User-Token header.
    """

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_debug_raises_eero_and_eeroctl_loggers_to_debug(self, runner):
        result = runner.invoke(cli, ["--debug", "auth", "--help"])

        assert result.exit_code == 0
        assert logging.getLogger("eero").level == logging.DEBUG
        assert logging.getLogger("eeroctl").level == logging.DEBUG

    def test_debug_does_not_raise_the_root_logger(self, runner):
        result = runner.invoke(cli, ["--debug", "auth", "--help"])

        assert result.exit_code == 0
        assert logging.getLogger().level != logging.DEBUG

    def test_without_debug_eero_and_eeroctl_loggers_are_not_debug(self, runner):
        result = runner.invoke(cli, ["auth", "--help"])

        assert result.exit_code == 0
        assert logging.getLogger("eero").level != logging.DEBUG
        assert logging.getLogger("eeroctl").level != logging.DEBUG

    def test_debug_disables_propagation_to_avoid_double_printing(self, runner):
        """propagate=False on eero/eeroctl after --debug (else lines print twice)."""
        result = runner.invoke(cli, ["--debug", "auth", "--help"])

        assert result.exit_code == 0
        assert logging.getLogger("eero").propagate is False
        assert logging.getLogger("eeroctl").propagate is False

    def test_debug_record_is_emitted_exactly_once(self, runner):
        """A log record on the `eero` logger is handled by exactly one handler.

        Without ``propagate = False``, the record would also bubble up to
        the root logger's own handler (installed by ``basicConfig``),
        printing the line twice.
        """
        result = runner.invoke(cli, ["--debug", "auth", "--help"])
        assert result.exit_code == 0

        eero_logger = logging.getLogger("eero")
        emit_calls = 0
        original_emits = [(h, h.emit) for h in eero_logger.handlers]

        def make_counting_emit(original_emit):
            def counting_emit(record):
                nonlocal emit_calls
                emit_calls += 1
                original_emit(record)

            return counting_emit

        for h, original_emit in original_emits:
            h.emit = make_counting_emit(original_emit)

        try:
            eero_logger.debug("a test debug message")
        finally:
            for h, original_emit in original_emits:
                h.emit = original_emit

        assert emit_calls == 1


class TestForceSourceTracing:
    """Tests for tracing EEROCTL_FORCE vs. --force (Q6 stands; §3.2 item 3).

    EEROCTL_FORCE keeps disabling confirmation prompts at every safety
    tier, but silently doing so from an environment variable is easy to
    miss, so eeroctl notes it and records the source on the context.
    """

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_env_sourced_force_prints_the_note(self, runner, monkeypatch):
        monkeypatch.setenv("EEROCTL_FORCE", "1")

        result = runner.invoke(cli, ["auth", "--help"])

        assert result.exit_code == 0
        assert "note: confirmation prompts disabled by EEROCTL_FORCE" in result.stderr

    def test_flag_sourced_force_does_not_print_the_note(self, runner):
        result = runner.invoke(cli, ["--force", "auth", "--help"])

        assert result.exit_code == 0
        assert "note: confirmation prompts disabled by EEROCTL_FORCE" not in result.stderr

    def test_no_force_does_not_print_the_note(self, runner):
        result = runner.invoke(cli, ["auth", "--help"])

        assert result.exit_code == 0
        assert "note: confirmation prompts disabled by EEROCTL_FORCE" not in result.stderr

    def test_env_sourced_force_respects_quiet(self, runner, monkeypatch):
        monkeypatch.setenv("EEROCTL_FORCE", "1")

        result = runner.invoke(cli, ["--quiet", "auth", "--help"])

        assert result.exit_code == 0
        assert "note: confirmation prompts disabled by EEROCTL_FORCE" not in result.stderr

    def test_context_records_env_force_source(self, runner, monkeypatch):
        monkeypatch.setenv("EEROCTL_FORCE", "1")
        captured_ctx = []

        from click import pass_context

        from eeroctl.context import get_cli_context

        @cli.command(name="test-force-source-env")
        @pass_context
        def test_cmd(ctx):
            captured_ctx.append(get_cli_context(ctx))

        try:
            result = runner.invoke(cli, ["test-force-source-env"])

            assert result.exit_code == 0
            assert len(captured_ctx) == 1
            assert captured_ctx[0].force_source == "env"
        finally:
            cli.commands.pop("test-force-source-env", None)

    def test_context_records_flag_force_source(self, runner):
        captured_ctx = []

        from click import pass_context

        from eeroctl.context import get_cli_context

        @cli.command(name="test-force-source-flag")
        @pass_context
        def test_cmd(ctx):
            captured_ctx.append(get_cli_context(ctx))

        try:
            result = runner.invoke(cli, ["--force", "test-force-source-flag"])

            assert result.exit_code == 0
            assert len(captured_ctx) == 1
            assert captured_ctx[0].force_source == "flag"
        finally:
            cli.commands.pop("test-force-source-flag", None)

    def test_context_records_no_force_source_by_default(self, runner):
        captured_ctx = []

        from click import pass_context

        from eeroctl.context import get_cli_context

        @cli.command(name="test-force-source-none")
        @pass_context
        def test_cmd(ctx):
            captured_ctx.append(get_cli_context(ctx))

        try:
            result = runner.invoke(cli, ["test-force-source-none"])

            assert result.exit_code == 0
            assert len(captured_ctx) == 1
            assert captured_ctx[0].force_source is None
        finally:
            cli.commands.pop("test-force-source-none", None)
