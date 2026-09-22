# Live-sample fixtures (phase A)

This directory holds redacted, real-network output samples for the
eero-api 8.0.1 phase-A read commands, captured per the migration plan
§5.3 process below. They exist because several phase-A commands ship
against **undocumented** response shapes (no OpenAPI/Swagger spec, no
public schema) -- see `src/eeroctl/formatting/generic.py`'s module
docstring -- and print them with the generic key/value renderer until a
live sample lets a dedicated, field-selecting formatter be written and
tested.

## What's in here

- `<command-slug>.json` -- one file per captured command, e.g.
  `entitlements-show.json`, `usage-summary.json`, `eero-connections.json`.
  Each file is:

  ```json
  {
    "command": ["eero", "--output", "json", "network", "entitlements", "show"],
    "exit_code": 0,
    "stdout": { "...": "redacted response body" },
    "stderr": ""
  }
  ```

- `SUMMARY.md` -- a table of every command run in the most recent capture,
  its exit code, and the byte size of its output file (or `skipped` with a
  reason, for per-eero/per-device/per-profile commands that had no target
  on the capturing network).

## Capture procedure

1. Authenticate the CLI against a real account (`eero auth login`) with a
   network you're comfortable using for this -- the script only *reads*,
   it never calls a write/mutating command.
2. Run the capture script from the repo root:

   ```bash
   uv run python scripts/capture-live-samples.py [--network-id NETWORK_ID] [--out tests/fixtures/live]
   ```

   `--network-id` defaults to the CLI's own preferred-network resolution
   (same as running any `eero` command with no `--network-id`).
3. The script prints a `Captured N reads, M skipped, K failed` line to
   stderr. Investigate before committing if `K` (failed) is non-zero --
   that means a read exited with a code other than 0 (success), 5
   (not-found), 11 (premium-required), or 12 (feature-unavailable), i.e.
   something crashed rather than just being unavailable on this particular
   account/network/hardware.
4. **Read every file in the diff before committing.** The redaction layer
   (`redact_payload` in the script, unit-tested in
   `tests/cli/test_capture_live_samples.py`) is a safety net, not a
   substitute for a human skim:
   - Key-based redaction reuses `eeroctl.formatting.generic.redact_sensitive`
     (itself derived from the SDK's `eero.logging._ZERO_VISIBILITY_PATTERNS`,
     see `src/eeroctl/const.py`) -- any dict value under a
     password/token/session/credential/email/phone-shaped key is replaced
     with `<redacted>`.
   - Value-pattern redaction then masks MAC addresses, device/eero serial
     numbers, email addresses, phone numbers, and IPv4/IPv6 addresses
     found in any remaining string value, regardless of its key -- this is
     the layer that catches these shapes when they show up embedded in an
     undocumented field (e.g. inside an `events`/`notifications` message
     string).
   - Neither layer understands every possible undocumented field. If you
     see something in a captured file that looks like it shouldn't be
     there -- a raw name, a precise geolocation, anything else personal --
     redact it by hand (`<redacted>` is the convention) before committing,
     and consider whether the script's patterns should be extended.
5. Commit the updated `tests/fixtures/live/*.json` and `SUMMARY.md` files.
   Treat this like any other fixture change: review the diff, don't just
   trust the tool.

## What these files are *for*

These are **inputs for future work**, not test fixtures consumed by the
current test suite:

- Writing dedicated `formatting/<domain>.py` view functions (replacing
  `render_generic`) for the phase-A commands whose response shape is
  still only "assumed" from SDK docstrings/type hints rather than
  confirmed against a live response.
- Writing `transformers/<domain>.py` extraction tests against a real
  shape instead of a hand-built mock.
- Documenting the actual (vs. assumed) field names in the relevant
  command module's docstring, the same way `network/guest.py`'s
  `guest_show` docstring already flags its own "unverified shape" gap.

They are deliberately **not** wired into `conftest.py` fixtures or
imported by any test module -- a live capture reflects one account's data
at one point in time (plan/feature flags, hardware mix, locale) and isn't
a stable contract to assert against in CI.

## Re-running the capture

Nothing here is meant to be captured once and frozen forever. Re-run the
script whenever a phase-A command's assumed shape needs re-verifying (a
new eero-api release, a bug report suggesting the shape has drifted,
picking up the next item on the migration plan's dedicated-formatter
backlog) -- just repeat the procedure above and review the new diff before
committing.
