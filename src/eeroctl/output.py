"""Output rendering layer for the Eero CLI.

Provides consistent output formatting across all commands:
- table: Rich formatted tables (default for read commands)
- list: One-item-per-line grep-friendly format
- json: Structured JSON with schema envelope
- yaml: YAML output format
- text: Plain text key-value format
"""

import json as json_lib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Union

import yaml  # type: ignore[import-untyped]
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


class OutputFormat(str, Enum):
    """Output format options."""

    TABLE = "table"
    LIST = "list"
    JSON = "json"
    YAML = "yaml"
    TEXT = "text"


class DetailLevel(str, Enum):
    """Detail level for output."""

    BRIEF = "brief"
    FULL = "full"


@dataclass
class OutputMeta:
    """Metadata for JSON output envelope."""

    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    network_id: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class OutputContext:
    """Context for output rendering."""

    format: OutputFormat = OutputFormat.TABLE
    detail: DetailLevel = DetailLevel.BRIEF
    quiet: bool = False
    no_color: bool = False
    network_id: Optional[str] = None

    # Console instance (created lazily)
    _console: Optional[Console] = field(default=None, repr=False)
    _err_console: Optional[Console] = field(default=None, repr=False)

    @property
    def console(self) -> Console:
        """Get the main console for stdout."""
        if self._console is None:
            self._console = Console(
                no_color=self.no_color,
                force_terminal=None if not self.no_color else False,
            )
        return self._console

    @property
    def err_console(self) -> Console:
        """Get the error console for stderr."""
        if self._err_console is None:
            self._err_console = Console(
                stderr=True,
                no_color=self.no_color,
                force_terminal=None if not self.no_color else False,
            )
        return self._err_console


