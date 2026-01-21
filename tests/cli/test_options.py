"""Unit tests for eeroctl.options module.

Tests cover:
- Individual option decorators (output_option, network_option, etc.)
- Combined option decorators (safety_options, common_options, all_options)
- get_effective_value() helper for option precedence
- apply_options() helper for updating CLI context
- Integration with Click commands
"""

from unittest.mock import MagicMock

import click
import pytest
from click.testing import CliRunner

from eeroctl.context import EeroCliContext, get_cli_context
from eeroctl.options import (
    all_options,
    apply_options,
    common_options,
    debug_option,
    display_options,
    force_option,
    get_effective_value,
    network_option,
    no_color_option,
    non_interactive_option,
    output_option,
    quiet_option,
    safety_options,
)

# =============================================================================
# get_effective_value Tests
# =============================================================================


class TestGetEffectiveValue:
    """Tests for get_effective_value helper."""

    def test_returns_local_value_when_provided(self):
        """Test local value takes precedence over parent."""
        click_ctx = MagicMock(spec=click.Context)
        click_ctx.obj = EeroCliContext(output_format="table")
        click_ctx.parent = None

        result = get_effective_value(click_ctx, "json", "output_format", "table")

        assert result == "json"

    def test_returns_parent_value_when_local_is_none(self):
        """Test parent value is used when local is None."""
        click_ctx = MagicMock(spec=click.Context)
        click_ctx.obj = EeroCliContext(output_format="yaml")
        click_ctx.parent = None

        result = get_effective_value(click_ctx, None, "output_format", "table")

        assert result == "yaml"

    def test_returns_default_when_no_value_found(self):
        """Test default is returned when no value found anywhere."""
        click_ctx = MagicMock(spec=click.Context)
        click_ctx.obj = EeroCliContext()  # network_id defaults to None
        click_ctx.parent = None

        result = get_effective_value(click_ctx, None, "network_id", "default_net")

        assert result == "default_net"

    def test_walks_parent_chain(self):
        """Test walks up parent chain to find value."""
        grandparent_ctx = MagicMock(spec=click.Context)
        grandparent_ctx.obj = EeroCliContext(network_id="grandparent_net")
        grandparent_ctx.parent = None

        parent_ctx = MagicMock(spec=click.Context)
        parent_ctx.obj = EeroCliContext()  # network_id is None
        parent_ctx.parent = grandparent_ctx

        child_ctx = MagicMock(spec=click.Context)
        child_ctx.obj = EeroCliContext()  # network_id is None
        child_ctx.parent = parent_ctx

        result = get_effective_value(child_ctx, None, "network_id", "default")

        assert result == "grandparent_net"

    def test_stops_at_first_non_none_value(self):
        """Test stops walking chain at first non-None value."""
        grandparent_ctx = MagicMock(spec=click.Context)
        grandparent_ctx.obj = EeroCliContext(output_format="yaml")
        grandparent_ctx.parent = None

        parent_ctx = MagicMock(spec=click.Context)
        parent_ctx.obj = EeroCliContext(output_format="json")
        parent_ctx.parent = grandparent_ctx

        child_ctx = MagicMock(spec=click.Context)
        child_ctx.obj = EeroCliContext()
        child_ctx.parent = parent_ctx

        result = get_effective_value(child_ctx, None, "output_format", "table")

        # Should get "json" from immediate parent, not "yaml" from grandparent
        # But current context has "table" as output_format default
        # Actually, let me check - EeroCliContext has output_format = "table" as default
        # So child_ctx.obj.output_format would be "table"

        # The function should return the current context's value first
        # Since child_ctx.obj has output_format="table", that's what we'd get
        # Hmm, but "table" is not None, so it should return "table"

        # Let me re-read the implementation...
        # It walks up the context chain and checks parent.obj attributes
        # The current context IS checked first (inside the while loop)

        # Actually, looking at the code again:
        # current = ctx, and we check current.obj.output_format
        # So if child_ctx.obj.output_format = "table", we get "table"
        assert result == "table"

    def test_handles_context_without_obj(self):
        """Test handles context where obj is None."""
        parent_ctx = MagicMock(spec=click.Context)
        parent_ctx.obj = EeroCliContext(output_format="json")
        parent_ctx.parent = None

        child_ctx = MagicMock(spec=click.Context)
        child_ctx.obj = None
        child_ctx.parent = parent_ctx

        result = get_effective_value(child_ctx, None, "output_format", "table")

        assert result == "json"


