"""Generic key/value rendering for phase-A command families.

Per the eero-api 8.0.1 migration plan §4 ("Enhancements") conventions
paragraph: "Where the response shape is undocumented, phase A ships the
generic key/value renderer for text/table and a raw data passthrough for
json/yaml; a dedicated table formatter is added only after a live sample
is captured (§5.3)."

`render_generic` is that renderer. It intentionally does no domain-specific
field selection: `table`/`list` go through `EeroCliContext.output_manager`
(`eeroctl.output.OutputManager`), whose `_render_single_item`/`_render_table`/
`_render_list` already print an arbitrary dict's keys generically; `text`
goes through `EeroCliContext.render_structured` too. `json`/`yaml` also go
through `render_structured`, but -- unlike `table`/`list`/`text` -- get the
raw `data` passed straight into the schema envelope untouched (the "raw data
passthrough" the plan calls for): `json`/`yaml` is the user's explicit
opt-in to the full payload, scripted with `jq` or similar, so it is never
redacted.

`table`/`list`/`text` render for a human on a terminal, and these commands
print *undocumented* API payloads verbatim -- there is no dedicated view
filtering the fields first (migration plan §4). A security review found
`account premium`/`network events` echoing values like a user token or an
email address in that path. `render_generic`/`render_generic_with_cursor`
therefore redact any value whose key matches
`const.GENERIC_RENDER_SENSITIVE_KEY_PATTERNS` (case-insensitive substring,
any nesting level) before handing the payload to `table`/`list`/`text`.

Each new phase-A `formatting/<domain>.py` module wraps this with a
per-command, schema-carrying function name (e.g. `print_entitlements_show`)
rather than calling `render_generic` directly from `commands/`, so the
schema string lives in exactly one place per command.
"""

from typing import Any, Optional

from ..const import GENERIC_RENDER_SENSITIVE_KEY_PATTERNS
from ..context import EeroCliContext
from ..output import OutputMeta

_REDACTED = "<redacted>"


def _is_sensitive_key(key: Any) -> bool:
    """Whether *key* matches one of `GENERIC_RENDER_SENSITIVE_KEY_PATTERNS`."""
    key_lower = str(key).lower()
    return any(pattern in key_lower for pattern in GENERIC_RENDER_SENSITIVE_KEY_PATTERNS)


def redact_sensitive(data: Any) -> Any:
    """Recursively redact sensitive values ahead of table/list/text rendering.

    Walks dicts and lists at any nesting level. A dict value whose key
    matches `GENERIC_RENDER_SENSITIVE_KEY_PATTERNS` is replaced with the
    literal string `"<redacted>"`, regardless of that value's own shape
    (so a nested dict/list under a `password` key is fully hidden, not just
    its own sensitive-looking children). Never called for `json`/`yaml`
    output -- see the module docstring.

    Args:
        data: The payload to redact (typically a dict, but tolerates any
            JSON-ish shape since it recurses structurally).

    Returns:
        A redacted deep copy; *data* itself is never mutated.
    """
    if isinstance(data, dict):
        return {
            key: (_REDACTED if _is_sensitive_key(key) else redact_sensitive(value))
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [redact_sensitive(item) for item in data]
    return data


def render_generic(cli_ctx: EeroCliContext, data: Any, schema: str) -> None:
    """Render an undocumented-shape API response with the generic renderer.

    Args:
        cli_ctx: The active CLI context (carries the effective output format).
        data: The already-extracted `data` payload (see `transformers.base.extract_data`).
        schema: Structured-output schema id, `eero.<noun>.<verb>/v1`.
    """
    if cli_ctx.is_json_output() or cli_ctx.is_yaml_output():
        cli_ctx.render_structured(data, schema)
        return

    safe_data = redact_sensitive(data)

    if cli_ctx.is_text_output():
        cli_ctx.render_structured(safe_data, schema)
        return

    assert cli_ctx.output_manager is not None  # set in EeroCliContext.__post_init__
    cli_ctx.output_manager.render(
        cli_ctx.output_format,
        safe_data,
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
