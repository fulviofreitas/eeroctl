"""Unit tests for eeroctl.errors module.

Tests cover:
- handle_cli_error for every exception in the v8 hierarchy (eero-api 8.0.1)
- The isinstance-order guarantees that keep a subclass from being shadowed
  by its parent's branch
- Negative tests proving the pre-v8 substring-matching fallbacks
  (is_premium_error / is_feature_unavailable_error / is_not_found_error,
  deleted in this commit) are gone: a generic EeroException whose message
  happens to contain "premium"/"beacon" must NOT be reclassified.
"""

from unittest.mock import MagicMock

import pytest
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

from eeroctl.errors import handle_cli_error
from eeroctl.exit_codes import ExitCode

# ========================== handle_cli_error Tests ==========================


class TestHandleCliError:
    """Tests for handle_cli_error function."""

    @pytest.fixture
    def console(self) -> MagicMock:
        """Create a mock console for testing."""
        return MagicMock(spec=Console)

    def test_authentication_exception(self, console):
        """Test handling of authentication exception."""
        exc = EeroAuthenticationException("Session expired")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.AUTH_REQUIRED
        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "Authentication required" in call_args

    def test_access_denied_exception(self, console, api_error):
        """EeroAccessDeniedException maps to FORBIDDEN, not the generic 403 path."""
        exc = api_error(EeroAccessDeniedException, 403, "error.access.denied")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.FORBIDDEN
        call_args = console.print.call_args[0][0]
        assert "Permission denied" in call_args
        assert "error.access.denied" in call_args

    def test_client_blocked_exception(self, console, api_error):
        """EeroClientBlockedException maps to the new CLIENT_BLOCKED (13)."""
        exc = api_error(EeroClientBlockedException, 400, "error.app.version.blocked")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.CLIENT_BLOCKED
        assert exit_code == 13
        call_args = console.print.call_args[0][0]
        assert "blocked" in call_args.lower()
        assert "error.app.version.blocked" in call_args

    def test_not_found_exception_direct_construction(self, console):
        """Test handling of a directly constructed not-found exception."""
        exc = EeroNotFoundException("Eero", "living_room")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.NOT_FOUND
        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "Eero" in call_args
        assert "living_room" in call_args

    def test_not_found_exception_from_response(self, console, api_error):
        """`from_response` (status 404, resource_type=None) renders without
        leaking a literal "None 'None'" placeholder."""
        exc = api_error(
            EeroNotFoundException,
            404,
            None,
            message="network-scoped path not found",
        )

        assert exc.resource_type is None
        assert exc.resource_id is None

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.NOT_FOUND
        call_args = console.print.call_args[0][0]
        assert "None 'None'" not in call_args
        assert "network-scoped path not found" in call_args

    def test_premium_required_exception(self, console):
        """Test handling of premium required exception."""
        exc = EeroPremiumRequiredException("Content filtering")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.PREMIUM_REQUIRED
        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "Content filtering" in call_args
        assert "Plus" in call_args or "subscription" in call_args

    def test_feature_unavailable_exception(self, console):
        """Test handling of feature unavailable exception."""
        exc = EeroFeatureUnavailableException("Nightlight", "only on Beacon")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.FEATURE_UNAVAILABLE
        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "Nightlight" in call_args

    def test_premium_required_exception_from_response(self, console, api_error):
        """Envelope-only construction (transport has no per-feature context)
        still maps to PREMIUM_REQUIRED, with the generic feature label."""
        exc = api_error(
            EeroPremiumRequiredException,
            402,
            "error.premium.user_not_subscribed",
            message="premium plan required",
        )

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.PREMIUM_REQUIRED
        call_args = console.print.call_args[0][0]
        assert "error.premium.user_not_subscribed" in call_args

    def test_feature_unavailable_exception_from_response(self, console, api_error):
        """Envelope-only construction still maps to FEATURE_UNAVAILABLE."""
        exc = api_error(
            EeroFeatureUnavailableException,
            400,
            "error.eero.offline",
            message="eero is offline",
        )

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.FEATURE_UNAVAILABLE
        call_args = console.print.call_args[0][0]
        assert "error.eero.offline" in call_args

    def test_client_blocked_not_shadowed_by_generic_api_exception_branch(self, console, api_error):
        """A 400-status EeroClientBlockedException must still resolve to
        CLIENT_BLOCKED (13), not fall through to the generic EeroAPIException
        else-branch (GENERIC_ERROR) just because 400 has no dedicated case
        there. Proves the isinstance order, not the status code, decides."""
        exc = api_error(EeroClientBlockedException, 400, "error.app.version.blocked")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.CLIENT_BLOCKED
        assert exit_code != ExitCode.GENERIC_ERROR

    def test_rate_limit_exception_maps_to_generic_error(self, console):
        """Q5 (decided): exit 7 stays TIMEOUT-only, so a rate limit has no
        dedicated code and falls to GENERIC_ERROR (1)."""
        exc = EeroRateLimitException("Too many requests")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.GENERIC_ERROR
        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "Rate limited" in call_args

    def test_network_exception(self, console):
        """EeroNetworkException maps to the new NETWORK_ERROR (14)."""
        exc = EeroNetworkException("Connection reset")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.NETWORK_ERROR
        assert exit_code == 14
        call_args = console.print.call_args[0][0]
        assert "Network error: could not reach the eero API" in call_args

    def test_timeout_exception(self, console):
        """Test handling of timeout exception."""
        exc = EeroTimeoutException("Request timed out")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.TIMEOUT
        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "timed out" in call_args

    def test_validation_exception_direct_construction(self, console):
        """Test handling of a directly constructed validation exception."""
        exc = EeroValidationException("password", "Must be at least 8 characters")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.USAGE_ERROR
        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "password" in call_args

    def test_validation_exception_from_response(self, console, api_error):
        """`from_response` sets field="request"; render "Invalid request:
        <message>" instead of "Validation error for 'request': …"."""
        exc = api_error(
            EeroValidationException,
            400,
            "error.form.errors",
            message="email is malformed",
        )

        assert exc.field == "request"

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.USAGE_ERROR
        call_args = console.print.call_args[0][0]
        assert "Invalid request: email is malformed" in call_args
        assert "Validation error for 'request'" not in call_args

    def test_error_code_suffix_present_when_set(self, console):
        """error_code, when truthy, is appended to the rendered message."""
        exc = EeroTimeoutException("Request timed out", error_code="error.timeout")

        handle_cli_error(exc, console)

        call_args = console.print.call_args[0][0]
        assert "(error code: error.timeout)" in call_args

    def test_error_code_suffix_absent_when_unset(self, console):
        """No error_code -> no suffix."""
        exc = EeroTimeoutException("Request timed out")

        handle_cli_error(exc, console)

        call_args = console.print.call_args[0][0]
        assert "(error code:" not in call_args

    def test_envelope_never_rendered(self, console):
        """`.envelope` must never appear in the rendered message (it can
        carry user_token, emails, phones)."""
        exc = EeroTimeoutException(
            "Request timed out",
            envelope={"data": {"user_token": "super-secret-token"}},
        )

        handle_cli_error(exc, console)

        call_args = console.print.call_args[0][0]
        assert "super-secret-token" not in call_args

    def test_api_exception_401(self, console):
        """Test handling of 401 API exception."""
        exc = EeroAPIException(401, "Unauthorized")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.AUTH_REQUIRED
        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "expired" in call_args.lower() or "login" in call_args.lower()

    def test_api_exception_403_generic(self, console):
        """A generic EeroAPIException(403, …) (not EeroAccessDeniedException)
        still falls back to FORBIDDEN through the EeroAPIException branch."""
        exc = EeroAPIException(403, "Forbidden")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.FORBIDDEN
        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "Permission denied" in call_args

    def test_api_exception_404(self, console):
        """A generic EeroAPIException(404, …) (not EeroNotFoundException)
        still falls back to NOT_FOUND through the EeroAPIException branch."""
        exc = EeroAPIException(404, "Network not found")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.NOT_FOUND

    def test_api_exception_409(self, console):
        """Test handling of 409 API exception."""
        exc = EeroAPIException(409, "Conflict")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.CONFLICT

    def test_api_exception_429_maps_to_generic_error(self, console):
        """No dedicated code for 429 either (Q5); unmapped -> GENERIC_ERROR."""
        exc = EeroAPIException(429, "Rate limited")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.GENERIC_ERROR

    def test_api_exception_500(self, console):
        """Test handling of 500 API exception."""
        exc = EeroAPIException(500, "Internal server error")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.GENERIC_ERROR
        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "500" in call_args

    def test_generic_eero_exception(self, console):
        """Test handling of generic Eero exception."""
        exc = EeroException("Something went wrong")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.GENERIC_ERROR
        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "Something went wrong" in call_args

    def test_unknown_exception(self, console):
        """Test handling of unknown exception type."""
        exc = ValueError("Unexpected error")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.GENERIC_ERROR
        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "Unexpected error" in call_args

    def test_context_prefix(self, console):
        """Test error message includes context prefix."""
        exc = EeroException("Error message")

        handle_cli_error(exc, console, context="Network operation")

        call_args = console.print.call_args[0][0]
        assert "Network operation:" in call_args

    # ---------------- Negative tests: substring fallbacks are gone ----------------

    def test_generic_exception_with_premium_keyword_is_not_reclassified(self, console):
        """A plain EeroException whose message mentions "premium" must map
        to GENERIC_ERROR (1), never PREMIUM_REQUIRED (11) — the deleted
        is_premium_error() substring fallback must not resurface."""
        exc = EeroException("premium plan required")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.GENERIC_ERROR
        assert exit_code == 1

    def test_generic_exception_with_beacon_keyword_is_not_reclassified(self, console):
        """A plain EeroException whose message mentions "beacon" must map to
        GENERIC_ERROR (1), never FEATURE_UNAVAILABLE (12) or NOT_FOUND (5) —
        the deleted is_feature_unavailable_error()/is_not_found_error()
        substring fallbacks must not resurface."""
        exc = EeroException("beacon not found")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.GENERIC_ERROR
        assert exit_code == 1
