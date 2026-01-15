"""Unit tests for eero.cli.safety module.

Tests cover:
- SafetyContext dataclass
- SafetyError exception
- OperationRisk enum
- require_confirmation function
- confirm_or_fail convenience function
- requires_confirmation decorator
"""

from unittest.mock import MagicMock, patch

import pytest

from eero_cli.exit_codes import ExitCode
from eero_cli.safety import (
    OPERATION_RISKS,
    OperationRisk,
    SafetyContext,
    SafetyError,
    confirm_or_fail,
    require_confirmation,
    requires_confirmation,
)

# ========================== OperationRisk Tests ==========================


class TestOperationRisk:
    """Tests for OperationRisk enum."""

    def test_low_risk_value(self):
        """Test LOW risk has correct value."""
        assert OperationRisk.LOW == "low"

    def test_medium_risk_value(self):
        """Test MEDIUM risk has correct value."""
        assert OperationRisk.MEDIUM == "medium"

    def test_high_risk_value(self):
        """Test HIGH risk has correct value."""
        assert OperationRisk.HIGH == "high"

    def test_risks_are_strings(self):
        """Test all risks are string enums."""
        for risk in OperationRisk:
            assert isinstance(risk.value, str)


# ========================== SafetyContext Tests ==========================


class TestSafetyContext:
    """Tests for SafetyContext dataclass."""

    def test_default_values(self):
        """Test SafetyContext has correct defaults."""
        ctx = SafetyContext()

        assert ctx.force is False
        assert ctx.non_interactive is False
        assert ctx.dry_run is False

    def test_custom_values(self):
        """Test SafetyContext accepts custom values."""
        ctx = SafetyContext(
            force=True,
            non_interactive=True,
            dry_run=True,
        )

        assert ctx.force is True
        assert ctx.non_interactive is True
        assert ctx.dry_run is True


# ========================== SafetyError Tests ==========================


class TestSafetyError:
    """Tests for SafetyError exception."""

    def test_message_and_exit_code(self):
        """Test SafetyError stores message and exit code."""
        error = SafetyError("Operation cancelled", ExitCode.SAFETY_RAIL)

        assert error.message == "Operation cancelled"
        assert error.exit_code == ExitCode.SAFETY_RAIL

    def test_default_exit_code(self):
        """Test SafetyError uses SAFETY_RAIL as default exit code."""
        error = SafetyError("Cancelled")

        assert error.exit_code == ExitCode.SAFETY_RAIL

    def test_is_exception(self):
        """Test SafetyError is an Exception."""
        error = SafetyError("Test")

        assert isinstance(error, Exception)

        with pytest.raises(SafetyError):
            raise error


# ========================== require_confirmation Tests ==========================


class TestRequireConfirmation:
    """Tests for require_confirmation function."""

    @pytest.fixture
    def mock_console(self) -> MagicMock:
        """Create a mock console."""
        console = MagicMock()
        console.print = MagicMock()
        return console

    def test_dry_run_returns_false(self, mock_console):
        """Test dry run always returns False and prints message."""
        ctx = SafetyContext(dry_run=True)

        result = require_confirmation(
            action="reboot",
            target="Living Room",
            risk=OperationRisk.MEDIUM,
            ctx=ctx,
            console=mock_console,
        )

        assert result is False
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        assert "DRY RUN" in call_args

    def test_force_bypasses_confirmation(self, mock_console):
        """Test force flag bypasses all confirmations."""
        ctx = SafetyContext(force=True)

        result = require_confirmation(
            action="factory reset",
            target="network",
            risk=OperationRisk.HIGH,
            ctx=ctx,
            console=mock_console,
        )

        assert result is True
        # Should not print anything
        mock_console.print.assert_not_called()

    def test_low_risk_no_confirmation_needed(self, mock_console):
        """Test LOW risk operations proceed without confirmation."""
        ctx = SafetyContext()

        result = require_confirmation(
            action="rename",
            target="device",
            risk=OperationRisk.LOW,
            ctx=ctx,
            console=mock_console,
        )

        assert result is True
        mock_console.print.assert_not_called()

    def test_non_interactive_without_force_raises(self, mock_console):
        """Test non-interactive mode without force raises SafetyError."""
        ctx = SafetyContext(non_interactive=True, force=False)

        with pytest.raises(SafetyError) as exc_info:
            require_confirmation(
                action="reboot",
                target="eero",
                risk=OperationRisk.MEDIUM,
                ctx=ctx,
                console=mock_console,
            )

        assert exc_info.value.exit_code == ExitCode.SAFETY_RAIL
        assert "--force" in exc_info.value.message

    @patch("eero.cli.safety.Confirm.ask")
    def test_medium_risk_prompts_user(self, mock_confirm, mock_console):
        """Test MEDIUM risk prompts for Y/N confirmation."""
        mock_confirm.return_value = True
        ctx = SafetyContext()

        result = require_confirmation(
            action="reboot",
            target="Living Room eero",
            risk=OperationRisk.MEDIUM,
            ctx=ctx,
            console=mock_console,
        )

        assert result is True
        mock_confirm.assert_called_once()

    @patch("eero.cli.safety.Confirm.ask")
    def test_medium_risk_user_declines(self, mock_confirm, mock_console):
        """Test MEDIUM risk raises when user declines."""
        mock_confirm.return_value = False
        ctx = SafetyContext()

        with pytest.raises(SafetyError) as exc_info:
            require_confirmation(
                action="reboot",
                target="eero",
                risk=OperationRisk.MEDIUM,
                ctx=ctx,
                console=mock_console,
            )

        assert "cancelled" in exc_info.value.message.lower()

    @patch("eero.cli.safety.Prompt.ask")
    def test_high_risk_requires_typed_confirmation(self, mock_prompt, mock_console):
        """Test HIGH risk requires typed confirmation phrase."""
        mock_prompt.return_value = "FACTORYRESET"
        ctx = SafetyContext()

        result = require_confirmation(
            action="factory reset",
            target="network",
            risk=OperationRisk.HIGH,
            confirmation_phrase="FACTORYRESET",
            ctx=ctx,
            console=mock_console,
        )

        assert result is True
        mock_prompt.assert_called_once()

    @patch("eero.cli.safety.Prompt.ask")
    def test_high_risk_wrong_phrase_raises(self, mock_prompt, mock_console):
        """Test HIGH risk raises when phrase doesn't match."""
        mock_prompt.return_value = "wrong"
        ctx = SafetyContext()

        with pytest.raises(SafetyError) as exc_info:
            require_confirmation(
                action="factory reset",
                target="network",
                risk=OperationRisk.HIGH,
                confirmation_phrase="FACTORYRESET",
                ctx=ctx,
                console=mock_console,
            )

        assert "mismatch" in exc_info.value.message.lower()

    @patch("eero.cli.safety.Prompt.ask")
    def test_high_risk_auto_generates_phrase(self, mock_prompt, mock_console):
        """Test HIGH risk auto-generates confirmation phrase if not provided."""
        # Action is "factory reset" -> phrase becomes "FACTORYRESET"
        mock_prompt.return_value = "FACTORYRESET"
        ctx = SafetyContext()

        result = require_confirmation(
            action="factory reset",
            target="network",
            risk=OperationRisk.HIGH,
            # No confirmation_phrase provided
            ctx=ctx,
            console=mock_console,
        )

        assert result is True

    def test_default_context_creation(self):
        """Test function creates default context if none provided."""
        # This should not raise - it creates a default SafetyContext
        result = require_confirmation(
            action="rename",
            target="device",
            risk=OperationRisk.LOW,
        )

        assert result is True


