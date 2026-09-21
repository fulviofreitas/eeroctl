"""Centralized error handling for the Eero CLI.

This module provides utilities for translating exceptions to user-friendly
error messages and appropriate exit codes.
"""

from typing import Optional, TypeVar

from eero.exceptions import (
    EeroAccessDeniedException,
    EeroAPIException,
    EeroAuthenticationException,
    EeroClientBlockedException,
    EeroException,
    EeroFeatureUnavailableException,
    EeroNetworkException,
    EeroNotFoundException,
    EeroPremiumRequiredException,
    EeroRateLimitException,
    EeroTimeoutException,
    EeroValidationException,
)
from rich.console import Console

from .exit_codes import ExitCode

T = TypeVar("T")


def _error_code_suffix(e: EeroException) -> str:
    """Build the ``(error code: ...)`` suffix for a rendered SDK error.

    Every v8 exception carries ``.error_code`` (``envelope["meta"]["error"]``),
    populated only when the API response included one. Never render
    ``e.envelope`` itself — it can carry ``user_token``, emails, phones.
    """
    return f" (error code: {e.error_code})" if e.error_code else ""


def handle_cli_error(
    e: Exception,
    console: Console,
    renderer: Optional[object] = None,
    context: str = "",
) -> int:
    """Handle an exception and return the appropriate exit code.

    This function translates exceptions into user-friendly error messages
    and determines the correct exit code.

    isinstance order matters: every SDK exception that subclasses another
    (``EeroAccessDeniedException``, ``EeroClientBlockedException``,
    ``EeroNotFoundException``, ``EeroPremiumRequiredException``,
    ``EeroFeatureUnavailableException`` all subclass ``EeroAPIException``;
    ``EeroValidationException`` does not) is checked before its parent, so
    the parent's branch never shadows it.

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

    elif isinstance(e, EeroAccessDeniedException):
        console.print(f"[red]{prefix}Permission denied: {e.message}{_error_code_suffix(e)}[/red]")
        return ExitCode.FORBIDDEN

    elif isinstance(e, EeroClientBlockedException):
        console.print(
            f"[red]{prefix}This client version is blocked by the API: "
            f"{e.message}{_error_code_suffix(e)}[/red]"
        )
        return ExitCode.CLIENT_BLOCKED

    elif isinstance(e, EeroNotFoundException):
        if e.resource_type is not None or e.resource_id is not None:
            console.print(
                f"[red]{prefix}{e.resource_type} '{e.resource_id}' "
                f"not found{_error_code_suffix(e)}[/red]"
            )
        else:
            # Built via `from_response` (no known resource type/ID): the
            # message is already a complete, human-readable sentence.
            console.print(f"[red]{prefix}{e.message}{_error_code_suffix(e)}[/red]")
        return ExitCode.NOT_FOUND

    elif isinstance(e, EeroPremiumRequiredException):
        console.print(
            f"[yellow]{prefix}{e.feature} requires Eero Plus "
            f"subscription{_error_code_suffix(e)}[/yellow]"
        )
        return ExitCode.PREMIUM_REQUIRED

    elif isinstance(e, EeroFeatureUnavailableException):
        console.print(f"[yellow]{prefix}{e.feature} is {e.reason}{_error_code_suffix(e)}[/yellow]")
        return ExitCode.FEATURE_UNAVAILABLE

    elif isinstance(e, EeroRateLimitException):
        # No dedicated exit code for rate limiting (§2.6/Q5 of the v8
        # migration plan: exit 7 stays TIMEOUT-only); falls to GENERIC_ERROR.
        console.print(
            f"[yellow]{prefix}Rate limited. Please wait and "
            f"try again.{_error_code_suffix(e)}[/yellow]"
        )
        return ExitCode.GENERIC_ERROR

    elif isinstance(e, EeroNetworkException):
        console.print(
            f"[red]{prefix}Network error: could not reach the eero API{_error_code_suffix(e)}[/red]"
        )
        return ExitCode.NETWORK_ERROR

    elif isinstance(e, EeroTimeoutException):
        console.print(
            f"[red]{prefix}Request timed out. Check your connection and "
            f"try again.{_error_code_suffix(e)}[/red]"
        )
        return ExitCode.TIMEOUT

    elif isinstance(e, EeroValidationException):
        if e.field == "request":
            # Built via `from_response`: `e.message` is already
            # "Validation error for 'request': <detail>"; render the
            # detail without the generic field-name wrapper.
            prefix_text = "Validation error for 'request': "
            detail = (
                e.message[len(prefix_text) :] if e.message.startswith(prefix_text) else (e.message)
            )
            console.print(f"[red]{prefix}Invalid request: {detail}{_error_code_suffix(e)}[/red]")
        else:
            console.print(
                f"[red]{prefix}Invalid input for '{e.field}': "
                f"{e.message}{_error_code_suffix(e)}[/red]"
            )
        return ExitCode.USAGE_ERROR

    elif isinstance(e, EeroAPIException):
        # Fallback for statuses not covered by a dedicated exception class
        # above (403-without-access-denied, 404-without-from_response, 409,
        # and any other status).
        if e.status_code == 401:
            console.print(
                f"[red]{prefix}Session expired. Run 'eero auth login' to "
                f"re-authenticate.{_error_code_suffix(e)}[/red]"
            )
            return ExitCode.AUTH_REQUIRED
        elif e.status_code == 403:
            console.print(
                f"[red]{prefix}Permission denied: {e.message}{_error_code_suffix(e)}[/red]"
            )
            return ExitCode.FORBIDDEN
        elif e.status_code == 404:
            console.print(
                f"[red]{prefix}Resource not found: {e.message}{_error_code_suffix(e)}[/red]"
            )
            return ExitCode.NOT_FOUND
        elif e.status_code == 409:
            console.print(f"[yellow]{prefix}Conflict: {e.message}{_error_code_suffix(e)}[/yellow]")
            return ExitCode.CONFLICT
        else:
            # Includes an unmapped 429 (Q5: no dedicated rate-limit code).
            console.print(
                f"[red]{prefix}API error ({e.status_code}): "
                f"{e.message}{_error_code_suffix(e)}[/red]"
            )
            return ExitCode.GENERIC_ERROR

    elif isinstance(e, EeroException):
        # Generic Eero exception
        console.print(f"[red]{prefix}{e.message}{_error_code_suffix(e)}[/red]")
        return ExitCode.GENERIC_ERROR

    else:
        # Unknown exception
        console.print(f"[red]{prefix}Unexpected error: {e}[/red]")
        return ExitCode.GENERIC_ERROR