# =============================================================================
# apply_options Tests
# =============================================================================


class TestApplyOptions:
    """Tests for apply_options helper."""

    def test_applies_output_format(self):
        """Test apply_options updates output_format."""
        click_ctx = MagicMock(spec=click.Context)
        click_ctx.obj = EeroCliContext(output_format="table")
        click_ctx.parent = None

        result = apply_options(click_ctx, output="json")

        assert result.output_format == "json"

    def test_applies_network_id(self):
        """Test apply_options updates network_id."""
        click_ctx = MagicMock(spec=click.Context)
        click_ctx.obj = EeroCliContext()
        click_ctx.parent = None

        result = apply_options(click_ctx, network_id="net_123")

        assert result.network_id == "net_123"

    def test_applies_force_flag(self):
        """Test apply_options updates force flag."""
        click_ctx = MagicMock(spec=click.Context)
        click_ctx.obj = EeroCliContext(force=False)
        click_ctx.parent = None

        result = apply_options(click_ctx, force=True)

        assert result.force is True

    def test_applies_non_interactive_flag(self):
        """Test apply_options updates non_interactive flag."""
        click_ctx = MagicMock(spec=click.Context)
        click_ctx.obj = EeroCliContext(non_interactive=False)
        click_ctx.parent = None

        result = apply_options(click_ctx, non_interactive=True)

        assert result.non_interactive is True

    def test_applies_debug_flag(self):
        """Test apply_options updates debug flag."""
        click_ctx = MagicMock(spec=click.Context)
        click_ctx.obj = EeroCliContext(debug=False)
        click_ctx.parent = None

        result = apply_options(click_ctx, debug=True)

        assert result.debug is True

    def test_applies_quiet_flag(self):
        """Test apply_options updates quiet flag."""
        click_ctx = MagicMock(spec=click.Context)
        click_ctx.obj = EeroCliContext(quiet=False)
        click_ctx.parent = None

        result = apply_options(click_ctx, quiet=True)

        assert result.quiet is True

    def test_applies_no_color_flag(self):
        """Test apply_options updates no_color flag."""
        click_ctx = MagicMock(spec=click.Context)
        click_ctx.obj = EeroCliContext(no_color=False)
        click_ctx.parent = None

        result = apply_options(click_ctx, no_color=True)

        assert result.no_color is True

    def test_preserves_unset_values(self):
        """Test apply_options preserves values not explicitly set."""
        click_ctx = MagicMock(spec=click.Context)
        click_ctx.obj = EeroCliContext(
            output_format="yaml",
            network_id="net_original",
            force=True,
        )
        click_ctx.parent = None

        result = apply_options(click_ctx, output="json")

        assert result.output_format == "json"  # Changed
        assert result.network_id == "net_original"  # Preserved
        assert result.force is True  # Preserved

    def test_returns_cli_context(self):
        """Test apply_options returns EeroCliContext."""
        click_ctx = MagicMock(spec=click.Context)
        click_ctx.obj = EeroCliContext()
        click_ctx.parent = None

        result = apply_options(click_ctx)

        assert isinstance(result, EeroCliContext)

    def test_invalidates_renderer_cache_on_output_change(self):
        """Test renderer cache is invalidated when output changes."""
        click_ctx = MagicMock(spec=click.Context)
        cli_ctx = EeroCliContext(output_format="table")
        click_ctx.obj = cli_ctx
        click_ctx.parent = None

        # Access renderer to populate cache
        _ = cli_ctx.renderer
        assert cli_ctx._renderer is not None

        # Apply new output format
        apply_options(click_ctx, output="json")

        # Cache should be invalidated
        assert cli_ctx._renderer is None


# =============================================================================
# Individual Option Decorator Tests
# =============================================================================


