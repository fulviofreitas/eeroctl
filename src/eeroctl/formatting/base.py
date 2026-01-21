"""Base formatting utilities for the Eero CLI.

This module provides shared formatting functions, constants, and helpers
used across all formatting modules.
"""

from typing import Any, List, Literal, Optional

from eero.const import EeroDeviceStatus
from eero.models.network import Network
from rich.console import Console
from rich.panel import Panel

# Create console for rich output
console = Console()

# Type alias for detail level
DetailLevel = Literal["brief", "full"]


# ==================== Status Formatting Helpers ====================


def get_network_status_value(network: Network) -> str:
    """Extract the status value from a network, handling both enum and string types.

    Args:
        network: Network model instance

    Returns:
        Status string value (e.g., "online", "offline")
    """
    if not network.status:
        return "unknown"
    # Handle both enum (has .value) and string types
    if hasattr(network.status, "value"):
        return str(network.status.value)
    return str(network.status)


def format_network_status(status_value: str) -> tuple[str, str]:
    """Format network status into display text and style.

    Args:
        status_value: Clean status string (e.g., "online", "offline", "updating")

    Returns:
        Tuple of (display_text, style)
    """
    status_lower = status_value.lower()
    if status_lower in ("online", "connected"):
        return "online", "green"
    elif status_lower == "offline":
        return "offline", "red"
    elif status_lower == "updating":
        return "updating", "yellow"
    return status_value or "unknown", "dim"


def format_device_status(status: EeroDeviceStatus) -> tuple[str, str]:
    """Format device status into display text and style.

    Args:
        status: Device status enum

    Returns:
        Tuple of (display_text, style)
    """
    if status == EeroDeviceStatus.CONNECTED:
        return "connected", "green"
    elif status == EeroDeviceStatus.BLOCKED:
        return "blocked", "red"
    elif status == EeroDeviceStatus.DISCONNECTED:
        return "disconnected", "yellow"
    return "unknown", "dim"


def format_eero_status(status: str) -> tuple[str, str]:
    """Format eero status into display text and style.

    Args:
        status: Eero status string

    Returns:
        Tuple of (display_text, style)
    """
    if status == "green":
        return status, "green"
    return status, "red"


def format_bool(value: bool, true_text: str = "Yes", false_text: str = "No") -> str:
    """Format a boolean value with color coding.

    Args:
        value: Boolean value
        true_text: Text to display when True
        false_text: Text to display when False

    Returns:
        Formatted string
    """
    if value:
        return f"[green]{true_text}[/green]"
    return f"[dim]{false_text}[/dim]"


def format_enabled(value: bool) -> str:
    """Format an enabled/disabled value."""
    return format_bool(value, "Enabled", "Disabled")


# ==================== Panel Building Helpers ====================


def build_panel(lines: List[str], title: str, border_style: str = "blue") -> Panel:
    """Build a panel from a list of formatted lines.

    Args:
        lines: List of formatted text lines
        title: Panel title
        border_style: Rich border style

    Returns:
        Rich Panel object
    """
    # Filter out None and empty lines
    content = "\n".join(line for line in lines if line)
    return Panel(content, title=title, border_style=border_style)


def field(label: str, value: Any, default: str = "Unknown") -> str:
    """Format a single field line.

    Args:
        label: Field label
        value: Field value
        default: Default value if value is None/empty

    Returns:
        Formatted line string
    """
    display_value = value if value is not None else default
    if display_value == "":
        display_value = default
    return f"[bold]{label}:[/bold] {display_value}"


def field_bool(label: str, value: Optional[bool]) -> str:
    """Format a boolean field line."""
    return f"[bold]{label}:[/bold] {format_enabled(bool(value)) if value is not None else '[dim]Unknown[/dim]'}"


def field_status(label: str, text: str, style: str) -> str:
    """Format a status field line with color."""
    return f"[bold]{label}:[/bold] [{style}]{text}[/{style}]"


# ==================== Date/Time Formatting ====================


def format_datetime(dt: Any, include_time: bool = True) -> str:
    """Format a datetime value for display.

    Args:
        dt: Datetime object or string
        include_time: Whether to include time component

    Returns:
        Formatted datetime string
    """
    if dt is None:
        return "Unknown"
    if hasattr(dt, "strftime"):
        fmt = "%Y-%m-%d %H:%M:%S" if include_time else "%Y-%m-%d"
        return dt.strftime(fmt)
    # Handle string datetime
    dt_str = str(dt)
    if include_time:
        return dt_str[:19].replace("T", " ")
    return dt_str[:10]
