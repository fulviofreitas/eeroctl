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

from typing import Any

from ..context import EeroCliContext


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