class Renderable(Protocol):
    """Protocol for objects that can be rendered."""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON output."""
        ...

    def to_table_row(self) -> List[str]:
        """Convert to table row values."""
        ...

    def to_list_line(self) -> str:
        """Convert to single line for list output."""
        ...


class OutputRenderer:
    """Renders output in various formats."""

    def __init__(self, ctx: OutputContext):
        self.ctx = ctx

    def render(
        self,
        data: Union[Dict, List, Any],
        schema: str,
        table_columns: Optional[List[Dict[str, Any]]] = None,
        table_rows: Optional[List[List[str]]] = None,
        list_items: Optional[List[str]] = None,
        meta: Optional[OutputMeta] = None,
    ) -> None:
        """Render data in the current output format.

        This is the unified entry point that automatically routes to the
        appropriate format renderer based on the context's output format.

        Args:
            data: The data to render (used for json, yaml, text formats)
            schema: Schema identifier (e.g., "eero.network.list/v1")
            table_columns: Column definitions for table format (optional)
            table_rows: Row data for table format (optional)
            list_items: Items for list format (optional)
            meta: Optional metadata for structured outputs
        """
        if self.ctx.format == OutputFormat.JSON:
            self.render_json(data, schema, meta)
        elif self.ctx.format == OutputFormat.YAML:
            self.render_yaml(data, schema, meta)
        elif self.ctx.format == OutputFormat.TEXT:
            self.render_text(data, schema, meta)
        elif self.ctx.format == OutputFormat.LIST:
            if list_items is not None:
                self.render_list(list_items)
            elif isinstance(data, list):
                # Auto-generate list items from data
                items = []
                for item in data:
                    if isinstance(item, dict):
                        name = (
                            item.get("name")
                            or item.get("display_name")
                            or item.get("id", "Unknown")
                        )
                        items.append(str(name))
                    else:
                        items.append(str(item))
                self.render_list(items)
            else:
                self.render_list([str(data)])
        else:  # TABLE (default)
            if table_columns is not None and table_rows is not None:
                # Extract title from schema
                title = schema.split("/")[0].replace("eero.", "").replace(".", " ").title()
                self.render_table(title, table_columns, table_rows)
            else:
                # Fallback to text for single items
                self.render_text(data, schema, meta)

    def render_json(
        self,
        data: Union[Dict, List, Any],
        schema: str,
        meta: Optional[OutputMeta] = None,
    ) -> None:
        """Render data as JSON with envelope.

        Args:
            data: The data to render
            schema: Schema identifier (e.g., "eero.network.show/v1")
            meta: Optional metadata
        """
        if meta is None:
            meta = OutputMeta(network_id=self.ctx.network_id)

        envelope = {
            "schema": schema,
            "data": data,
            "meta": {
                "timestamp": meta.timestamp,
                "network_id": meta.network_id,
                "warnings": meta.warnings,
            },
        }

        # Use standard json for clean output
        output = json_lib.dumps(envelope, indent=2, default=str)
        self.ctx.console.print(output, highlight=False)

    def render_yaml(
        self,
        data: Union[Dict, List, Any],
        schema: str,
        meta: Optional[OutputMeta] = None,
    ) -> None:
        """Render data as YAML with envelope.

        Args:
            data: The data to render
            schema: Schema identifier (e.g., "eero.network.show/v1")
            meta: Optional metadata
        """
        if meta is None:
            meta = OutputMeta(network_id=self.ctx.network_id)

        envelope = {
            "schema": schema,
            "data": data,
            "meta": {
                "timestamp": meta.timestamp,
                "network_id": meta.network_id,
                "warnings": meta.warnings,
            },
        }

        # Use yaml for clean output
        output = yaml.dump(envelope, default_flow_style=False, sort_keys=False, allow_unicode=True)
        self.ctx.console.print(output, highlight=False)

    def render_text(
        self,
        data: Union[Dict, List, Any],
        schema: str,
        meta: Optional[OutputMeta] = None,
    ) -> None:
        """Render data as plain text key-value pairs.

        Args:
            data: The data to render
            schema: Schema identifier (used for title)
            meta: Optional metadata (ignored in text output)
        """
        if isinstance(data, dict):
            self._render_text_dict(data)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if i > 0:
                    self.ctx.console.print("---", highlight=False)
                if isinstance(item, dict):
                    self._render_text_dict(item)
                else:
                    self.ctx.console.print(str(item), highlight=False)
        else:
            self.ctx.console.print(str(data), highlight=False)

    def _render_text_dict(self, data: Dict[str, Any], prefix: str = "") -> None:
        """Render a dictionary as plain text key-value pairs."""
        for key, value in data.items():
            formatted_key = key.replace("_", " ").title()
            if isinstance(value, dict):
                self.ctx.console.print(f"{prefix}{formatted_key}:", highlight=False)
                self._render_text_dict(value, prefix=prefix + "  ")
            elif isinstance(value, list):
                if not value:
                    self.ctx.console.print(f"{prefix}{formatted_key}: (none)", highlight=False)
                elif all(isinstance(v, (str, int, float, bool)) for v in value):
                    self.ctx.console.print(
                        f"{prefix}{formatted_key}: {', '.join(str(v) for v in value)}",
                        highlight=False,
                    )
                else:
                    self.ctx.console.print(f"{prefix}{formatted_key}:", highlight=False)
                    for item in value:
                        if isinstance(item, dict):
                            self._render_text_dict(item, prefix=prefix + "  ")
                            self.ctx.console.print(f"{prefix}  ---", highlight=False)
                        else:
                            self.ctx.console.print(f"{prefix}  - {item}", highlight=False)
            elif value is None:
                self.ctx.console.print(f"{prefix}{formatted_key}: -", highlight=False)
            elif isinstance(value, bool):
                self.ctx.console.print(
                    f"{prefix}{formatted_key}: {'yes' if value else 'no'}", highlight=False
                )
            else:
                self.ctx.console.print(f"{prefix}{formatted_key}: {value}", highlight=False)

    def render_mutation_result(
        self,
        changed: bool,
        target: str,
        action: str,
        job_id: Optional[str] = None,
        message: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> None:
        """Render result of a mutating operation.

        Args:
            changed: Whether the state was changed
            target: Target of the operation
            action: Action performed
            job_id: Optional job ID for async operations
            message: Optional human-readable message
            schema: Schema for JSON output
        """
        if self.ctx.format == OutputFormat.JSON:
            result = {
                "changed": changed,
                "target": target,
                "action": action,
            }
            if job_id:
                result["job_id"] = job_id

            self.render_json(result, schema or f"eero.mutation.{action}/v1")
        else:
            if not self.ctx.quiet:
                if message:
                    self.ctx.console.print(message)
                else:
                    status = "[green]✓[/green]" if changed else "[yellow]•[/yellow]"
                    self.ctx.console.print(f"{status} {action}: {target}")

    def render_table(
        self,
        title: str,
        columns: List[Dict[str, Any]],
        rows: List[List[str]],
    ) -> None:
        """Render data as a Rich table.

        Args:
            title: Table title
            columns: Column definitions with 'name' and optional 'style', 'justify'
            rows: Row data as list of lists
        """
        table = Table(title=title, show_header=True)

        for col in columns:
            table.add_column(
                col["name"],
                style=col.get("style"),
                justify=col.get("justify", "left"),
                no_wrap=col.get("no_wrap", False),
            )

        for row in rows:
            table.add_row(*row)

        self.ctx.console.print(table)

    def render_list(self, items: List[str]) -> None:
        """Render items as one-per-line list.

        Args:
            items: List of items to render
        """
        for item in items:
            self.ctx.console.print(item, highlight=False)

    def render_panel(
        self,
        content: str,
        title: str,
        border_style: str = "blue",
    ) -> None:
        """Render content in a Rich panel.

        Args:
            content: Panel content
            title: Panel title
            border_style: Border color/style
        """
        panel = Panel(content, title=title, border_style=border_style)
        self.ctx.console.print(panel)

    def render_error(self, message: str, hint: Optional[str] = None) -> None:
        """Render an error message to stderr.

        Args:
            message: Error message
            hint: Optional hint for resolution
        """
        self.ctx.err_console.print(f"[bold red]Error:[/bold red] {message}")
        if hint:
            self.ctx.err_console.print(f"[dim]Hint: {hint}[/dim]")

    def render_warning(self, message: str) -> None:
        """Render a warning message to stderr.

        Args:
            message: Warning message
        """
        self.ctx.err_console.print(f"[yellow]Warning:[/yellow] {message}")

    def render_success(self, message: str) -> None:
        """Render a success message.

        Args:
            message: Success message
        """
        if not self.ctx.quiet:
            self.ctx.console.print(f"[bold green]✓[/bold green] {message}")

    def render_info(self, message: str) -> None:
        """Render an info message.

        Args:
            message: Info message
        """
        if not self.ctx.quiet:
            self.ctx.console.print(f"[blue]ℹ[/blue] {message}")


# Convenience function to get renderer from click context
def get_renderer(ctx) -> OutputRenderer:
    """Get OutputRenderer from Click context.

    Args:
        ctx: Click context

    Returns:
        OutputRenderer instance
    """
    output_ctx = getattr(ctx.obj, "output_ctx", None)
    if output_ctx is None:
        output_ctx = OutputContext()
    return OutputRenderer(output_ctx)


class OutputManager:
    """Simplified output manager for easy format-based rendering."""

    # Define which columns to show for each resource type (based on schema prefix)
    COLUMN_CONFIGS = {
        "eero.network": ["id", "name", "status", "public_ip", "isp_name"],
        "eero.eero": ["eero_id", "location", "model", "status", "is_gateway", "ip_address"],
        "eero.client": ["id", "display_name", "ip", "mac", "connected", "connection_type"],
        "eero.profile": ["id", "name", "paused", "device_count"],
        "eero.activity": ["name", "category", "bytes", "time"],
        "eero.troubleshoot": [
            "network_name",
            "network_status",
            "internet",
            "mesh",
            "total_eeros",
            "total_clients",
        ],
    }

    def __init__(self, console: Console):
        self.console = console
        self._err_console = Console(stderr=True)

    def render(
        self,
        format: str,
        data: Union[Dict, List],
        schema: str,
        meta: Dict[str, Any],
    ) -> None:
        """Render data in the specified format.

        Args:
            format: Output format (table, list, json, yaml, text)
            data: Data to render
            schema: Schema identifier for JSON/YAML envelope
            meta: Metadata for JSON/YAML envelope
        """
        if format == "json":
            self._render_json(data, schema, meta)
        elif format == "yaml":
            self._render_yaml(data, schema, meta)
        elif format == "text":
            self._render_text(data, schema)
        elif format == "list":
            self._render_list(data, schema)
        else:
            self._render_table(data, schema)

    def _render_json(
        self,
        data: Union[Dict, List],
        schema: str,
        meta: Dict[str, Any],
    ) -> None:
        """Render as JSON with envelope."""
        envelope = {
            "schema": schema,
            "data": data,
            "meta": {
                "timestamp": meta.get(
                    "timestamp", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                ),
                "network_id": meta.get("network_id"),
                "warnings": meta.get("warnings", []),
            },
        }
        output = json_lib.dumps(envelope, indent=2, default=str)
        self.console.print(output, highlight=False)

    def _render_yaml(
        self,
        data: Union[Dict, List],
        schema: str,
        meta: Dict[str, Any],
    ) -> None:
        """Render as YAML with envelope."""
        envelope = {
            "schema": schema,
            "data": data,
            "meta": {
                "timestamp": meta.get(
                    "timestamp", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                ),
                "network_id": meta.get("network_id"),
                "warnings": meta.get("warnings", []),
            },
        }
        output = yaml.dump(envelope, default_flow_style=False, sort_keys=False, allow_unicode=True)
        self.console.print(output, highlight=False)

    def _render_text(self, data: Union[Dict, List], schema: str = "") -> None:
        """Render as plain text key-value pairs."""
        if not data:
            self.console.print("No data to display.", highlight=False)
            return

        if isinstance(data, dict):
            self._render_text_dict(data)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if i > 0:
                    self.console.print("---", highlight=False)
                if isinstance(item, dict):
                    self._render_text_dict(item)
                else:
                    self.console.print(str(item), highlight=False)

    def _render_text_dict(self, data: Dict[str, Any], prefix: str = "") -> None:
        """Render a dictionary as plain text key-value pairs."""
        for key, value in data.items():
            formatted_key = key.replace("_", " ").title()
            if isinstance(value, dict):
                self.console.print(f"{prefix}{formatted_key}:", highlight=False)
                self._render_text_dict(value, prefix=prefix + "  ")
            elif isinstance(value, list):
                if not value:
                    self.console.print(f"{prefix}{formatted_key}: (none)", highlight=False)
                elif all(isinstance(v, (str, int, float, bool)) for v in value):
                    self.console.print(
                        f"{prefix}{formatted_key}: {', '.join(str(v) for v in value)}",
                        highlight=False,
                    )
                else:
                    self.console.print(f"{prefix}{formatted_key}:", highlight=False)
                    for item in value:
                        if isinstance(item, dict):
                            self._render_text_dict(item, prefix=prefix + "  ")
                            self.console.print(f"{prefix}  ---", highlight=False)
                        else:
                            self.console.print(f"{prefix}  - {item}", highlight=False)
            elif value is None:
                self.console.print(f"{prefix}{formatted_key}: -", highlight=False)
            elif isinstance(value, bool):
                self.console.print(
                    f"{prefix}{formatted_key}: {'yes' if value else 'no'}", highlight=False
                )
            else:
                self.console.print(f"{prefix}{formatted_key}: {value}", highlight=False)

    def _get_columns_for_schema(self, schema: str, data_keys: List[str]) -> List[str]:
        """Get the columns to display based on schema and available keys."""
        # Find matching column config
        for prefix, columns in self.COLUMN_CONFIGS.items():
            if schema.startswith(prefix):
                # Filter to only columns that exist in data
                return [c for c in columns if c in data_keys]

        # Fallback: pick first 6 simple columns (no nested objects)
        return data_keys[:6]

    def _format_value(self, value: Any) -> str:
        """Format a value for table/list display."""
        if value is None:
            return "[dim]-[/dim]"
        if isinstance(value, bool):
            return "[green]✓[/green]" if value else "[dim]✗[/dim]"
        if isinstance(value, (list, dict)):
            if not value:
                return "[dim]-[/dim]"
            if isinstance(value, list):
                return f"[dim]{len(value)} items[/dim]"
            return "[dim]...[/dim]"
        # Handle enum values
        value_str = str(value)
        if "." in value_str and value_str.count(".") == 1:
            # Likely an enum like "EeroNetworkStatus.ONLINE"
            value_str = value_str.split(".")[-1].lower()
        return value_str

    def _render_table(self, data: Union[Dict, List], schema: str = "") -> None:
        """Render as Rich table with smart column selection."""
        if not data:
            self.console.print("[yellow]No data to display.[/yellow]")
            return

        # Handle single dict - render as key-value pairs
        if isinstance(data, dict):
            self._render_single_item(data, schema)
            return

        if not data:
            self.console.print("[yellow]No data to display.[/yellow]")
            return

        first_item = data[0]
        data_keys = list(first_item.keys())

        # Get columns to display
        columns = self._get_columns_for_schema(schema, data_keys)

        if not columns:
            self.console.print("[yellow]No displayable columns.[/yellow]")
            return

        # Create table
        table = Table(show_header=True, header_style="bold cyan", box=None)

        # Add columns
        for col in columns:
            col_name = col.replace("_", " ").title()
            table.add_column(col_name, no_wrap=True)

        # Add rows
        for item in data:
            row_values = [self._format_value(item.get(col)) for col in columns]
            table.add_row(*row_values)

        self.console.print(table)

    def _render_single_item(self, data: Dict, schema: str = "") -> None:
        """Render a single item as key-value pairs."""
        # Define important keys to show first
        priority_keys = ["id", "name", "display_name", "status", "ip", "public_ip", "isp_name"]

        # Get keys in order: priority first, then others
        all_keys = list(data.keys())
        ordered_keys = [k for k in priority_keys if k in all_keys]
        ordered_keys += [k for k in all_keys if k not in ordered_keys]

        # Only show non-null, non-complex values
        for key in ordered_keys:
            value = data.get(key)
            if value is None:
                continue
            if isinstance(value, (dict, list)) and not value:
                continue

            key_label = key.replace("_", " ").title()
            formatted = self._format_value(value)

            # Skip complex objects in single view
            if formatted in ["[dim]...[/dim]"]:
                continue

            self.console.print(f"[bold]{key_label}:[/bold] {formatted}")

    def _render_list(self, data: Union[Dict, List], schema: str = "") -> None:
        """Render as one-item-per-line list."""
        if not data:
            self.console.print("[yellow]No data to display.[/yellow]")
            return

        # Handle single dict
        if isinstance(data, dict):
            name = data.get("name") or data.get("display_name") or data.get("id", "Unknown")
            status = data.get("status", "")
            if status:
                self.console.print(f"{name} ({self._format_value(status)})")
            else:
                self.console.print(f"{name}")
            return

        # For list, show each item on its own line
        for item in data:
            if isinstance(item, dict):
                name = (
                    item.get("name")
                    or item.get("display_name")
                    or item.get("location")
                    or item.get("id", "Unknown")
                )
                status = item.get("status", "")
                ip = item.get("ip") or item.get("public_ip") or item.get("ip_address", "")

                parts = [str(name)]
                if status:
                    parts.append(f"({self._format_value(status)})")
                if ip:
                    parts.append(f"[dim]{ip}[/dim]")

                self.console.print(" ".join(parts))
            else:
                self.console.print(str(item))


# Standard table definitions for common resources
NETWORK_TABLE_COLUMNS = [
    {"name": "ID", "style": "dim"},
    {"name": "Name", "style": "cyan"},
    {"name": "Status", "style": "green"},
    {"name": "Public IP", "style": "blue"},
    {"name": "ISP", "style": "magenta"},
]

EERO_TABLE_COLUMNS = [
    {"name": "ID", "style": "dim"},
    {"name": "Name", "style": "cyan"},
    {"name": "Model", "style": "green"},
    {"name": "IP", "style": "blue"},
    {"name": "Status"},
    {"name": "Role"},
    {"name": "Connection", "style": "magenta"},
]

CLIENT_TABLE_COLUMNS = [
    {"name": "ID", "style": "dim"},
    {"name": "Name", "style": "cyan"},
    {"name": "IP", "style": "green"},
    {"name": "MAC", "style": "yellow"},
    {"name": "Status"},
    {"name": "Type"},
    {"name": "Connection"},
]

PROFILE_TABLE_COLUMNS = [
    {"name": "ID", "style": "dim"},
    {"name": "Name", "style": "cyan"},
    {"name": "Devices", "justify": "right"},
    {"name": "Paused"},
    {"name": "Schedule"},
]
