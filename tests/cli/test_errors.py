"""Unit tests for eero.cli.errors module.

Tests cover:
- handle_cli_error function for different exception types
- Error helper functions (is_premium_error, is_feature_unavailable_error, is_not_found_error)
"""

from unittest.mock import MagicMock

import pytest
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

from eero_cli.errors import (
    handle_cli_error,
    is_feature_unavailable_error,
    is_not_found_error,
    is_premium_error,
)
from eero_cli.exit_codes import ExitCode

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

    def test_not_found_exception(self, console):
        """Test handling of not found exception."""
        exc = EeroNotFoundException("Eero", "living_room")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.NOT_FOUND
        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "Eero" in call_args
        assert "living_room" in call_args

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

    def test_rate_limit_exception(self, console):
        """Test handling of rate limit exception."""
        exc = EeroRateLimitException("Too many requests")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.TIMEOUT
        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "Rate limited" in call_args

    def test_timeout_exception(self, console):
        """Test handling of timeout exception."""
        exc = EeroTimeoutException("Request timed out")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.TIMEOUT
        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "timed out" in call_args

    def test_validation_exception(self, console):
        """Test handling of validation exception."""
        exc = EeroValidationException("password", "Must be at least 8 characters")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.USAGE_ERROR
        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "password" in call_args

    def test_api_exception_401(self, console):
        """Test handling of 401 API exception."""
        exc = EeroAPIException(401, "Unauthorized")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.AUTH_REQUIRED
        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "expired" in call_args.lower() or "login" in call_args.lower()

    def test_api_exception_403(self, console):
        """Test handling of 403 API exception."""
        exc = EeroAPIException(403, "Forbidden")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.FORBIDDEN
        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "Permission denied" in call_args

    def test_api_exception_404(self, console):
        """Test handling of 404 API exception."""
        exc = EeroAPIException(404, "Network not found")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.NOT_FOUND

    def test_api_exception_409(self, console):
        """Test handling of 409 API exception."""
        exc = EeroAPIException(409, "Conflict")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.CONFLICT

    def test_api_exception_429(self, console):
        """Test handling of 429 API exception."""
        exc = EeroAPIException(429, "Rate limited")

        exit_code = handle_cli_error(exc, console)

        assert exit_code == ExitCode.TIMEOUT

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


# ========================== is_premium_error Tests ==========================


class TestIsPremiumError:
    """Tests for is_premium_error helper function."""

    def test_premium_required_exception_returns_true(self):
        """Test returns True for EeroPremiumRequiredException."""
        exc = EeroPremiumRequiredException("Feature")
        assert is_premium_error(exc) is True

    def test_generic_exception_with_premium_keyword_returns_true(self):
        """Test returns True when error message contains 'premium'."""
        exc = Exception("This feature requires premium")
        assert is_premium_error(exc) is True

    def test_generic_exception_with_plus_keyword_returns_true(self):
        """Test returns True when error message contains 'plus'."""
        exc = Exception("Requires Eero Plus subscription")
        assert is_premium_error(exc) is True

    def test_generic_exception_with_subscription_keyword_returns_true(self):
        """Test returns True when error message contains 'subscription'."""
        exc = Exception("Active subscription required")
        assert is_premium_error(exc) is True

    def test_unrelated_exception_returns_false(self):
        """Test returns False for unrelated exceptions."""
        exc = Exception("Network timeout")
        assert is_premium_error(exc) is False

    def test_case_insensitive_matching(self):
        """Test keyword matching is case insensitive."""
        exc = Exception("PREMIUM feature required")
        assert is_premium_error(exc) is True

        exc = Exception("Eero PLUS subscription")
        assert is_premium_error(exc) is True


# ========================== is_feature_unavailable_error Tests ==========================


class TestIsFeatureUnavailableError:
    """Tests for is_feature_unavailable_error helper function."""

    def test_feature_unavailable_exception_returns_true(self):
        """Test returns True for EeroFeatureUnavailableException."""
        exc = EeroFeatureUnavailableException("Nightlight", "not supported")
        assert is_feature_unavailable_error(exc, "anything") is True

    def test_generic_exception_with_keyword_returns_true(self):
        """Test returns True when message contains feature keyword."""
        exc = Exception("Beacon feature not available")
        assert is_feature_unavailable_error(exc, "beacon") is True

    def test_generic_exception_without_keyword_returns_false(self):
        """Test returns False when message doesn't contain keyword."""
        exc = Exception("Network error occurred")
        assert is_feature_unavailable_error(exc, "beacon") is False

    def test_case_insensitive_matching(self):
        """Test keyword matching is case insensitive."""
        exc = Exception("BEACON nightlight is not supported")
        assert is_feature_unavailable_error(exc, "beacon") is True

        exc = Exception("This is for Beacon only")
        assert is_feature_unavailable_error(exc, "BEACON") is True


# ========================== is_not_found_error Tests ==========================


class TestIsNotFoundError:
    """Tests for is_not_found_error helper function."""

    def test_not_found_exception_returns_true(self):
        """Test returns True for EeroNotFoundException."""
        exc = EeroNotFoundException("Device", "abc123")
        assert is_not_found_error(exc) is True

    def test_api_exception_404_returns_true(self):
        """Test returns True for EeroAPIException with 404 status."""
        exc = EeroAPIException(404, "Resource not found")
        assert is_not_found_error(exc) is True

    def test_api_exception_other_status_returns_false(self):
        """Test returns False for EeroAPIException with non-404 status."""
        exc = EeroAPIException(500, "Server error")
        assert is_not_found_error(exc) is False

    def test_generic_exception_with_not_found_returns_true(self):
        """Test returns True when message contains 'not found'."""
        exc = Exception("Device not found in network")
        assert is_not_found_error(exc) is True

    def test_generic_exception_without_not_found_returns_false(self):
        """Test returns False for unrelated exceptions."""
        exc = Exception("Connection timeout")
        assert is_not_found_error(exc) is False

    def test_case_insensitive_matching(self):
        """Test 'not found' matching is case insensitive."""
        exc = Exception("Resource NOT FOUND")
        assert is_not_found_error(exc) is True