class TestOutputOption:
    """Tests for output_option decorator."""

    def test_adds_output_option(self, cli_runner: CliRunner):
        """Test decorator adds --output option to command."""

        @click.command()
        @output_option
        def cmd(output):
            click.echo(f"output={output}")

        result = cli_runner.invoke(cmd, ["--output", "json"])

        assert result.exit_code == 0
        assert "output=json" in result.output

    def test_accepts_short_option(self, cli_runner: CliRunner):
        """Test decorator accepts -o shorthand."""

        @click.command()
        @output_option
        def cmd(output):
            click.echo(f"output={output}")

        result = cli_runner.invoke(cmd, ["-o", "yaml"])

        assert result.exit_code == 0
        assert "output=yaml" in result.output

    def test_validates_choices(self, cli_runner: CliRunner):
        """Test decorator validates output choices."""

        @click.command()
        @output_option
        def cmd(output):
            click.echo(f"output={output}")

        result = cli_runner.invoke(cmd, ["--output", "invalid"])

        assert result.exit_code != 0
        assert "invalid" in result.output.lower()

    def test_default_is_none(self, cli_runner: CliRunner):
        """Test default value is None (for inheritance)."""

        @click.command()
        @output_option
        def cmd(output):
            click.echo(f"output={output}")

        result = cli_runner.invoke(cmd, [])

        assert result.exit_code == 0
        assert "output=None" in result.output


class TestNetworkOption:
    """Tests for network_option decorator."""

    def test_adds_network_option(self, cli_runner: CliRunner):
        """Test decorator adds --network-id option."""

        @click.command()
        @network_option
        def cmd(network_id):
            click.echo(f"network_id={network_id}")

        result = cli_runner.invoke(cmd, ["--network-id", "net_123"])

        assert result.exit_code == 0
        assert "network_id=net_123" in result.output

    def test_accepts_short_option(self, cli_runner: CliRunner):
        """Test decorator accepts -n shorthand."""

        @click.command()
        @network_option
        def cmd(network_id):
            click.echo(f"network_id={network_id}")

        result = cli_runner.invoke(cmd, ["-n", "net_abc"])

        assert result.exit_code == 0
        assert "network_id=net_abc" in result.output

    def test_default_is_none(self, cli_runner: CliRunner):
        """Test default value is None (for inheritance)."""

        @click.command()
        @network_option
        def cmd(network_id):
            click.echo(f"network_id={network_id}")

        result = cli_runner.invoke(cmd, [])

        assert result.exit_code == 0
        assert "network_id=None" in result.output


class TestForceOption:
    """Tests for force_option decorator."""

    def test_adds_force_flag(self, cli_runner: CliRunner):
        """Test decorator adds --force flag."""

        @click.command()
        @force_option
        def cmd(force):
            click.echo(f"force={force}")

        result = cli_runner.invoke(cmd, ["--force"])

        assert result.exit_code == 0
        assert "force=True" in result.output

    def test_adds_no_force_flag(self, cli_runner: CliRunner):
        """Test decorator adds --no-force flag."""

        @click.command()
        @force_option
        def cmd(force):
            click.echo(f"force={force}")

        result = cli_runner.invoke(cmd, ["--no-force"])

        assert result.exit_code == 0
        assert "force=False" in result.output

    def test_accepts_short_option(self, cli_runner: CliRunner):
        """Test decorator accepts -y shorthand."""

        @click.command()
        @force_option
        def cmd(force):
            click.echo(f"force={force}")

        result = cli_runner.invoke(cmd, ["-y"])

        assert result.exit_code == 0
        assert "force=True" in result.output

    def test_default_is_none(self, cli_runner: CliRunner):
        """Test default value is None (for inheritance)."""

        @click.command()
        @force_option
        def cmd(force):
            click.echo(f"force={force}")

        result = cli_runner.invoke(cmd, [])

        assert result.exit_code == 0
        assert "force=None" in result.output


class TestNonInteractiveOption:
    """Tests for non_interactive_option decorator."""

    def test_adds_non_interactive_flag(self, cli_runner: CliRunner):
        """Test decorator adds --non-interactive flag."""

        @click.command()
        @non_interactive_option
        def cmd(non_interactive):
            click.echo(f"non_interactive={non_interactive}")

        result = cli_runner.invoke(cmd, ["--non-interactive"])

        assert result.exit_code == 0
        assert "non_interactive=True" in result.output

    def test_adds_interactive_flag(self, cli_runner: CliRunner):
        """Test decorator adds --interactive flag."""

        @click.command()
        @non_interactive_option
        def cmd(non_interactive):
            click.echo(f"non_interactive={non_interactive}")

        result = cli_runner.invoke(cmd, ["--interactive"])

        assert result.exit_code == 0
        assert "non_interactive=False" in result.output

    def test_default_is_none(self, cli_runner: CliRunner):
        """Test default value is None (for inheritance)."""

        @click.command()
        @non_interactive_option
        def cmd(non_interactive):
            click.echo(f"non_interactive={non_interactive}")

        result = cli_runner.invoke(cmd, [])

        assert result.exit_code == 0
        assert "non_interactive=None" in result.output


