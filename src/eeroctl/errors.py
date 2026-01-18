"""Centralized error handling for the Eero CLI.

This module provides utilities for translating exceptions to user-friendly
error messages and appropriate exit codes.
"""

from typing import Optional, TypeVar

from eero.exceptions import (
    EeroAPIException,
    EeroAuthenticationException,
    EeroException,
    EeroFeatureUnavailableException,
    EeroNotFoundException,
    EeroPremiumRequiredException,
    EeroRateLimitException,
    EeroTimeoutException,
    EeroValidationException,
)
from rich.console import Console

from .exit_codes import ExitCode

T = TypeVar("T")


def handle_cli_error(
    e: Exception,
    console: Console,
    renderer: Optional[object] = None,
    context: str = "",
) -> int:
    """Handle an exception and return the appropriate exit code.

    This function translates exceptions into user-friendly error messages
    and determines the correct exit code.

    Args:
        e: The exception to handle
        console: Rich console for output
        renderer: Optional OutputRenderer for JSON output
        context: Optional context string for better error messages

    Returns:
        The exit code to use
    """
    prefix = f"{context}: " if context else ""

    if isinstance(e, EeroAuthenticationException):
        console.print(f"[red]{prefix}Authentication required. Run 'eero auth login' first.[/red]")
        return ExitCode.AUTH_REQUIRED

    elif isinstance(e, EeroNotFoundException):
        console.print(f"[red]{prefix}{e.resource_type} '{e.resource_id}' not found[/red]")
        return ExitCode.NOT_FOUND

    elif isinstance(e, EeroPremiumRequiredException):
        console.print(f"[yellow]{prefix}{e.feature} requires Eero Plus subscription[/yellow]")
        return ExitCode.PREMIUM_REQUIRED

    elif isinstance(e, EeroFeatureUnavailableException):
        console.print(f"[yellow]{prefix}{e.feature} is {e.reason}[/yellow]")
        return ExitCode.FEATURE_UNAVAILABLE

    elif isinstance(e, EeroRateLimitException):
        console.print(f"[yellow]{prefix}Rate limited. Please wait and try again.[/yellow]")
        return ExitCode.TIMEOUT

    elif isinstance(e, EeroTimeoutException):
        console.print(f"[red]{prefix}Request timed out. Check your connection and try again.[/red]")
        return ExitCode.TIMEOUT

    elif isinstance(e, EeroValidationException):
        console.print(f"[red]{prefix}Invalid input for '{e.field}': {e.message}[/red]")
        return ExitCode.USAGE_ERROR

    elif isinstance(e, EeroAPIException):
        # Map HTTP status codes to exit codes
        if e.status_code == 401:
            console.print(
                f"[red]{prefix}Session expired. Run 'eero auth login' to re-authenticate.[/red]"
            )
            return ExitCode.AUTH_REQUIRED
        elif e.status_code == 403:
            console.print(f"[red]{prefix}Permission denied: {e.message}[/red]")
            return ExitCode.FORBIDDEN
        elif e.status_code == 404:
            console.print(f"[red]{prefix}Resource not found: {e.message}[/red]")
            return ExitCode.NOT_FOUND
        elif e.status_code == 409:
            console.print(f"[yellow]{prefix}Conflict: {e.message}[/yellow]")
            return ExitCode.CONFLICT
        elif e.status_code == 429:
            console.print(f"[yellow]{prefix}Rate limited. Please wait and try again.[/yellow]")
            return ExitCode.TIMEOUT
        else:
            console.print(f"[red]{prefix}API error ({e.status_code}): {e.message}[/red]")
            return ExitCode.GENERIC_ERROR

    elif isinstance(e, EeroException):
        # Generic Eero exception
        console.print(f"[red]{prefix}{e.message}[/red]")
        return ExitCode.GENERIC_ERROR

    else:
        # Unknown exception
        console.print(f"[red]{prefix}Unexpected error: {e}[/red]")
        return ExitCode.GENERIC_ERROR


def is_premium_error(e: Exception) -> bool:
    """Check if an exception indicates a premium feature requirement.

    Args:
        e: Exception to check

    Returns:
        True if this is a premium-required error
    """
    if isinstance(e, EeroPremiumRequiredException):
        return True
    # Fallback string matching for generic exceptions
    error_str = str(e).lower()
    return "premium" in error_str or "plus" in error_str or "subscription" in error_str


def is_feature_unavailable_error(e: Exception, feature_keyword: str) -> bool:
    """Check if an exception indicates a feature is unavailable.

    Args:
        e: Exception to check
        feature_keyword: Keyword to look for in error message

    Returns:
        True if this is a feature-unavailable error
    """
    if isinstance(e, EeroFeatureUnavailableException):
        return True
    # Fallback string matching for generic exceptions
    return feature_keyword.lower() in str(e).lower()


def is_not_found_error(e: Exception) -> bool:
    """Check if an exception indicates a resource was not found.

    Args:
        e: Exception to check

    Returns:
        True if this is a not-found error
    """
    if isinstance(e, EeroNotFoundException):
        return True
    if isinstance(e, EeroAPIException) and e.status_code == 404:
        return True
    return "not found" in str(e).lower()
