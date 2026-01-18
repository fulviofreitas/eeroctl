"""Unit tests for eeroctl.commands.completion module.

Tests cover:
- completion bash command
- completion zsh command
- completion fish command
"""

import pytest
from click.testing import CliRunner

from eeroctl.main import cli


class TestCompletionGroup:
    """Tests for the completion command group."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_completion_help(self, runner):
        """Test completion group shows help."""
        result = runner.invoke(cli, ["completion", "--help"])

        assert result.exit_code == 0
        assert "Generate shell completion" in result.output
        assert "bash" in result.output
        assert "zsh" in result.output
        assert "fish" in result.output


class TestCompletionBash:
    """Tests for completion bash command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_completion_bash_help(self, runner):
        """Test completion bash shows help."""
        result = runner.invoke(cli, ["completion", "bash", "--help"])

        assert result.exit_code == 0
        assert "Generate bash completion" in result.output

    def test_completion_bash_generates_script(self, runner):
        """Test completion bash generates a valid script."""
        result = runner.invoke(cli, ["completion", "bash"])

        assert result.exit_code == 0
        # Verify it outputs bash completion script elements
        assert "_eero_completion" in result.output
        assert "COMPREPLY" in result.output
        assert "complete" in result.output


class TestCompletionZsh:
    """Tests for completion zsh command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_completion_zsh_help(self, runner):
        """Test completion zsh shows help."""
        result = runner.invoke(cli, ["completion", "zsh", "--help"])

        assert result.exit_code == 0
        assert "Generate zsh completion" in result.output

    def test_completion_zsh_generates_script(self, runner):
        """Test completion zsh generates a valid script."""
        result = runner.invoke(cli, ["completion", "zsh"])

        assert result.exit_code == 0
        # Verify it outputs zsh completion script elements
        assert "#compdef" in result.output
        assert "_eero" in result.output
        assert "compdef" in result.output


class TestCompletionFish:
    """Tests for completion fish command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_completion_fish_help(self, runner):
        """Test completion fish shows help."""
        result = runner.invoke(cli, ["completion", "fish", "--help"])

        assert result.exit_code == 0
        assert "Generate fish completion" in result.output

    def test_completion_fish_generates_script(self, runner):
        """Test completion fish generates a valid script."""
        result = runner.invoke(cli, ["completion", "fish"])

        assert result.exit_code == 0
        # Verify it outputs fish completion script elements
        assert "_eero_completion" in result.output
        assert "complete" in result.output
        assert "eero" in result.output