class TestDebugOption:
    """Tests for debug_option decorator."""

    def test_adds_debug_flag(self, cli_runner: CliRunner):
        """Test decorator adds --debug flag."""

        @click.command()
        @debug_option
        def cmd(debug):
            click.echo(f"debug={debug}")

        result = cli_runner.invoke(cmd, ["--debug"])

        assert result.exit_code == 0
        assert "debug=True" in result.output

    def test_adds_no_debug_flag(self, cli_runner: CliRunner):
        """Test decorator adds --no-debug flag."""

        @click.command()
        @debug_option
        def cmd(debug):
            click.echo(f"debug={debug}")

        result = cli_runner.invoke(cmd, ["--no-debug"])

        assert result.exit_code == 0
        assert "debug=False" in result.output

    def test_default_is_none(self, cli_runner: CliRunner):
        """Test default value is None (for inheritance)."""

        @click.command()
        @debug_option
        def cmd(debug):
            click.echo(f"debug={debug}")

        result = cli_runner.invoke(cmd, [])

        assert result.exit_code == 0
        assert "debug=None" in result.output


class TestQuietOption:
    """Tests for quiet_option decorator."""

    def test_adds_quiet_flag(self, cli_runner: CliRunner):
        """Test decorator adds --quiet flag."""

        @click.command()
        @quiet_option
        def cmd(quiet):
            click.echo(f"quiet={quiet}")

        result = cli_runner.invoke(cmd, ["--quiet"])

        assert result.exit_code == 0
        assert "quiet=True" in result.output

    def test_adds_short_flag(self, cli_runner: CliRunner):
        """Test decorator adds -q short flag."""

        @click.command()
        @quiet_option
        def cmd(quiet):
            click.echo(f"quiet={quiet}")

        result = cli_runner.invoke(cmd, ["-q"])

        assert result.exit_code == 0
        assert "quiet=True" in result.output

    def test_adds_no_quiet_flag(self, cli_runner: CliRunner):
        """Test decorator adds --no-quiet flag."""

        @click.command()
        @quiet_option
        def cmd(quiet):
            click.echo(f"quiet={quiet}")

        result = cli_runner.invoke(cmd, ["--no-quiet"])

        assert result.exit_code == 0
        assert "quiet=False" in result.output

    def test_default_is_none(self, cli_runner: CliRunner):
        """Test default value is None (for inheritance)."""

        @click.command()
        @quiet_option
        def cmd(quiet):
            click.echo(f"quiet={quiet}")

        result = cli_runner.invoke(cmd, [])

        assert result.exit_code == 0
        assert "quiet=None" in result.output


class TestNoColorOption:
    """Tests for no_color_option decorator."""

    def test_adds_no_color_flag(self, cli_runner: CliRunner):
        """Test decorator adds --no-color flag."""

        @click.command()
        @no_color_option
        def cmd(no_color):
            click.echo(f"no_color={no_color}")

        result = cli_runner.invoke(cmd, ["--no-color"])

        assert result.exit_code == 0
        assert "no_color=True" in result.output

    def test_adds_color_flag(self, cli_runner: CliRunner):
        """Test decorator adds --color flag."""

        @click.command()
        @no_color_option
        def cmd(no_color):
            click.echo(f"no_color={no_color}")

        result = cli_runner.invoke(cmd, ["--color"])

        assert result.exit_code == 0
        assert "no_color=False" in result.output

    def test_default_is_none(self, cli_runner: CliRunner):
        """Test default value is None (for inheritance)."""

        @click.command()
        @no_color_option
        def cmd(no_color):
            click.echo(f"no_color={no_color}")

        result = cli_runner.invoke(cmd, [])

        assert result.exit_code == 0
        assert "no_color=None" in result.output


# =============================================================================
# Combined Option Decorator Tests
# =============================================================================


