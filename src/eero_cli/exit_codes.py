"""Exit codes for the Eero CLI.

Standard exit codes for consistent behavior across all commands.
"""

from enum import IntEnum


class ExitCode(IntEnum):
    """Standard exit codes for the CLI.

    Exit codes must be consistent across all commands for scripting.
    """

    SUCCESS = 0
    """Command completed successfully."""

    GENERIC_ERROR = 1
    """Generic/unexpected error."""

    USAGE_ERROR = 2
    """Invalid arguments or command usage."""

    AUTH_REQUIRED = 3
    """Authentication required or session expired."""

    FORBIDDEN = 4
    """Permission denied/forbidden operation."""

    NOT_FOUND = 5
    """Resource not found (ID, name, MAC address)."""

    CONFLICT = 6
    """Conflict or invalid state (e.g., already enabled)."""

    TIMEOUT = 7
    """Request or operation timed out."""

    SAFETY_RAIL = 8
    """Safety rail triggered - needs --force or confirmation."""

    # Reserved: 9

    PARTIAL_SUCCESS = 10
    """Multi-target operation had partial success."""

    PREMIUM_REQUIRED = 11
    """Feature requires Eero Plus subscription."""

    FEATURE_UNAVAILABLE = 12
    """Feature is not available on this device or network."""


# Exit code descriptions for help text
EXIT_CODE_DESCRIPTIONS = {
    ExitCode.SUCCESS: "Operation completed successfully",
    ExitCode.GENERIC_ERROR: "An unexpected error occurred",
    ExitCode.USAGE_ERROR: "Invalid command usage or arguments",
    ExitCode.AUTH_REQUIRED: "Authentication required or session expired",
    ExitCode.FORBIDDEN: "Permission denied for this operation",
    ExitCode.NOT_FOUND: "Requested resource not found",
    ExitCode.CONFLICT: "Operation conflicts with current state",
    ExitCode.TIMEOUT: "Operation timed out",
    ExitCode.SAFETY_RAIL: "Safety confirmation required (use --force)",
    ExitCode.PARTIAL_SUCCESS: "Operation partially completed",
    ExitCode.PREMIUM_REQUIRED: "Feature requires Eero Plus subscription",
    ExitCode.FEATURE_UNAVAILABLE: "Feature not available on this device",
}
