"""Centralized error handling for the Eero CLI.

This module provides utilities for translating exceptions to user-friendly
error messages and appropriate exit codes.
"""

from typing import Any, Callable, Optional, TypeVar

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
from rich.markup import escape

from .exit_codes import ExitCode

T = TypeVar("T")

# A renderer takes (exception, context prefix) and returns (Rich-markup line, exit code).
_Renderer = Callable[[Any, str], tuple[str, ExitCode]]


def _error_code_suffix(e: EeroException) -> str:
    """Build the ``(error code: ...)`` suffix for a rendered SDK error.

    Every v8 exception carries ``.error_code`` (``envelope["meta"]["error"]``),
    populated only when the API response included one. Never render
    ``e.envelope`` itself — it can carry ``user_token``, emails, phones.

    ``error_code`` is API-supplied and gets interpolated into Rich markup by
    every caller, so it is escaped here rather than at each call site.
    """
    return f" (error code: {escape(e.error_code)})" if e.error_code else ""


def _render_authentication(e: EeroAuthenticationException, prefix: str) -> tuple[str, ExitCode]:
    """Render an authentication failure."""
    return (
        f"[red]{prefix}Authentication required. Run 'eero auth login' first.[/red]",
        ExitCode.AUTH_REQUIRED,
    )


def _render_access_denied(e: EeroAccessDeniedException, prefix: str) -> tuple[str, ExitCode]:
    """Render a permission-denied failure."""
    return (
        f"[red]{prefix}Permission denied: {escape(e.message)}{_error_code_suffix(e)}[/red]",
        ExitCode.FORBIDDEN,
    )


def _render_client_blocked(e: EeroClientBlockedException, prefix: str) -> tuple[str, ExitCode]:
    """Render a blocked-client-version failure."""
    return (
        f"[red]{prefix}This client version is blocked by the API: "
        f"{escape(e.message)}{_error_code_suffix(e)}[/red]",
        ExitCode.CLIENT_BLOCKED,
    )


def _render_not_found(e: EeroNotFoundException, prefix: str) -> tuple[str, ExitCode]:
    """Render a not-found failure."""
    if e.resource_type is not None or e.resource_id is not None:
        message = (
            f"[red]{prefix}{escape(str(e.resource_type))} "
            f"'{escape(str(e.resource_id))}' "
            f"not found{_error_code_suffix(e)}[/red]"
        )
    else:
        # Built via `from_response` (no known resource type/ID): the
        # message is already a complete, human-readable sentence.
        message = f"[red]{prefix}{escape(e.message)}{_error_code_suffix(e)}[/red]"
    return message, ExitCode.NOT_FOUND


def _render_premium_required(e: EeroPremiumRequiredException, prefix: str) -> tuple[str, ExitCode]:
    """Render an Eero Plus subscription requirement."""
    return (
        f"[yellow]{prefix}{escape(e.feature)} requires Eero Plus "
        f"subscription{_error_code_suffix(e)}[/yellow]",
        ExitCode.PREMIUM_REQUIRED,
    )


def _render_feature_unavailable(
    e: EeroFeatureUnavailableException, prefix: str
) -> tuple[str, ExitCode]:
    """Render a feature-unavailable failure."""
    return (
        f"[yellow]{prefix}{escape(e.feature)} is "
        f"{escape(e.reason)}{_error_code_suffix(e)}[/yellow]",
        ExitCode.FEATURE_UNAVAILABLE,
    )


def _render_rate_limit(e: EeroRateLimitException, prefix: str) -> tuple[str, ExitCode]:
    """Render a rate-limit failure."""
    # No dedicated exit code for rate limiting (§2.6/Q5 of the v8
    # migration plan: exit 7 stays TIMEOUT-only); falls to GENERIC_ERROR.
    return (
        f"[yellow]{prefix}Rate limited. Please wait and try again.{_error_code_suffix(e)}[/yellow]",
        ExitCode.GENERIC_ERROR,
    )


def _render_network(e: EeroNetworkException, prefix: str) -> tuple[str, ExitCode]:
    """Render a transport-level network failure."""
    return (
        f"[red]{prefix}Network error: could not reach the eero API{_error_code_suffix(e)}[/red]",
        ExitCode.NETWORK_ERROR,
    )


def _render_timeout(e: EeroTimeoutException, prefix: str) -> tuple[str, ExitCode]:
    """Render a request timeout."""
    return (
        f"[red]{prefix}Request timed out. Check your connection and "
        f"try again.{_error_code_suffix(e)}[/red]",
        ExitCode.TIMEOUT,
    )


def _render_validation(e: EeroValidationException, prefix: str) -> tuple[str, ExitCode]:
    """Render a validation failure."""
    if e.field == "request":
        # Built via `from_response`: `e.message` is already
        # "Validation error for 'request': <detail>"; render the
        # detail without the generic field-name wrapper.
        prefix_text = "Validation error for 'request': "
        detail = e.message[len(prefix_text) :] if e.message.startswith(prefix_text) else (e.message)
        message = f"[red]{prefix}Invalid request: {escape(detail)}{_error_code_suffix(e)}[/red]"
    else:
        message = (
            f"[red]{prefix}Invalid input for '{escape(e.field)}': "
            f"{escape(e.message)}{_error_code_suffix(e)}[/red]"
        )
    return message, ExitCode.USAGE_ERROR


