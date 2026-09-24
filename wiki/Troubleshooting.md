# 🔧 Troubleshooting

Common issues and their solutions when using eeroctl. Every error maps to a fixed
exit code — the full table is in [CLI Reference → Exit Codes](CLI-Reference#-exit-codes).

---

## macOS: "operation not permitted" when activating venv

If you see this error when trying to activate the virtual environment:

```
(eval):source:1: operation not permitted: venv/bin/activate
```

This is caused by macOS quarantine attributes on downloaded files. Fix it by running:

```bash
xattr -cr venv
```

> 💡 **Tip:** If using `uv`, you won't encounter this issue as `uv` manages its own environment.

---

## Authentication Issues

### "Authentication required" / "Session invalid" (exit 3)

There is no client-side session expiry any more: the token is stored, and the API
decides whether it is still valid. `eero auth status` makes one live call and reports
**Valid**, **Invalid** (the API rejected the stored token) or **Not authenticated**
(nothing stored). Any command that hits a rejected or missing token exits `3`, whichever
entry point it uses.

Re-authenticate:

```bash
eero auth login --force
```

For scripts, `eero auth status --check` exits `3` in the same situations and `0`
otherwise; `--offline` skips the network call and only reports what is stored.

### "Not authenticated" right after upgrading to 3.0.0

The upgrade moves the token (see [Migration → Credentials](Migration#credentials)).
Check where it went:

```bash
eero auth status --offline --output list
```

- `keyring_available True` and `status stored_not_verified`: the token is in the
  keyring; drop `--offline` to confirm it works.
- `keyring_available False` and `cookie_file` absent: the promotion into the keyring
  failed and the file was cleaned up. Run `eero auth login`, or restore
  `cookies.json.pre-v8.bak` as described in [Migration → Rollback](Migration#rollback).

### Clear All Credentials

To completely reset authentication (also removes `config.json` and the
`.pre-v8.bak` backup):

```bash
eero auth clear --force
```

When the backup existed, "removed pre-v8 credential backup" is printed on stderr.

### Keyring errors on Linux

If `auth status` shows `Keyring Available: No` on a headless box, no Secret Service
is running. Either start one, or switch to file storage:

```bash
eero auth login --no-keyring
```

As of eero-api 8.0.3, a plain `eero auth login` on a machine with no keyring backend
at all falls back to file storage automatically: the SDK verifies the keyring write
with a read-back and only skips the file fallback when that verification succeeds.
Earlier SDK versions could report `Login successful!` while a non-functional keyring
backend silently discarded the session, leaving every following command
unauthenticated with no error at login time. `--no-keyring` remains the more explicit
choice on a system you already know has no keyring support.

---

## Permission and Feature Errors

### "Permission denied" (exit 4)

The account is logged in but the API refused the operation (`HTTP 403`). This is
role-based — a network *guest* or *admin* cannot do everything the *owner* can. The
message ends with `(error code: …)` when the API supplied one; `error.access.denied`
is the usual value. Some reads (for example pending invites) return 403 for every
non-owner account; there is nothing to fix on your side.

Check what your account may do before filing a bug:

```bash
eero network permissions            # role + per-capability map
eero -o json network permissions | jq -r '.data.role'
```

`network members invites` is the known case: it prints "Not permitted for this
account." and exits `4` on accounts that can nevertheless run `members list`.

### "requires Eero Plus" (exit 11) / "is not available" (exit 12)

`11` means the feature needs an Eero Plus subscription (activity, backup internet,
DNS policy). `12` means the hardware or network does not have it — the classic case
is `eero eero nightlight …` on anything but a Beacon.

Absent-but-optional configuration is **not** an error: reads such as
`network wan multistaticip show` print "not configured" and exit `0` with
`"data": null` in structured output.

### "This client version is blocked by the API" (exit 13)

The eero API refused to talk to this client version at all. Retrying will not help.
Upgrade eeroctl (which upgrades eero-api); if the latest release is blocked too, open
an issue against [eero-api](https://github.com/fulviofreitas/eero-api/issues).

---

## Network Connection Issues

### No Networks Found

If `eero network list` returns no networks:

1. Verify you're logged in: `eero auth status`
2. Check your Eero account has networks associated
3. Try re-authenticating: `eero auth login --force`

### "Network error: could not reach the eero API" (exit 14)

DNS failure, unreachable host or a reset connection — the request never got an
answer. Check your own connectivity first. eeroctl does **not** retry by default; for
flaky links, allow extra attempts on read-only requests that fail with a transport
error or a 5xx:

```bash
eero --get-retries 3 network list
# or: export EEROCTL_GET_RETRIES=3
# or: "get_retries": 3 in config.json
```

Writes are never retried, on purpose: a write whose result you did not see must be
checked with its read command, not re-sent.

### "Request timed out" (exit 7)

The API accepted the connection but did not answer in time. Retry once; if it persists,
the eero API is likely degraded — wait a few minutes.

### "Rate limited" (exit 1)

Too many requests in a short window. Wait before retrying; eeroctl never retries a
429 itself. (In 2.x this exited `7`; 3.0.0 keeps `7` for timeouts only.)

---

## Write Commands

### "This write has not been verified against a live network"

Some settings endpoints have not been exercised against a real network by the eero-api
maintainers. eeroctl still sends them, but tells you so — once before the
confirmation prompt (also under `--force`) and once as
`note: unverified write (<operation>); verify with `<read command>`` on stderr when
the request goes out — and names the read command to confirm the result with. The
same note appears in `meta.warnings` for `json`/`yaml` output. It is information, not
an error: exit code is `0` if the API accepted the request. `--quiet` hides the
stderr note; `--debug` shows the SDK's raw `WARNING:eero.api.…` line instead.

If the read-back shows the change did not apply, do not loop the write. Open an issue
with the command and the read-back output; the list of affected commands is in
[Migration → Unverified commands](Migration#unverified-commands).

### "Applying this change reboots every eero on the network"

DNS, security, SQM, MLO and DHCP writes, `network reboot` and `eero updates apply`
restart the whole mesh a few minutes after the command returns. The prompt asks you
to type `REBOOT`; `--force` skips the prompt but still prints the warning. Plan the
outage — every client loses Wi-Fi for a couple of minutes.

### "Already configured as requested; no change made." (exit 0, nothing written)

eeroctl read the current value and it already matched; the line ends with "Check
with `<read command>`." (DNS writes say "DNS already configured as requested; no
change made."). Pass `--force` to write anyway.

### "Write was not applied." (exit 1)

The API answered a read-first write with a non-2xx envelope. Nothing is retried;
run the read command named in the prompt, then re-run once by hand if the setting
really did not change.

### Exit 8 in a script

The command needed confirmation and `--non-interactive` was set. Add `--force` (or
`EEROCTL_FORCE=1`) once you have confirmed the script is meant to make that change.

---

## CLI Output Issues

### Disable Colors

If your terminal doesn't support colors or you're piping output:

```bash
eero --no-color network list
# or set NO_COLOR=1 / EEROCTL_NO_COLOR=1
```

### JSON Output for Scripting

For machine-readable output:

```bash
eero --output json network list
```

stdout carries only the JSON envelope; prompts, warnings and the unverified-write note
go to stderr, so `| jq` is safe on every command.

### `--output json | jq` shows non-JSON, or nothing at all

Since 3.0.0 **all** status, warning, prompt and `note:` text is written to stderr;
stdout carries only the envelope. If `jq` complains about a parse error, something on
your side is merging the streams (`2>&1`, a wrapper, a cron `MAILTO` capture) — drop
the redirect or send stderr elsewhere (`2>/dev/null` hides the warnings; `2>>log` keeps
them).

An **empty stdout after a write is expected**: write commands report "done" / "already
configured" / "verify with …" on stderr and do not render an envelope unless the
command has something structured to return. Test the exit code, not the output:

```bash
eero -o json network guest disable --force >/dev/null; echo "exit $?"
```

Reads always render an envelope; an empty stdout on a read means the command failed
and the exit code is non-zero.

### "Invalid input for 'id': must be a single path segment identifier" (exit 2)

Also seen as `'link': must be a host-relative API path` and `'url': must be an
absolute https URL on api-user.e2ro.com`. An argument containing `/` (or starting
with `/`, `http://`, `https://`) is handed to the SDK unchanged, and the SDK rejected
it before any request: `..`, whitespace, a query string or fragment, a foreign host,
or a path that belongs to a different network than the command addresses. Valid
forms: a bare id (`123456`), a host-relative path (`/2.2/eeros/123456`) or a full
`https://api-user.e2ro.com/…` URL — copy them from `--output json`. Names, serials
and MAC addresses (anything without a `/`) are still looked up for you; a nickname
that itself contains `/` must be addressed by id, serial or MAC.

---

## Debug Mode

For detailed logging when troubleshooting issues:

```bash
eero --debug network list
```

This raises the `eero` (SDK) and `eeroctl` loggers to DEBUG — not the root logger,
so the HTTP library never prints request headers — with the SDK's own redaction
applied (tokens, emails and phone numbers are masked). The raw `WARNING:eero.api.…`
line for an unverified write is passed through unchanged in this mode, in place of
the `note:` line; `meta.warnings` is populated either way.

---

## 🔗 Related Pages

- [Migration](Migration) — 3.0.0 changes, credentials, rollback
- [CLI Reference](CLI-Reference) — exit codes and safety tiers
- [Configuration](Configuration) — storage and environment variables