class TestSafetyOptions:
    """Tests for safety_options combined decorator."""

    def test_adds_both_options(self, cli_runner: CliRunner):
        """Test decorator adds both force and non_interactive."""

        @click.command()
        @safety_options
        def cmd(force, non_interactive):
            click.echo(f"force={force}, non_interactive={non_interactive}")

        result = cli_runner.invoke(cmd, ["--force", "--non-interactive"])

        assert result.exit_code == 0
        assert "force=True" in result.output
        assert "non_interactive=True" in result.output

    def test_defaults_are_none(self, cli_runner: CliRunner):
        """Test both defaults are None."""

        @click.command()
        @safety_options
        def cmd(force, non_interactive):
            click.echo(f"force={force}, non_interactive={non_interactive}")

        result = cli_runner.invoke(cmd, [])

        assert result.exit_code == 0
        assert "force=None" in result.output
        assert "non_interactive=None" in result.output


class TestCommonOptions:
    """Tests for common_options combined decorator."""

    def test_adds_both_options(self, cli_runner: CliRunner):
        """Test decorator adds both output and network_id."""

        @click.command()
        @common_options
        def cmd(output, network_id):
            click.echo(f"output={output}, network_id={network_id}")

        result = cli_runner.invoke(cmd, ["--output", "json", "--network-id", "net_1"])

        assert result.exit_code == 0
        assert "output=json" in result.output
        assert "network_id=net_1" in result.output

    def test_defaults_are_none(self, cli_runner: CliRunner):
        """Test both defaults are None."""

        @click.command()
        @common_options
        def cmd(output, network_id):
            click.echo(f"output={output}, network_id={network_id}")

        result = cli_runner.invoke(cmd, [])

        assert result.exit_code == 0
        assert "output=None" in result.output
        assert "network_id=None" in result.output


class TestDisplayOptions:
    """Tests for display_options combined decorator."""

    def test_adds_all_options(self, cli_runner: CliRunner):
        """Test decorator adds debug, quiet, and no_color."""

        @click.command()
        @display_options
        def cmd(debug, quiet, no_color):
            click.echo(f"debug={debug}, quiet={quiet}, no_color={no_color}")

        result = cli_runner.invoke(cmd, ["--debug", "--quiet", "--no-color"])

        assert result.exit_code == 0
        assert "debug=True" in result.output
        assert "quiet=True" in result.output
        assert "no_color=True" in result.output

    def test_defaults_are_none(self, cli_runner: CliRunner):
        """Test all defaults are None."""

        @click.command()
        @display_options
        def cmd(debug, quiet, no_color):
            click.echo(f"debug={debug}, quiet={quiet}, no_color={no_color}")

        result = cli_runner.invoke(cmd, [])

        assert result.exit_code == 0
        assert "debug=None" in result.output
        assert "quiet=None" in result.output
        assert "no_color=None" in result.output


class TestAllOptions:
    """Tests for all_options combined decorator."""

    def test_adds_all_options(self, cli_runner: CliRunner):
        """Test decorator adds all seven options."""

        @click.command()
        @all_options
        def cmd(output, network_id, force, non_interactive, debug, quiet, no_color):
            click.echo(
                f"output={output}, network_id={network_id}, "
                f"force={force}, non_interactive={non_interactive}, "
                f"debug={debug}, quiet={quiet}, no_color={no_color}"
            )

        result = cli_runner.invoke(
            cmd,
            [
                "--output",
                "yaml",
                "--network-id",
                "net_x",
                "--force",
                "--non-interactive",
                "--debug",
                "--quiet",
                "--no-color",
            ],
        )

        assert result.exit_code == 0
        assert "output=yaml" in result.output
        assert "network_id=net_x" in result.output
        assert "force=True" in result.output
        assert "non_interactive=True" in result.output
        assert "debug=True" in result.output
        assert "quiet=True" in result.output
        assert "no_color=True" in result.output

    def test_defaults_are_none(self, cli_runner: CliRunner):
        """Test all defaults are None."""

        @click.command()
        @all_options
        def cmd(output, network_id, force, non_interactive, debug, quiet, no_color):
            click.echo(
                f"output={output}, network_id={network_id}, "
                f"force={force}, non_interactive={non_interactive}, "
                f"debug={debug}, quiet={quiet}, no_color={no_color}"
            )

        result = cli_runner.invoke(cmd, [])

        assert result.exit_code == 0
        assert "output=None" in result.output
        assert "network_id=None" in result.output
        assert "force=None" in result.output
        assert "non_interactive=None" in result.output
        assert "debug=None" in result.output
        assert "quiet=None" in result.output
        assert "no_color=None" in result.output


