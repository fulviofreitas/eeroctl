"""Unit tests for eero.cli.context module.

Tests cover:
- EeroCliContext dataclass initialization and properties
- create_cli_context factory function
- ensure_cli_context and get_cli_context helpers
- OutputRenderer integration
"""

from unittest.mock import MagicMock

import click
import pytest

from eeroctl.context import EeroCliContext, create_cli_context, ensure_cli_context, get_cli_context
from eeroctl.output import OutputFormat

# ========================== EeroCliContext Tests ==========================


class TestEeroCliContext:
    """Tests for EeroCliContext dataclass."""

    def test_default_initialization(self):
        """Test EeroCliContext initializes with sensible defaults."""
        ctx = EeroCliContext()

        assert ctx.client is None
        assert ctx.console is not None
        assert ctx.network_id is None
        assert ctx.output_format == "table"
        assert ctx.detail_level == "brief"
        assert ctx.non_interactive is False
        assert ctx.force is False
        assert ctx.dry_run is False
        assert ctx.quiet is False
        assert ctx.debug is False

    def test_custom_initialization(self):
        """Test EeroCliContext with custom values."""
        ctx = EeroCliContext(
            network_id="net_123",
            output_format="json",
            detail_level="full",
            non_interactive=True,
            force=True,
            debug=True,
        )

        assert ctx.network_id == "net_123"
        assert ctx.output_format == "json"
        assert ctx.detail_level == "full"
        assert ctx.non_interactive is True
        assert ctx.force is True
        assert ctx.debug is True

    def test_is_json_output_true(self):
        """Test is_json_output returns True for JSON format."""
        ctx = EeroCliContext(output_format="json")
        assert ctx.is_json_output() is True

    def test_is_json_output_false(self):
        """Test is_json_output returns False for non-JSON formats."""
        for fmt in ("table", "list"):
            ctx = EeroCliContext(output_format=fmt)
            assert ctx.is_json_output() is False

    def test_extra_storage_get_set(self):
        """Test extra storage get/set methods."""
        ctx = EeroCliContext()

        # Test set and get
        ctx.set("custom_key", "custom_value")
        assert ctx.get("custom_key") == "custom_value"

        # Test default value
        assert ctx.get("nonexistent", "default") == "default"

        # Test None for missing key
        assert ctx.get("missing") is None

    def test_extra_storage_bracket_syntax(self):
        """Test extra storage with [] syntax."""
        ctx = EeroCliContext()

        ctx["key1"] = "value1"
        assert ctx["key1"] == "value1"
        assert ctx["missing"] is None

    def test_output_manager_auto_created(self):
        """Test OutputManager is auto-created in post_init."""
        ctx = EeroCliContext()
        assert ctx.output_manager is not None

    def test_renderer_property_creates_instance(self):
        """Test renderer property creates OutputRenderer on first access."""
        ctx = EeroCliContext(output_format="table", network_id="net_123")

        renderer = ctx.renderer
        assert renderer is not None

        # Should return same instance on second access
        assert ctx.renderer is renderer

    def test_renderer_respects_output_format(self):
        """Test renderer respects the output format setting."""
        ctx = EeroCliContext(output_format="json")
        renderer = ctx.renderer
        assert renderer.ctx.format == OutputFormat.JSON

    def test_renderer_respects_quiet_setting(self):
        """Test renderer respects quiet setting."""
        ctx = EeroCliContext(quiet=True)
        renderer = ctx.renderer
        assert renderer.ctx.quiet is True


# ========================== create_cli_context Tests ==========================


class TestCreateCliContext:
    """Tests for create_cli_context factory function."""

    def test_creates_context_with_defaults(self):
        """Test factory creates context with default values."""
        ctx = create_cli_context()

        assert isinstance(ctx, EeroCliContext)
        assert ctx.debug is False
        assert ctx.verbose is False
        assert ctx.output_format == "table"
        assert ctx.network_id is None

    def test_creates_context_with_custom_values(self):
        """Test factory creates context with specified values."""
        ctx = create_cli_context(
            debug=True,
            verbose=True,
            output_format="json",
            detail_level="full",
            network_id="net_abc",
            non_interactive=True,
            force=True,
            dry_run=True,
            quiet=True,
            no_color=True,
            timeout=60,
            retries=3,
            retry_backoff=1000,
        )

        assert ctx.debug is True
        assert ctx.verbose is True
        assert ctx.output_format == "json"
        assert ctx.detail_level == "full"
        assert ctx.network_id == "net_abc"
        assert ctx.non_interactive is True
        assert ctx.force is True
        assert ctx.dry_run is True
        assert ctx.quiet is True
        assert ctx.no_color is True
        assert ctx.timeout == 60
        assert ctx.retries == 3
        assert ctx.retry_backoff == 1000

    def test_creates_console_with_settings(self):
        """Test factory creates Console respecting no_color and quiet."""
        ctx = create_cli_context(no_color=True, quiet=True)

        # Console should be configured
        assert ctx.console is not None
        # Output manager should be created
        assert ctx.output_manager is not None


