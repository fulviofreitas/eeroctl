#!/usr/bin/env python3
"""Live-sample capture script for the eero-api 8.0.1 phase-A read checklist.

Per the eero-api 8.0.1 migration plan §5.3, every phase-A read-only command
is run once by a maintainer against a *real* network, captured with
``--output json``, redacted, and committed to ``tests/fixtures/live/`` --
raw material for the dedicated formatters that will eventually replace the
generic key/value renderer (see ``src/eeroctl/formatting/generic.py`` and
``tests/fixtures/live/README.md``).

This script is stdlib-only for its own control flow (``argparse``, ``json``,
``re``, ``subprocess``, ``pathlib``, ...); the one non-stdlib import is
``eeroctl.formatting.generic.redact_sensitive`` itself, reused on purpose so
the capture script never drifts out of step with the CLI's own key-based
redaction rules (imported lazily and defensively -- see
``_redact_sensitive_keys`` below).

It runs every phase-A read command exactly once, each as its own
``python -m eeroctl.main ...`` subprocess (the exact code path a real
operator invokes, not an in-process import of command callbacks), with
``--output json``. For each item it records::

    {"command": [...], "exit_code": int, "stdout": <parsed-json-or-text>,
     "stderr": "..."}

redacts the payload (see ``redact_payload``), and writes one
``<command-slug>.json`` file per item plus a single ``SUMMARY.md`` table.

Never sends anything anywhere except to the local ``eero`` CLI subprocess,
which itself talks only to the already-authenticated Eero cloud API -- the
same one every other eeroctl command talks to. Nothing here makes an
outbound network call of its own, uploads anything, or logs to a remote
service.

Usage::

    uv run python scripts/capture-live-samples.py \\
        [--network-id NETWORK_ID] [--out tests/fixtures/live]

Exit status: non-zero if any invoked read command exited with a code other
than one of ``ACCEPTABLE_EXIT_CODES`` (0 success, 5 not-found, 11
premium-required, 12 feature-unavailable -- all expected, non-crash outcomes
for *some* accounts/networks/hardware). A bootstrap step that can't find a
target for a per-eero/per-device/per-profile command (e.g. a network with no
secondary Eeros) skips that command instead of running it at all; skips are
reported in ``SUMMARY.md`` but never count as a failure.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

# Exit codes considered "acceptable" outcomes for a live read run against an
# arbitrary account/network/hardware mix -- see src/eeroctl/exit_codes.py.
#   0  SUCCESS
#   5  NOT_FOUND             (e.g. a wrong/stale id -- shouldn't happen here,
#                              but a network with the feature entirely absent
#                              can surface this on some commands)
#   11 PREMIUM_REQUIRED      (account isn't on Eero Plus)
#   12 FEATURE_UNAVAILABLE   (hardware/network doesn't support the feature)
# Anything else (auth errors, crashes, usage errors, network errors, ...) is
# a real problem the operator needs to see, so the script exits non-zero.
ACCEPTABLE_EXIT_CODES = frozenset({0, 5, 11, 12})

DEFAULT_OUT_DIR = Path("tests/fixtures/live")
DEFAULT_INSIGHT_TYPE = "blocked"


# ==================== Redaction ====================
#
# Two layers, applied in order:
#
#   1. Key-based: reuse `eeroctl.formatting.generic.redact_sensitive`
#      verbatim, so this script inherits the exact same
#      credential/session/contact-info key patterns the CLI's own
#      table/text/list renderer uses (itself derived from the SDK's
#      `eero.logging._ZERO_VISIBILITY_PATTERNS`, see
#      `src/eeroctl/const.py`). Any dict value whose key looks like a
#      password/token/session/email/phone field is fully replaced.
#
#   2. Value-pattern based: regexes applied to every remaining *string*
#      value, regardless of its key, masking anything that looks like a MAC
#      address, a device/eero serial number, an email address, a phone
#      number, or an IPv4/IPv6 address. This is deliberately independent of
#      key names -- undocumented phase-A payloads (this whole capture
#      exercise exists because the shapes are undocumented, migration plan
#      §5.3) may embed these under innocuous-looking keys (e.g. a "value" or
#      "detail" field inside an events/notifications payload).
#
# Layer 2 is intentionally conservative in the "over-redact rather than
# leak" direction: the serial-number pattern in particular will also catch
# other alphanumeric identifiers that happen to mix letters and digits at
# the same length. That is an accepted trade-off for fixtures that get
# committed to the repository -- see tests/fixtures/live/README.md.

_MAC_COLON_RE = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")
_MAC_BARE_RE = re.compile(r"\b[0-9A-Fa-f]{12}\b")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\-.\s()]{7,}\d)(?!\d)")
_IPV4_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
# Candidate spans for IPv6 addresses: runs of hex digits and colons (the
# character set every IPv6 textual form -- full, "::"-compressed, or
# leading/trailing "::" -- is built from). Actual validation is delegated to
# `ipaddress.ip_address` (stdlib) rather than hand-rolled further, since a
# purely regex-based IPv6 matcher is notoriously prone to picking the wrong
# alternation branch around "::" and silently leaking a partial prefix
# (e.g. only redacting "fe80::" out of "fe80::1ff:fe23:4567:890a").
# Known limitation: `\b` requires a word-char/non-word-char transition, so
# an address that starts with "::" and is otherwise very short (e.g. the
# loopback "::1") has no leading boundary to match from and is left
# unmasked. Accepted: "::1" is a well-known constant, not user data, and
# every non-trivial (globally routable or link-local) address -- the shapes
# that actually carry information worth redacting -- starts with enough
# leading hex digits to have a normal boundary.
_IPV6_CANDIDATE_RE = re.compile(r"\b[0-9A-Fa-f:]{2,45}\b")
# Alphanumeric tokens 8-20 chars long, mixing at least one letter and one
# digit, no separators -- the shape of an Eero device/node serial number.
# Deliberately checked *before* `_PHONE_RE`: a serial that happens to embed
# a long pure-digit run (e.g. "SN1234567890XY") would otherwise have that
# run consumed by the phone-number pattern first, breaking the token apart
# before the serial pattern gets a chance to match the whole thing. Checked
# *after* the MAC patterns so a bare 12-hex-digit MAC is labelled
# "<mac-redacted>" rather than "<serial-redacted>".
_SERIAL_RE = re.compile(
    r"\b(?=[A-Za-z0-9]{8,20}\b)(?=[A-Za-z0-9]*[0-9])(?=[A-Za-z0-9]*[A-Za-z])[A-Za-z0-9]{8,20}\b"
)


def _mask_ipv6(value: str) -> str:
    """Replace every substring of *value* that `ipaddress` parses as IPv6."""
    import ipaddress

    def _replace(match: re.Match[str]) -> str:
        token = match.group(0)
        if token.count(":") < 2:
            return token
        try:
            ipaddress.IPv6Address(token)
        except ValueError:
            return token
        return "<ipv6-redacted>"

    return _IPV6_CANDIDATE_RE.sub(_replace, value)


_VALUE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (_EMAIL_RE, "<email-redacted>"),
    (_MAC_COLON_RE, "<mac-redacted>"),
    (_IPV4_RE, "<ipv4-redacted>"),
    (_MAC_BARE_RE, "<mac-redacted>"),
    (_SERIAL_RE, "<serial-redacted>"),
    (_PHONE_RE, "<phone-redacted>"),
)


def _redact_sensitive_keys(data: Any) -> Any:
    """Apply the CLI's own key-based redaction (see module docstring).

    Imported lazily so this script can still run its value-pattern masking
    (and be unit-tested) even if ``eeroctl`` isn't importable for some
    reason; falls back to a no-op key pass in that case.
    """
    try:
        from eeroctl.formatting.generic import redact_sensitive
    except ImportError:  # pragma: no cover - defensive, not expected in CI
        return data
    return redact_sensitive(data)


def _mask_string(value: str) -> str:
    """Mask MAC/serial/email/phone/IP substrings anywhere in *value*."""
    value = _mask_ipv6(value)
    for pattern, replacement in _VALUE_PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def _mask_value_patterns(data: Any) -> Any:
    """Recursively apply `_mask_string` to every string value in *data*."""
    if isinstance(data, dict):
        return {key: _mask_value_patterns(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_mask_value_patterns(item) for item in data]
    if isinstance(data, str):
        return _mask_string(data)
    return data


def redact_payload(data: Any) -> Any:
    """Redact *data* ahead of writing it to a committed fixture file.

    Applies key-based redaction first (`_redact_sensitive_keys`), then
    value-pattern masking (`_mask_value_patterns`) over whatever remains.
    Never mutates *data*; both layers return new structures.
    """
    return _mask_value_patterns(_redact_sensitive_keys(data))


# ==================== Command execution ====================


@dataclass
class CaptureItem:
    """One phase-A read command to run and capture."""

    slug: str
    argv: list[str]
    # Optional predicate: returns False (and a reason) to skip this item,
    # e.g. when no bootstrap target (eero/device/profile) was found.
    skip_reason: Optional[str] = None


@dataclass
class CaptureResult:
    slug: str
    command: list[str]
    exit_code: Optional[int]
    stdout: Any
    stderr: str
    skipped: bool = False
    skip_reason: Optional[str] = None
    byte_count: int = 0


_REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_cli(python: str, argv: list[str]) -> tuple[int, str, str]:
    """Run ``python -m eeroctl.main <argv>`` and return (exit_code, stdout, stderr).

    Invoking via ``-m eeroctl.main`` (rather than the installed ``eero``/
    ``eeroctl`` console scripts) exercises the exact in-repo code path
    without depending on the console scripts being on ``PATH``. Runs with
    ``cwd`` pinned to the repository root so this resolves the same way
    regardless of the caller's current directory.
    """
    proc = subprocess.run(
        [python, "-m", "eeroctl.main", *argv],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_REPO_ROOT),
    )
    return proc.returncode, proc.stdout, proc.stderr


def _parse_stdout(stdout: str) -> Any:
    """Best-effort JSON-parse *stdout*; falls back to the raw text."""
    stripped = stdout.strip()
    if not stripped:
        return ""
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return stdout


def _first_id(items: Any) -> Optional[str]:
    """Return the ``id`` of the first item in a list-command JSON payload.

    Every phase-A ``<noun> list`` command's structured output is a list of
    normalized dicts carrying an ``"id"`` key (`network list`, `eero list`,
    `device list`, `profile list` -- see e.g.
    ``src/eeroctl/commands/eero/base.py``'s ``eero_list``). Tolerates the
    schema envelope wrapping the list under a ``"data"`` key.
    """
    if isinstance(items, dict):
        items = items.get("data", items)
    if not isinstance(items, list) or not items:
        return None
    first = items[0]
    if not isinstance(first, dict):
        return None
    value = first.get("id")
    return str(value) if value is not None else None


def _default_channels_window() -> tuple[str, str]:
    """A 24h ``--start``/``--end`` pair ending now, ISO-8601 UTC with a
    trailing ``Z`` (the format ``ISO8601_TIMESTAMP`` in ``options.py``
    expects -- ``network channels`` has no cadence-based default, unlike
    the insights/data-usage families, see ``commands/network/events.py``).
    """
    end = datetime.now(timezone.utc).replace(microsecond=0)
    start = end - timedelta(hours=24)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return start.strftime(fmt), end.strftime(fmt)


# ==================== Manifest ====================


def _global_flags(network_id: Optional[str]) -> list[str]:
    """Global ``--output json`` [``--network-id``] flags, placed before the
    subcommand path -- both are top-level options on the ``cli`` group
    (``src/eeroctl/main.py``) that every leaf command falls back to when it
    doesn't set its own (``apply_options``, ``src/eeroctl/options.py``).
    """
    flags = ["--output", "json"]
    if network_id:
        flags += ["--network-id", network_id]
    return flags


def build_manifest(network_id_flag: Optional[str], python: str) -> list[CaptureItem]:
    """Build the ordered list of phase-A read commands to capture.

    Bootstraps ``network id`` (if not given on the CLI), the first eero,
    first device, and first profile by actually invoking the corresponding
    ``list``/``show`` commands up front -- the same commands the checklist
    calls "baseline" reads, run early here because later items need their
    ids.
    """
    gf = _global_flags(network_id_flag)

    manifest: list[CaptureItem] = []

    # ---- Baseline discovery reads (also part of the checklist) ----
    manifest.append(CaptureItem("network-show", [*gf, "network", "show"]))
    manifest.append(CaptureItem("eero-list", [*gf, "eero", "list"]))
    manifest.append(CaptureItem("device-list", [*gf, "device", "list"]))
    manifest.append(CaptureItem("profile-list", [*gf, "profile", "list"]))

    # Run the bootstrap reads immediately so later items can use their ids.
    eero_id: Optional[str] = None
    device_id: Optional[str] = None
    profile_id: Optional[str] = None

    for item in list(manifest):
        code, out, _err = _run_cli(python, item.argv)
        parsed = _parse_stdout(out)
        if item.slug == "eero-list" and code == 0:
            eero_id = _first_id(parsed)
        elif item.slug == "device-list" and code == 0:
            device_id = _first_id(parsed)
        elif item.slug == "profile-list" and code == 0:
            profile_id = _first_id(parsed)

    channels_start, channels_end = _default_channels_window()

    manifest.extend(
        [
            CaptureItem("entitlements-show", [*gf, "network", "entitlements", "show"]),
            CaptureItem("entitlements-upsell", [*gf, "network", "entitlements", "upsell"]),
            CaptureItem(
                "entitlements-capabilities", [*gf, "network", "entitlements", "capabilities"]
            ),
            CaptureItem("account-premium", [*gf, "account", "premium"]),
            CaptureItem("network-events", [*gf, "network", "events"]),
            CaptureItem("network-scan", [*gf, "network", "scan"]),
            CaptureItem(
                "network-channels",
                [
                    *gf,
                    "network",
                    "channels",
                    "--start",
                    channels_start,
                    "--end",
                    channels_end,
                ],
            ),
            CaptureItem("network-permissions", [*gf, "network", "permissions"]),
            CaptureItem("notifications-show", [*gf, "network", "notifications", "show"]),
            CaptureItem("notifications-unread", [*gf, "network", "notifications", "unread"]),
            CaptureItem("notifications-history", [*gf, "network", "notifications", "history"]),
            CaptureItem("dns-policy-show", [*gf, "network", "dns", "policy", "show"]),
            CaptureItem("members-list", [*gf, "network", "members", "list"]),
            CaptureItem("members-invites", [*gf, "network", "members", "invites"]),
            CaptureItem("dhcp-show", [*gf, "network", "dhcp", "show"]),
            CaptureItem("wpa3-show", [*gf, "network", "wpa3", "show"]),
            CaptureItem("security-show", [*gf, "network", "security", "show"]),
            CaptureItem(
                "security-fast-transition-show",
                [*gf, "network", "security", "fast-transition", "show"],
            ),
            CaptureItem(
                "power-saving-schedules-list",
                [*gf, "network", "power-saving", "schedules", "list"],
            ),
            CaptureItem("backup-show", [*gf, "network", "backup", "show"]),
            CaptureItem("backup-status", [*gf, "network", "backup", "status"]),
            CaptureItem(
                "backup-access-points-list",
                [*gf, "network", "backup", "access-points", "list"],
            ),
            CaptureItem(
                "backup-access-points-discover",
                [*gf, "network", "backup", "access-points", "discover"],
            ),
            CaptureItem("subnets-show", [*gf, "network", "subnets", "show"]),
            CaptureItem("wan-multistaticip-show", [*gf, "network", "wan", "multistaticip", "show"]),
            (
                CaptureItem(
                    "eero-connections",
                    [*gf, "eero", "connections", eero_id],
                )
                if eero_id
                else CaptureItem(
                    "eero-connections", [], skip_reason="no eero found (empty 'eero list')"
                )
            ),
            (
                CaptureItem("eero-support", [*gf, "eero", "support", eero_id])
                if eero_id
                else CaptureItem(
                    "eero-support", [], skip_reason="no eero found (empty 'eero list')"
                )
            ),
            (
                CaptureItem(
                    "device-labels-show",
                    [*gf, "device", "labels", "show", device_id],
                )
                if device_id
                else CaptureItem(
                    "device-labels-show", [], skip_reason="no device found (empty 'device list')"
                )
            ),
            (
                CaptureItem("network-ouicheck", [*gf, "network", "ouicheck", eero_id])
                if eero_id
                else CaptureItem(
                    "network-ouicheck", [], skip_reason="no eero found (empty 'eero list')"
                )
            ),
            CaptureItem("network-transfer", [*gf, "network", "transfer"]),
            CaptureItem(
                "speedtest-history", [*gf, "network", "speedtest", "history", "--limit", "3"]
            ),
            CaptureItem(
                "activity-devices",
                [
                    *gf,
                    "activity",
                    "devices",
                    "--cadence",
                    "hourly",
                    "--insight-type",
                    DEFAULT_INSIGHT_TYPE,
                ],
            ),
            CaptureItem(
                "activity-profiles",
                [
                    *gf,
                    "activity",
                    "profiles",
                    "--cadence",
                    "hourly",
                    "--insight-type",
                    DEFAULT_INSIGHT_TYPE,
                ],
            ),
            CaptureItem(
                "usage-summary", [*gf, "network", "usage", "summary", "--cadence", "daily"]
            ),
            CaptureItem(
                "usage-breakdown", [*gf, "network", "usage", "breakdown", "--cadence", "daily"]
            ),
            CaptureItem(
                "usage-devices", [*gf, "network", "usage", "devices", "--cadence", "daily"]
            ),
            CaptureItem("usage-eeros", [*gf, "network", "usage", "eeros", "--cadence", "daily"]),
            CaptureItem(
                "usage-unprofiled",
                [*gf, "network", "usage", "unprofiled", "--cadence", "daily"],
            ),
            CaptureItem("usage-report-show", [*gf, "network", "usage", "report", "show"]),
            CaptureItem("guest-show", [*gf, "network", "guest", "show"]),
            (
                CaptureItem(
                    "profile-schedule-show",
                    [*gf, "profile", "schedule", "show", profile_id],
                )
                if profile_id
                else CaptureItem(
                    "profile-schedule-show",
                    [],
                    skip_reason="no profile found (empty 'profile list')",
                )
            ),
            (
                CaptureItem("eero-nightlight-show", [*gf, "eero", "nightlight", "show", eero_id])
                if eero_id
                else CaptureItem(
                    "eero-nightlight-show", [], skip_reason="no eero found (empty 'eero list')"
                )
            ),
        ]
    )

    return manifest


# ==================== Orchestration ====================


def capture_all(manifest: list[CaptureItem], python: str, out_dir: Path) -> list[CaptureResult]:
    """Run every (non-skipped) item in *manifest* and write its fixture file."""
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[CaptureResult] = []

    for item in manifest:
        if item.skip_reason is not None:
            results.append(
                CaptureResult(
                    slug=item.slug,
                    command=item.argv,
                    exit_code=None,
                    stdout=None,
                    stderr="",
                    skipped=True,
                    skip_reason=item.skip_reason,
                )
            )
            continue

        code, out, err = _run_cli(python, item.argv)
        parsed = _parse_stdout(out)
        redacted = redact_payload(parsed)

        masked_command = _mask_value_patterns(["eero", *item.argv])
        payload = {
            "command": masked_command,
            "exit_code": code,
            "stdout": redacted,
            "stderr": _mask_string(err),
        }
        out_path = out_dir / f"{item.slug}.json"
        text = json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"
        out_path.write_text(text)

        results.append(
            CaptureResult(
                slug=item.slug,
                command=masked_command,
                exit_code=code,
                stdout=redacted,
                stderr=payload["stderr"],
                byte_count=len(text.encode("utf-8")),
            )
        )

    return results


def write_summary(results: list[CaptureResult], out_dir: Path) -> None:
    lines = [
        "# Live-sample capture summary",
        "",
        "Generated by `scripts/capture-live-samples.py`. Every row is one",
        "phase-A read command, run once against a real network and redacted",
        "before being written to this directory (see `README.md`).",
        "",
        "| Command | Exit code | Bytes |",
        "| --- | --- | --- |",
    ]
    for result in results:
        if result.skipped:
            lines.append(f"| `{result.slug}` | skipped ({result.skip_reason}) | - |")
        else:
            lines.append(f"| `{result.slug}` | {result.exit_code} | {result.byte_count} |")
    (out_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument(
        "--network-id",
        default=None,
        help="Network id to operate on (default: the SDK/CLI's own preferred-network logic).",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT_DIR),
        help=f"Output directory for captured fixtures (default: {DEFAULT_OUT_DIR}).",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python interpreter used to invoke 'python -m eeroctl.main' (default: current).",
    )
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    manifest = build_manifest(args.network_id, args.python)
    results = capture_all(manifest, args.python, out_dir)
    write_summary(results, out_dir)

    failures = [r for r in results if not r.skipped and r.exit_code not in ACCEPTABLE_EXIT_CODES]
    for failure in failures:
        print(
            f"FAILED: {' '.join(failure.command)} exited {failure.exit_code}",
            file=sys.stderr,
        )
        if failure.stderr:
            print(failure.stderr, file=sys.stderr)

    skipped = [r for r in results if r.skipped]
    for skip in skipped:
        print(f"skipped: {skip.slug} ({skip.skip_reason})", file=sys.stderr)

    print(
        f"Captured {len(results) - len(skipped)} reads, {len(skipped)} skipped, "
        f"{len(failures)} failed. Output: {out_dir}",
        file=sys.stderr,
    )

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