def _render_api(e: EeroAPIException, prefix: str) -> tuple[str, ExitCode]:
    """Render an API error by status, for statuses with no dedicated exception class."""
    # Fallback for statuses not covered by a dedicated exception class
    # (403-without-access-denied, 404-without-from_response, 409, and any
    # other status).
    if e.status_code == 401:
        return (
            f"[red]{prefix}Session expired. Run 'eero auth login' to "
            f"re-authenticate.{_error_code_suffix(e)}[/red]",
            ExitCode.AUTH_REQUIRED,
        )
    if e.status_code == 403:
        return (
            f"[red]{prefix}Permission denied: {escape(e.message)}{_error_code_suffix(e)}[/red]",
            ExitCode.FORBIDDEN,
        )
    if e.status_code == 404:
        return (
            f"[red]{prefix}Resource not found: {escape(e.message)}{_error_code_suffix(e)}[/red]",
            ExitCode.NOT_FOUND,
        )
    if e.status_code == 409:
        return (
            f"[yellow]{prefix}Conflict: {escape(e.message)}{_error_code_suffix(e)}[/yellow]",
            ExitCode.CONFLICT,
        )
    # Includes an unmapped 429 (Q5: no dedicated rate-limit code).
    return (
        f"[red]{prefix}API error ({e.status_code}): "
        f"{escape(e.message)}{_error_code_suffix(e)}[/red]",
        ExitCode.GENERIC_ERROR,
    )


def _render_eero(e: EeroException, prefix: str) -> tuple[str, ExitCode]:
    """Render a generic SDK exception."""
    return (
        f"[red]{prefix}{escape(e.message)}{_error_code_suffix(e)}[/red]",
        ExitCode.GENERIC_ERROR,
    )


def _render_unknown(e: Exception, prefix: str) -> tuple[str, ExitCode]:
    """Render a non-SDK exception."""
    return f"[red]{prefix}Unexpected error: {escape(str(e))}[/red]", ExitCode.GENERIC_ERROR


# Checked with isinstance in order, so every subclass precedes its parent:
# the five EeroAPIException subclasses come before EeroAPIException, and
# every SDK class before EeroException, so a parent never shadows a child.
_RENDERERS: list[tuple[type[Exception], _Renderer]] = [
    (EeroAuthenticationException, _render_authentication),
    (EeroAccessDeniedException, _render_access_denied),
    (EeroClientBlockedException, _render_client_blocked),
    (EeroNotFoundException, _render_not_found),
    (EeroPremiumRequiredException, _render_premium_required),
    (EeroFeatureUnavailableException, _render_feature_unavailable),
    (EeroRateLimitException, _render_rate_limit),
    (EeroNetworkException, _render_network),
    (EeroTimeoutException, _render_timeout),
    (EeroValidationException, _render_validation),
    (EeroAPIException, _render_api),
    (EeroException, _render_eero),
]


def handle_cli_error(
    e: Exception,
    console: Console,
    renderer: Optional[object] = None,
    context: str = "",
) -> int:
    """Handle an exception and return the appropriate exit code.

    This function translates exceptions into user-friendly error messages
    and determines the correct exit code.

    ``_RENDERERS`` is walked in order: every SDK exception that subclasses
    another (``EeroAccessDeniedException``, ``EeroClientBlockedException``,
    ``EeroNotFoundException``, ``EeroPremiumRequiredException``,
    ``EeroFeatureUnavailableException`` all subclass ``EeroAPIException``;
    ``EeroValidationException`` does not) is checked before its parent, so
    the parent's renderer never shadows it.

    Every attribute drawn from the exception (``.message``, ``.error_code``,
    ``.resource_type``/``.resource_id``, ``.feature``, ``.reason``,
    ``.field``, the validation detail) can contain arbitrary API-supplied
    text and is interpolated into a Rich-markup string; each one is passed
    through :func:`rich.markup.escape` before interpolation so a stray ``[``
    in a server response renders literally instead of raising
    ``rich.errors.MarkupError`` or garbling the line. Only the literal
    ``[red]``/``[yellow]``/``[/red]``/``[/yellow]`` tags the renderers write
    themselves are left unescaped.

    Args:
        e: The exception to handle
        console: Rich console for output
        renderer: Optional OutputRenderer for JSON output
        context: Optional context string for better error messages

    Returns:
        The exit code to use
    """
    prefix = f"{context}: " if context else ""
    render: _Renderer = _render_unknown
    for exc_type, candidate in _RENDERERS:
        if isinstance(e, exc_type):
            render = candidate
            break
    message, exit_code = render(e, prefix)
    console.print(message)
    return exit_code