# ========================== ensure_cli_context Tests ==========================


class TestEnsureCliContext:
    """Tests for ensure_cli_context helper."""

    def test_creates_context_when_obj_is_none(self):
        """Test creates new context when ctx.obj is None."""
        click_ctx = MagicMock(spec=click.Context)
        click_ctx.obj = None

        result = ensure_cli_context(click_ctx)

        assert isinstance(result, EeroCliContext)
        assert click_ctx.obj is result

    def test_creates_context_when_obj_is_wrong_type(self):
        """Test creates new context when ctx.obj is wrong type."""
        click_ctx = MagicMock(spec=click.Context)
        click_ctx.obj = {"some": "dict"}  # Wrong type

        result = ensure_cli_context(click_ctx)

        assert isinstance(result, EeroCliContext)
        assert click_ctx.obj is result

    def test_returns_existing_context(self):
        """Test returns existing context when already set."""
        click_ctx = MagicMock(spec=click.Context)
        existing_ctx = EeroCliContext(network_id="net_existing")
        click_ctx.obj = existing_ctx

        result = ensure_cli_context(click_ctx)

        assert result is existing_ctx
        assert result.network_id == "net_existing"


# ========================== get_cli_context Tests ==========================


class TestGetCliContext:
    """Tests for get_cli_context helper."""

    def test_returns_context_from_obj(self):
        """Test returns context when set on ctx.obj."""
        click_ctx = MagicMock(spec=click.Context)
        expected = EeroCliContext(network_id="net_test")
        click_ctx.obj = expected

        result = get_cli_context(click_ctx)

        assert result is expected

    def test_creates_default_when_obj_is_none(self):
        """Test creates default context when ctx.obj is None and no parent."""
        click_ctx = MagicMock(spec=click.Context)
        click_ctx.obj = None
        click_ctx.parent = None

        result = get_cli_context(click_ctx)

        assert isinstance(result, EeroCliContext)

    def test_finds_context_in_parent(self):
        """Test finds context in parent context."""
        parent_ctx = MagicMock(spec=click.Context)
        expected = EeroCliContext(network_id="net_parent")
        parent_ctx.obj = expected
        parent_ctx.parent = None

        child_ctx = MagicMock(spec=click.Context)
        child_ctx.obj = None
        child_ctx.parent = parent_ctx

        result = get_cli_context(child_ctx)

        assert result is expected

    def test_raises_for_wrong_type(self):
        """Test raises RuntimeError when obj is wrong type."""
        click_ctx = MagicMock(spec=click.Context)
        click_ctx.obj = "wrong_type"  # Not an EeroCliContext
        click_ctx.parent = None

        # First call sets ctx.obj to new EeroCliContext if obj is None
        # But if obj is a non-None wrong type after parent traversal, it raises
        # Actually, let's check the actual behavior
        click_ctx.obj = "string"  # Wrong type, not None

        with pytest.raises(RuntimeError, match="Expected EeroCliContext"):
            get_cli_context(click_ctx)

    def test_finds_context_in_grandparent(self):
        """Test finds context in grandparent context."""
        grandparent_ctx = MagicMock(spec=click.Context)
        expected = EeroCliContext(network_id="net_grandparent")
        grandparent_ctx.obj = expected
        grandparent_ctx.parent = None

        parent_ctx = MagicMock(spec=click.Context)
        parent_ctx.obj = None
        parent_ctx.parent = grandparent_ctx

        child_ctx = MagicMock(spec=click.Context)
        child_ctx.obj = None
        child_ctx.parent = parent_ctx

        result = get_cli_context(child_ctx)

        assert result is expected


# ========================== Integration Tests ==========================


class TestContextIntegration:
    """Integration tests for context module with Click."""

    def test_context_propagates_through_command_chain(self, cli_runner):
        """Test context propagates through nested Click commands."""
        from click import group, pass_context

        captured_contexts = []

        @group()
        @pass_context
        def cli(ctx):
            ctx.obj = EeroCliContext(network_id="net_main")

        @cli.command()
        @pass_context
        def subcommand(ctx):
            captured_contexts.append(get_cli_context(ctx))

        cli_runner.invoke(cli, ["subcommand"])

        assert len(captured_contexts) == 1
        assert captured_contexts[0].network_id == "net_main"

    def test_context_isolation_between_invocations(self, cli_runner):
        """Test context is isolated between separate invocations."""
        from click import group, pass_context

        contexts = []

        @group()
        @pass_context
        def cli(ctx):
            ctx.obj = EeroCliContext()
            ctx.obj.set("counter", len(contexts))
            contexts.append(ctx.obj)

        @cli.command()
        @pass_context
        def cmd(ctx):
            pass

        cli_runner.invoke(cli, ["cmd"])
        cli_runner.invoke(cli, ["cmd"])

        # Each invocation should have its own context
        assert len(contexts) == 2
        assert contexts[0].get("counter") == 0
        assert contexts[1].get("counter") == 1