# ========================== confirm_or_fail Tests ==========================


class TestConfirmOrFail:
    """Tests for confirm_or_fail convenience function."""

    def test_force_returns_true(self):
        """Test force=True returns True immediately."""
        result = confirm_or_fail(
            action="reboot",
            target="eero",
            risk=OperationRisk.MEDIUM,
            force=True,
        )

        assert result is True

    def test_dry_run_returns_false(self):
        """Test dry_run=True returns False."""
        result = confirm_or_fail(
            action="reboot",
            target="eero",
            risk=OperationRisk.MEDIUM,
            dry_run=True,
        )

        assert result is False

    def test_non_interactive_raises_without_force(self):
        """Test non_interactive without force raises SafetyError."""
        with pytest.raises(SafetyError):
            confirm_or_fail(
                action="reboot",
                target="eero",
                risk=OperationRisk.MEDIUM,
                non_interactive=True,
                force=False,
            )

    def test_low_risk_always_passes(self):
        """Test LOW risk always returns True."""
        result = confirm_or_fail(
            action="view",
            target="settings",
            risk=OperationRisk.LOW,
        )

        assert result is True


# ========================== requires_confirmation Decorator Tests ==========================


class TestRequiresConfirmationDecorator:
    """Tests for requires_confirmation decorator."""

    def test_decorator_passes_with_force(self):
        """Test decorated function executes when force=True."""
        executed = []

        @requires_confirmation("test action", risk=OperationRisk.MEDIUM)
        def test_func(target, force=False):
            executed.append(target)
            return "success"

        result = test_func(target="test", force=True)

        assert result == "success"
        assert executed == ["test"]

    def test_decorator_with_low_risk(self):
        """Test decorated function executes for LOW risk."""
        executed = []

        @requires_confirmation("view", risk=OperationRisk.LOW)
        def view_func(target):
            executed.append(target)
            return "viewed"

        result = view_func(target="item")

        assert result == "viewed"
        assert executed == ["item"]

    def test_decorator_preserves_function_name(self):
        """Test decorator preserves function name."""

        @requires_confirmation("test", risk=OperationRisk.LOW)
        def my_special_function():
            pass

        assert my_special_function.__name__ == "my_special_function"

    def test_decorator_preserves_docstring(self):
        """Test decorator preserves docstring."""

        @requires_confirmation("test", risk=OperationRisk.LOW)
        def documented_function():
            """This is documentation."""
            pass

        assert documented_function.__doc__ == """This is documentation."""


# ========================== OPERATION_RISKS Mapping Tests ==========================


class TestOperationRisks:
    """Tests for OPERATION_RISKS constant mapping."""

    def test_high_risk_operations(self):
        """Test HIGH risk operations are correctly mapped."""
        high_risk_ops = ["reboot_network", "change_wifi_password", "factory_reset"]

        for op in high_risk_ops:
            assert op in OPERATION_RISKS
            assert OPERATION_RISKS[op] == OperationRisk.HIGH

    def test_medium_risk_operations(self):
        """Test MEDIUM risk operations are correctly mapped."""
        medium_risk_ops = [
            "reboot_eero",
            "guest_enable",
            "block_device",
            "pause_profile",
        ]

        for op in medium_risk_ops:
            assert op in OPERATION_RISKS
            assert OPERATION_RISKS[op] == OperationRisk.MEDIUM

    def test_low_risk_operations(self):
        """Test LOW risk operations are correctly mapped."""
        low_risk_ops = ["rename_device", "view_any"]

        for op in low_risk_ops:
            assert op in OPERATION_RISKS
            assert OPERATION_RISKS[op] == OperationRisk.LOW

    def test_all_risks_are_valid(self):
        """Test all mapped risks are valid OperationRisk values."""
        for op, risk in OPERATION_RISKS.items():
            assert isinstance(risk, OperationRisk), f"Invalid risk for {op}"
