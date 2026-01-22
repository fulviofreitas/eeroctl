"""Eero device formatting utilities for the Eero CLI.

This module provides formatting functions for displaying Eero device data.
Updated to work with raw dict data from transformers.
"""

from typing import Any, Dict, List, Optional, Union

from rich.panel import Panel
from rich.table import Table

from ..transformers.eero import normalize_eero
from .base import (
    DetailLevel,
    build_panel,
    console,
    field,
    field_bool,
    field_status,
    format_eero_status,
)

# ==================== Eero Table ====================


def create_eeros_table(eeros: List[Dict[str, Any]]) -> Table:
    """Create a table displaying Eero devices.

    Args:
        eeros: List of eero dicts (already transformed)

    Returns:
        Rich Table object
    """
    table = Table(title="Eero Devices")
    table.add_column("ID", style="dim")
    table.add_column("Name/Location", style="cyan")
    table.add_column("Model", style="blue")
    table.add_column("Status", style="green")
    table.add_column("Role", style="magenta")
    table.add_column("Clients", style="yellow")
    table.add_column("Firmware", style="cyan")

    for eero in eeros:
        e = normalize_eero(eero) if "_raw" not in eero else eero

        status = e.get("status", "unknown")
        status_text, status_style = format_eero_status(status)

        role = "Gateway" if e.get("is_gateway") else "Leaf"
        clients = str(e.get("connected_clients_count", 0))
        name = e.get("name") or e.get("location") or "Unknown"

        table.add_row(
            e.get("id") or "Unknown",
            name,
            e.get("model") or "Unknown",
            f"[{status_style}]{status_text}[/{status_style}]",
            role,
            clients,
            e.get("os_version") or "Unknown",
        )

    return table


# ==================== Eero Brief View Panels ====================


def _eero_basic_panel(eero: Dict[str, Any], extensive: bool = False) -> Panel:
    """Build the basic eero info panel."""
    status = eero.get("status", "unknown")
    status_text, status_style = format_eero_status(status)
    name = eero.get("name") or eero.get("location") or "Unknown"

    lines = [
        field("Name/Location", name),
        field("Model", eero.get("model")),
        field("Model Number", eero.get("model_number")),
        field("Serial", eero.get("serial")),
        field_status("Status", status_text, status_style),
        field_bool("Gateway", eero.get("is_gateway")),
        field_bool("Wired", eero.get("wired")),
        field("Firmware", eero.get("os_version")),
        field("Clients", eero.get("connected_clients_count", 0)),
    ]

    if extensive:
        lines.extend(
            [
                field("MAC Address", eero.get("mac_address")),
                field("IP Address", eero.get("ip_address")),
                field_bool("Update Available", eero.get("update_available")),
            ]
        )

    return build_panel(lines, f"Eero: {name}", "blue")


def _eero_led_panel(eero: Dict[str, Any]) -> Optional[Panel]:
    """Build the LED/nightlight panel."""
    led_on = eero.get("led_on")
    nightlight_enabled = eero.get("nightlight_enabled")

    if led_on is None and nightlight_enabled is None:
        return None

    lines = []
    if led_on is not None:
        lines.append(field_bool("LED", led_on))
    if eero.get("led_brightness") is not None:
        lines.append(field("LED Brightness", f"{eero.get('led_brightness')}%"))
    if nightlight_enabled is not None:
        lines.append(field_bool("Nightlight", nightlight_enabled))

    nightlight = eero.get("nightlight", {})
    if nightlight and isinstance(nightlight, dict):
        schedule = nightlight.get("schedule")
        if schedule:
            lines.append(field("Schedule", schedule))

    return build_panel(lines, "LED & Nightlight", "yellow") if lines else None


def _eero_performance_panel(eero: Dict[str, Any]) -> Optional[Panel]:
    """Build the performance panel."""
    uptime = eero.get("uptime")
    mesh_quality = eero.get("mesh_quality_bars")

    if uptime is None and mesh_quality is None:
        return None

    lines = []

    if uptime is not None:
        hours = uptime // 3600
        days = hours // 24
        if days > 0:
            lines.append(field("Uptime", f"{days} days, {hours % 24} hours"))
        else:
            lines.append(field("Uptime", f"{hours} hours"))

    if mesh_quality is not None:
        bars_style = "green" if mesh_quality >= 4 else "yellow" if mesh_quality >= 2 else "red"
        filled = "●" * mesh_quality
        empty = "○" * (5 - mesh_quality)
        lines.append(
            f"[bold]Mesh Quality:[/bold] [{bars_style}]{filled}{empty} ({mesh_quality}/5)[/{bars_style}]"
        )

    if eero.get("memory_usage") is not None:
        lines.append(field("Memory Usage", f"{eero.get('memory_usage')}%"))

    if eero.get("cpu_usage") is not None:
        lines.append(field("CPU Usage", f"{eero.get('cpu_usage')}%"))

    return build_panel(lines, "Performance", "green") if lines else None


# ==================== Main Eero Details Function ====================


def print_eero_details(
    eero: Union[Dict[str, Any], Any], detail_level: DetailLevel = "brief"
) -> None:
    """Print eero information with configurable detail level.

    Args:
        eero: Eero dict or model object
        detail_level: "brief" or "full"
    """
    # Normalize to dict if needed
    if isinstance(eero, dict):
        e = normalize_eero(eero) if "_raw" not in eero else eero
    else:
        # Legacy model support - convert to dict
        if hasattr(eero, "model_dump"):
            e = normalize_eero(eero.model_dump())
        else:
            e = normalize_eero(vars(eero))

    extensive = detail_level == "full"

    # Basic info panel (always shown)
    console.print(_eero_basic_panel(e, extensive))

    # LED/Nightlight panel
    led_panel = _eero_led_panel(e)
    if led_panel:
        console.print(led_panel)

    # Performance panel
    perf_panel = _eero_performance_panel(e)
    if perf_panel:
        console.print(perf_panel)
