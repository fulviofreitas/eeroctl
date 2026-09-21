"""Generic key/value rendering for phase-A command families.

Per the eero-api 8.0.1 migration plan §4 ("Enhancements") conventions
paragraph: "Where the response shape is undocumented, phase A ships the
generic key/value renderer for text/table and a raw data passthrough for
json/yaml; a dedicated table formatter is added only after a live sample
is captured (§5.3)."

`render_generic` is that renderer. It intentionally does no domain-specific
field selection: `table`/`list` go through `EeroCliContext.output_manager`
(`eeroctl.output.OutputManager`), whose `_render_single_item`/`_render_table`/
`_render_list` already print an arbitrary dict's keys generically; `json`/
`yaml`/`text` go through `EeroCliContext.render_structured`, which passes
`data` straight into the schema envelope untouched (the "raw data
passthrough" the plan calls for).

Each new phase-A `formatting/<domain>.py` module wraps this with a
per-command, schema-carrying function name (e.g. `print_entitlements_show`)
rather than calling `render_generic` directly from `commands/`, so the
schema string lives in exactly one place per command.
"""

from typing import Any, Optional

from ..context import EeroCliContext
from ..output import OutputMeta


def render_generic(cli_ctx: EeroCliContext, data: Any, schema: str) -> None:
    """Render an undocumented-shape API response with the generic renderer.

    Args:
        cli_ctx: The active CLI context (carries the effective output format).
        data: The already-extracted `data` payload (see `transformers.base.extract_data`).
        schema: Structured-output schema id, `eero.<noun>.<verb>/v1`.
    """
    if cli_ctx.is_structured_output():
        cli_ctx.render_structured(data, schema)
        return

    assert cli_ctx.output_manager is not None  # set in EeroCliContext.__post_init__
    cli_ctx.output_manager.render(
        cli_ctx.output_format,
        data,
        schema,
        {"network_id": cli_ctx.network_id},
    )


def render_generic_with_cursor(
    cli_ctx: EeroCliContext,
    data: Any,
    schema: str,
    *,
    next_cursor: Optional[str],
    cursor_label: str = "next_cursor",
) -> None:
    """`render_generic`, plus a pagination cursor surfaced per format.

    For `json`/`yaml`, the cursor is added to the envelope's top-level `meta`
    object under *cursor_label* (e.g. `network events --cursor <value from
    meta.next_cursor>` chains pages). For `table`/`list`/`text`, there is no
    `meta` object in the rendered output, so the cursor is printed as a dim
    note line instead.

    Args:
        cli_ctx: The active CLI context.
        data: The already-extracted `data` payload.
        schema: Structured-output schema id.
        next_cursor: The pagination cursor for the next page, or `None` if
            there isn't one (e.g. the response did not include one).
        cursor_label: The `meta`/note key to use.
    """
    if next_cursor is None:
        render_generic(cli_ctx, data, schema)
        return

    if cli_ctx.is_json_output():
        meta = OutputMeta(network_id=cli_ctx.network_id, extra={cursor_label: next_cursor})
        cli_ctx.renderer.render_json(data, schema, meta)
    elif cli_ctx.is_yaml_output():
        meta = OutputMeta(network_id=cli_ctx.network_id, extra={cursor_label: next_cursor})
        cli_ctx.renderer.render_yaml(data, schema, meta)
    else:
        render_generic(cli_ctx, data, schema)
        if not cli_ctx.quiet:
            cli_ctx.console.print(f"[dim]{cursor_label}: {next_cursor}[/dim]")
