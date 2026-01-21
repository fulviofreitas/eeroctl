"""Miscellaneous formatting utilities for the Eero CLI.

This module provides formatting functions for speed tests, blacklists,
and other miscellaneous data.
"""

from typing import Any, Dict, List

from rich.table import Table

from .base import build_panel, console, field

# ==================== Speed Test Formatting ====================


def print_speedtest_results(result: dict) -> None:
    """Print speed test results.

    Args:
        result: Speed test result dictionary
    """
    download = result.get("down", {}).get("value", 0)
    upload = result.get("up", {}).get("value", 0)
    latency = result.get("latency", {}).get("value", 0)

    lines = [
        field("Download", f"{download} Mbps"),
        field("Upload", f"{upload} Mbps"),
        field("Latency", f"{latency} ms"),
    ]
    console.print(build_panel(lines, "Speed Test Results", "green"))


# ==================== Blacklist Formatting ====================


def create_blacklist_table(blacklist_data: List[Dict[str, Any]]) -> Table:
    """Create a table displaying blacklisted devices.

    Args:
        blacklist_data: List of blacklisted device dictionaries

    Returns:
        Rich Table object
    """
    table = Table(title="Blacklisted Devices")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Nickname", style="blue")
    table.add_column("IP", style="green")
    table.add_column("MAC", style="yellow")
    table.add_column("Type", style="cyan")
    table.add_column("Manufacturer", style="green")
    table.add_column("Connection Type", style="blue")
    table.add_column("Eero Location", style="yellow")
    table.add_column("Last Active", style="magenta")

    for device in blacklist_data:
        device_id = "Unknown"
        if device.get("url"):
            parts = device["url"].split("/")
            if len(parts) >= 2:
                device_id = parts[-1]

        device_name = (
            device.get("display_name")
            or device.get("hostname")
            or device.get("nickname")
            or "Unknown"
        )
        source = device.get("source", {})
        eero_location = source.get("location") if source else "Unknown"

        table.add_row(
            device_id,
            device_name,
            device.get("nickname") or "",
            device.get("ip") or "Unknown",
            device.get("mac") or "Unknown",
            device.get("device_type") or "Unknown",
            device.get("manufacturer") or "Unknown",
            device.get("connection_type") or "Unknown",
            eero_location,
            str(device.get("last_active") or "Unknown"),
        )

    return table
