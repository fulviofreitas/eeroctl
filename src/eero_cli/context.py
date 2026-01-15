"""CLI context management.

This module provides a context object that is passed through Click commands
to share state like the client, output settings, and global flags.
"""

from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ContextManager, Dict, Optional

import click
from eero import EeroClient
from rich.console import Console

from .output import DetailLevel, OutputContext, OutputFormat, OutputManager, OutputRenderer

if TYPE_CHECKING:
    pass


@dataclass
class EeroCliContext:
    """Context object to pass shared resources to Click commands."""

    # Core components
    client: Optional[EeroClient] = None
    console: Console = field(default_factory=Console)
    err_console: Console = field(default_factory=lambda: Console(stderr=True))
    output_manager: Optional[OutputManager] = None

    # Network selection
    network_id: Optional[str] = None

    # Output settings
    output_format: str = "table"  # table, list, json
    detail_level: str = "brief"  # brief, full

    # Safety and interaction flags
    non_interactive: bool = False
    force: bool = False
    dry_run: bool = False
    quiet: bool = False
    no_color: bool = False

    # Debug/logging flags
    debug: bool = False
    verbose: bool = False

    # Retry/timeout settings
    timeout: Optional[int] = None
    retries: Optional[int] = None
    retry_backoff: Optional[int] = None

    # Additional storage for subcommand state
    _extra: Dict[str, Any] = field(default_factory=dict)

    # Cached renderer instance
    _renderer: Optional[OutputRenderer] = field(default=None, repr=False)

    def __post_init__(self):
        """Initialize derived components."""
        if self.output_manager is None:
            self.output_manager = OutputManager(self.console)

    @property
    def renderer(self) -> OutputRenderer:
        """Get the output renderer for this context."""
        if self._renderer is None:
            output_ctx = OutputContext(
                format=(
                    OutputFormat(self.output_format)
                    if self.output_format in ("table", "list", "json", "yaml", "text")
                    else OutputFormat.TABLE
                ),
                detail=(
                    DetailLevel(self.detail_level)
                    if self.detail_level in ("brief", "full")
                    else DetailLevel.BRIEF
                ),
                quiet=self.quiet,
                no_color=self.no_color,
                network_id=self.network_id,
            )
            self._renderer = OutputRenderer(output_ctx)
        return self._renderer

    def is_json_output(self) -> bool:
        """Check if output format is JSON."""
        return self.output_format == "json"

    def is_yaml_output(self) -> bool:
        """Check if output format is YAML."""
        return self.output_format == "yaml"

    def is_text_output(self) -> bool:
        """Check if output format is plain text."""
        return self.output_format == "text"

    def is_structured_output(self) -> bool:
        """Check if output format is a structured format (JSON, YAML, or text)."""
        return self.output_format in ("json", "yaml", "text")

    def status(self, message: str) -> ContextManager:
        """Return a status spinner context manager, but only for table output.

        For parseable outputs (json, yaml, list, text), returns a no-op context
        to avoid polluting the output with status messages.

        Args:
            message: Status message to display

        Returns:
            Status context manager or nullcontext
        """
        if self.output_format == "table":
            return self.console.status(message)
        return nullcontext()

    def render_structured(self, data: Any, schema: str) -> None:
        """Render data in the current structured format (JSON, YAML, or text).

        Args:
            data: Data to render (dict or list)
            schema: Schema identifier for envelope
        """
        if self.is_json_output():
            self.renderer.render_json(data, schema)
        elif self.is_yaml_output():
            self.renderer.render_yaml(data, schema)
        else:
            self.renderer.render_text(data, schema)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from extra storage."""
        return self._extra.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value in extra storage."""
        self._extra[key] = value

    def __getitem__(self, key: str) -> Any:
        """Get a value from extra storage using [] syntax."""
        return self._extra.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        """Set a value in extra storage using [] syntax."""
        self._extra[key] = value


def ensure_cli_context(ctx: click.Context) -> EeroCliContext:
    """Ensure the Click context has an EeroCliContext object.

    If ctx.obj is None or not an EeroCliContext, creates a new one.

    Args:
        ctx: Click context

    Returns:
        The EeroCliContext object
    """
    if ctx.obj is None or not isinstance(ctx.obj, EeroCliContext):
        ctx.obj = EeroCliContext()
    return ctx.obj


def get_cli_context(ctx: click.Context) -> EeroCliContext:
    """Get the EeroCliContext from a Click context.

    Args:
        ctx: Click context

    Returns:
        The EeroCliContext object

    Raises:
        RuntimeError: If no EeroCliContext is found
    """
    if ctx.obj is None:
        # Try to find it in parent contexts
        parent = ctx.parent
        while parent is not None:
            if isinstance(parent.obj, EeroCliContext):
                return parent.obj
            parent = parent.parent
        # Create a default one if not found
        ctx.obj = EeroCliContext()

    if not isinstance(ctx.obj, EeroCliContext):
        raise RuntimeError(
            f"Expected EeroCliContext but got {type(ctx.obj).__name__}. "
            "Make sure the CLI is properly initialized."
        )

    return ctx.obj


def create_cli_context(
    debug: bool = False,
    verbose: bool = False,
    output_format: str = "table",
    detail_level: str = "brief",
    network_id: Optional[str] = None,
    non_interactive: bool = False,
    force: bool = False,
    dry_run: bool = False,
    quiet: bool = False,
    no_color: bool = False,
    timeout: Optional[int] = None,
    retries: Optional[int] = None,
    retry_backoff: Optional[int] = None,
) -> EeroCliContext:
    """Create a new CLI context with the given settings.

    Factory function for creating an EeroCliContext with specific options.
    Used primarily by the main CLI entry point.

    Args:
        debug: Enable debug logging.
        verbose: Enable verbose output.
        output_format: Output format (table, list, json).
        detail_level: Detail level (brief, full).
        network_id: Network ID to use.
        non_interactive: Never prompt for input.
        force: Skip confirmation prompts.
        dry_run: Show what would happen without making changes.
        quiet: Suppress non-essential output.
        no_color: Disable colored output.
        timeout: Request timeout in seconds.
        retries: Number of retries for failed requests.
        retry_backoff: Backoff time between retries in milliseconds.

    Returns:
        A configured EeroCliContext instance.
    """
    console = Console(force_terminal=not no_color, no_color=no_color, quiet=quiet)

    return EeroCliContext(
        client=None,  # Will be initialized later
        console=console,
        output_manager=OutputManager(console),
        network_id=network_id,
        output_format=output_format,
        detail_level=detail_level,
        non_interactive=non_interactive,
        force=force,
        dry_run=dry_run,
        quiet=quiet,
        no_color=no_color,
        debug=debug,
        verbose=verbose,
        timeout=timeout,
        retries=retries,
        retry_backoff=retry_backoff,
    )
