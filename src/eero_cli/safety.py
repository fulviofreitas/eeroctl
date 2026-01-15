"""Safety middleware for the Eero CLI.

Handles confirmation prompts for destructive/disruptive operations.
Provides consistent safety behavior across all mutating commands.
"""

import sys
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

import click
from rich.console import Console
from rich.prompt import Confirm, Prompt

from .exit_codes import ExitCode


class OperationRisk(str, Enum):
    """Risk level of an operation."""

    LOW = "low"
    """Low risk - no confirmation needed."""

    MEDIUM = "medium"
    """Medium risk - simple Y/N confirmation."""

    HIGH = "high"
    """High risk - requires typed confirmation phrase."""


@dataclass
class SafetyContext:
    """Context for safety checks."""

    force: bool = False
    """Whether --force was specified."""

    non_interactive: bool = False
    """Whether --non-interactive was specified."""

    dry_run: bool = False
    """Whether --dry-run was specified."""


class SafetyError(Exception):
    """Raised when a safety check fails."""

    def __init__(self, message: str, exit_code: int = ExitCode.SAFETY_RAIL):
        self.message = message
        self.exit_code = exit_code
        super().__init__(message)


def require_confirmation(
    action: str,
    target: str,
    risk: OperationRisk = OperationRisk.MEDIUM,
    confirmation_phrase: Optional[str] = None,
    ctx: Optional[SafetyContext] = None,
    console: Optional[Console] = None,
) -> bool:
    """Check if operation should proceed based on safety settings.

    Args:
        action: Description of the action (e.g., "reboot")
        target: Target of the action (e.g., "Living Room eero")
        risk: Risk level of the operation
        confirmation_phrase: Required phrase for HIGH risk operations
        ctx: Safety context with force/non_interactive flags
        console: Rich console for prompts

    Returns:
        True if operation should proceed

    Raises:
        SafetyError: If safety check fails and operation should not proceed
    """
    if ctx is None:
        ctx = SafetyContext()

    if console is None:
        console = Console(stderr=True)

    # Dry run always prints and returns False
    if ctx.dry_run:
        console.print(f"[yellow]DRY RUN:[/yellow] Would {action} {target}")
        return False

    # Force bypasses all confirmations
    if ctx.force:
        return True

    # Low risk operations proceed without confirmation
    if risk == OperationRisk.LOW:
        return True

    # Non-interactive mode without force fails
    if ctx.non_interactive:
        raise SafetyError(
            f"Operation '{action}' on '{target}' requires confirmation. "
            "Use --force to proceed in non-interactive mode.",
            exit_code=ExitCode.SAFETY_RAIL,
        )

    # Interactive confirmation
    if risk == OperationRisk.HIGH:
        # High risk requires typed phrase
        if confirmation_phrase is None:
            confirmation_phrase = action.upper().replace(" ", "")

        console.print(
            f"\n[bold yellow]⚠ Warning:[/bold yellow] You are about to {action} {target}."
        )
        console.print(
            "[dim]This is a high-impact operation that may cause service disruption.[/dim]"
        )
        console.print(f"\nTo confirm, type [bold]{confirmation_phrase}[/bold] and press Enter:")

        user_input = Prompt.ask("Confirmation", console=console)

        if user_input != confirmation_phrase:
            raise SafetyError(
                f"Confirmation phrase mismatch. Expected '{confirmation_phrase}'.",
                exit_code=ExitCode.SAFETY_RAIL,
            )
        return True

    else:
        # Medium risk - simple Y/N
        console.print(f"\n[bold]Proceed with {action} on {target}?[/bold]")
        confirmed = Confirm.ask("Continue", default=False, console=console)

        if not confirmed:
            raise SafetyError(
                "Operation cancelled by user.",
                exit_code=ExitCode.SAFETY_RAIL,
            )
        return True


def confirm_or_fail(
    action: str,
    target: str,
    risk: OperationRisk = OperationRisk.MEDIUM,
    confirmation_phrase: Optional[str] = None,
    force: bool = False,
    non_interactive: bool = False,
    dry_run: bool = False,
    console: Optional[Console] = None,
) -> bool:
    """Convenience function combining context creation and confirmation.

    Args:
        action: Description of the action
        target: Target of the action
        risk: Risk level
        confirmation_phrase: Required phrase for HIGH risk
        force: --force flag value
        non_interactive: --non-interactive flag value
        dry_run: --dry-run flag value
        console: Rich console for prompts

    Returns:
        True if operation should proceed

    Raises:
        SafetyError: If safety check fails
    """
    ctx = SafetyContext(force=force, non_interactive=non_interactive, dry_run=dry_run)
    return require_confirmation(
        action=action,
        target=target,
        risk=risk,
        confirmation_phrase=confirmation_phrase,
        ctx=ctx,
        console=console,
    )


# Decorator for commands that require confirmation
def requires_confirmation(
    action: str,
    target_param: str = "target",
    risk: OperationRisk = OperationRisk.MEDIUM,
    confirmation_phrase: Optional[str] = None,
):
    """Decorator to add confirmation requirement to a command.

    Args:
        action: Description of the action
        target_param: Name of the parameter containing the target
        risk: Risk level of the operation
        confirmation_phrase: Required phrase for HIGH risk

    Example:
        @requires_confirmation("reboot", target_param="eero_id", risk=OperationRisk.MEDIUM)
        def reboot(ctx, eero_id: str, force: bool, non_interactive: bool, dry_run: bool):
            ...
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            # Extract safety-related kwargs
            force = kwargs.get("force", False)
            non_interactive = kwargs.get("non_interactive", False)
            dry_run = kwargs.get("dry_run", False)
            target = kwargs.get(target_param, "unknown")

            try:
                if confirm_or_fail(
                    action=action,
                    target=str(target),
                    risk=risk,
                    confirmation_phrase=confirmation_phrase,
                    force=force,
                    non_interactive=non_interactive,
                    dry_run=dry_run,
                ):
                    return func(*args, **kwargs)
            except SafetyError as e:
                click.echo(f"Error: {e.message}", err=True)
                sys.exit(e.exit_code)

        # Preserve function metadata
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator


# List of operations and their risk levels for reference
OPERATION_RISKS = {
    # HIGH risk - requires typed confirmation
    "reboot_network": OperationRisk.HIGH,
    "change_wifi_password": OperationRisk.HIGH,
    "change_wifi_ssid": OperationRisk.HIGH,
    "factory_reset": OperationRisk.HIGH,
    # MEDIUM risk - Y/N confirmation
    "reboot_eero": OperationRisk.MEDIUM,
    "guest_enable": OperationRisk.MEDIUM,
    "guest_disable": OperationRisk.MEDIUM,
    "dns_change": OperationRisk.MEDIUM,
    "security_change": OperationRisk.MEDIUM,
    "sqm_change": OperationRisk.MEDIUM,
    "block_device": OperationRisk.MEDIUM,
    "unblock_device": OperationRisk.MEDIUM,
    "pause_profile": OperationRisk.MEDIUM,
    "unpause_profile": OperationRisk.MEDIUM,
    "schedule_change": OperationRisk.MEDIUM,
    "delete_forward": OperationRisk.MEDIUM,
    "delete_reservation": OperationRisk.MEDIUM,
    "export_support_bundle": OperationRisk.MEDIUM,
    # LOW risk - no confirmation
    "rename_device": OperationRisk.LOW,
    "rename_network": OperationRisk.LOW,  # Actually shown as MEDIUM in spec
    "view_any": OperationRisk.LOW,
}