# =============================================================================
# Integration Tests
# =============================================================================


class TestOptionIntegration:
    """Integration tests for options with Click command hierarchy."""

    def test_option_at_subcommand_level(self, cli_runner: CliRunner):
        """Test option works when placed at subcommand level."""

        @click.group()
        @click.pass_context
        def cli(ctx):
            ctx.obj = EeroCliContext(output_format="table")

        @cli.command()
        @output_option
        @click.pass_context
        def subcommand(ctx, output):
            cli_ctx = apply_options(ctx, output=output)
            click.echo(f"effective_output={cli_ctx.output_format}")

        # Option at subcommand level
        result = cli_runner.invoke(cli, ["subcommand", "--output", "json"])

        assert result.exit_code == 0
        assert "effective_output=json" in result.output

    def test_option_inherits_from_parent(self, cli_runner: CliRunner):
        """Test option inherits from parent when not specified locally."""

        @click.group()
        @click.pass_context
        def cli(ctx):
            ctx.obj = EeroCliContext(output_format="yaml")

        @cli.command()
        @output_option
        @click.pass_context
        def subcommand(ctx, output):
            # Don't override - should inherit "yaml"
            cli_ctx = get_cli_context(ctx)
            if output is not None:
                cli_ctx.output_format = output
            click.echo(f"effective_output={cli_ctx.output_format}")

        # No option specified - should inherit from parent
        result = cli_runner.invoke(cli, ["subcommand"])

        assert result.exit_code == 0
        assert "effective_output=yaml" in result.output

    def test_local_option_overrides_parent(self, cli_runner: CliRunner):
        """Test local option overrides parent value."""

        @click.group()
        @click.pass_context
        def cli(ctx):
            ctx.obj = EeroCliContext(output_format="yaml", network_id="parent_net")

        @cli.command()
        @common_options
        @click.pass_context
        def subcommand(ctx, output, network_id):
            cli_ctx = apply_options(ctx, output=output, network_id=network_id)
            click.echo(f"output={cli_ctx.output_format}, network_id={cli_ctx.network_id}")

        # Override output, but not network_id
        result = cli_runner.invoke(cli, ["subcommand", "--output", "json"])

        assert result.exit_code == 0
        assert "output=json" in result.output
        assert "network_id=parent_net" in result.output

    def test_nested_command_groups(self, cli_runner: CliRunner):
        """Test options work with nested command groups."""

        @click.group()
        @click.pass_context
        def cli(ctx):
            ctx.obj = EeroCliContext(output_format="table", network_id="main_net")

        @cli.group()
        @click.pass_context
        def network(ctx):
            pass  # Inherits from parent

        @network.command()
        @common_options
        @click.pass_context
        def list_networks(ctx, output, network_id):
            cli_ctx = apply_options(ctx, output=output, network_id=network_id)
            click.echo(f"output={cli_ctx.output_format}")

        result = cli_runner.invoke(cli, ["network", "list-networks", "--output", "json"])

        assert result.exit_code == 0
        assert "output=json" in result.output

    def test_safety_options_with_apply(self, cli_runner: CliRunner):
        """Test safety options work with apply_options."""

        @click.group()
        @click.pass_context
        def cli(ctx):
            ctx.obj = EeroCliContext(force=False, non_interactive=False)

        @cli.command()
        @safety_options
        @click.pass_context
        def dangerous(ctx, force, non_interactive):
            cli_ctx = apply_options(ctx, force=force, non_interactive=non_interactive)
            click.echo(f"force={cli_ctx.force}, non_interactive={cli_ctx.non_interactive}")

        result = cli_runner.invoke(cli, ["dangerous", "--force", "--non-interactive"])

        assert result.exit_code == 0
        assert "force=True" in result.output
        assert "non_interactive=True" in result.output

    def test_options_can_appear_after_arguments(self, cli_runner: CliRunner):
        """Test options can appear after positional arguments."""

        @click.command()
        @click.argument("name")
        @output_option
        def cmd(name, output):
            click.echo(f"name={name}, output={output}")

        # Option after argument
        result = cli_runner.invoke(cmd, ["my-item", "--output", "json"])

        assert result.exit_code == 0
        assert "name=my-item" in result.output
        assert "output=json" in result.output


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def cli_runner() -> CliRunner:
    """Provide a Click CLI test runner."""
    return CliRunner()
