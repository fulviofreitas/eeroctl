# ⚙️ Configuration

Authentication storage and configuration options.

> Upgrading from 2.x? The credential record, its location and every environment
> variable changed in 3.0.0 — see [Migration](Migration).

---

## Authentication Storage

eeroctl stores nothing itself: the session token is written by the
[eero-api](https://github.com/fulviofreitas/eero-api) SDK. `auth_method` in
`config.json` chooses which SDK backend is used.

### Keyring (Default)

Credentials go in the system keyring under the SDK's record
**service `eero-api`, account `auth-tokens`**:

- **macOS:** Keychain
- **Linux:** Secret Service (GNOME Keyring, KWallet)
- **Windows:** Windows Credential Locker

```bash
# Login with keyring storage (default)
eero auth login
```

In keyring mode there is normally **no** `cookies.json` on disk. If one exists from an
older release, the SDK promotes its token into the keyring on the first command,
verifies the read-back, and deletes the file. `eero auth status` shows where the token
currently lives.

The record is shared with every other eero-api 8 program on the machine (for example
`rusteero`): logging out from one logs out all of them.

### File-based Storage

For systems without keyring support or headless environments:

```bash
# Store credentials in a file
eero auth login --no-keyring
```

Credentials are stored in `~/.config/eeroctl/cookies.json` (mode `600`). The record
is schema 2:

```json
{"session_id": "…", "schema_version": 2}
```

A pre-8 file (no `schema_version` key) is rewritten in place on first load. There is
no client-side expiry any more; whether the token still works is decided by the API,
which is what `eero auth status` checks.

### `cookies.json.pre-v8.bak`

Before the SDK migrates an existing schema-1 `cookies.json`, eeroctl copies it once to
`~/.config/eeroctl/cookies.json.pre-v8.bak` (mode `600`; never overwritten; not
created when the file is already schema 2). It exists only so a rollback to 2.21.8
keeps your session ([Migration → Rollback](Migration#rollback)).

It holds the session token in plain text. **Delete it once you are happy on 3.0.0.**
`eero auth clear` and `eero auth logout` remove it for you (printing "removed pre-v8
credential backup" on stderr), and `eero auth status` reports whether it is present
(*Legacy Backup* row; `legacy_backup` in `--output list`;
`storage.cookie_file.legacy_backup_present` in `json`/`yaml`).

### Ephemeral session (CI/containers)

Set `EEROCTL_SESSION_TOKEN` to skip both backends. The SDK keeps the token in memory
only; nothing is written to the keyring or disk, and the pre-v8 backup step is
skipped. `eero auth status` reports `auth_method: env` with both storage locations
`present: false`; `eero auth login`, `logout` and `clear` refuse with exit `2` and
"session comes from EEROCTL_SESSION_TOKEN; unset it to manage stored credentials".
The value must be a printable header value (no control characters); anything else
exits `2`. It is never echoed or logged, including under `--debug`. See
[CI/CD Usage](#cicd-usage).

---

## Config Files

| File | Location | Purpose |
|------|----------|---------|
| Settings | `~/.config/eeroctl/config.json` | User preferences |
| Credentials (file mode only) | `~/.config/eeroctl/cookies.json` | Session token, schema 2 |
| Credential backup | `~/.config/eeroctl/cookies.json.pre-v8.bak` | One-time pre-3.0.0 copy; safe to delete |

On Windows the directory is `%APPDATA%\eeroctl`. `EEROCTL_CONFIG_DIR` overrides it
on every platform.

### Configuration Options

The `config.json` file is created automatically on first use with these defaults:

```json
{
  "default_output": "table",
  "auth_method": "keyring",
  "preferred_network_id": null,
  "accept_language": "en-US",
  "get_retries": 0,
  "send_legacy_cookie": true
}
```

An existing 2.x `config.json` is not replaced: any key missing from it is added with
its default the next time eeroctl runs.

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `default_output` | `table`, `list`, `json`, `yaml`, `text` | `table` | Default output format for commands |
| `auth_method` | `keyring`, `cookie_file` | `keyring` | Which SDK storage backend holds the token |
| `preferred_network_id` | Network ID or `null` | `null` | Default network for commands (`eero network use`) |
| `send_legacy_cookie` | `true`, `false` | `true` | Also send the session as the legacy `s=` cookie to `api-user.e2ro.com`. The SDK expects to remove this in a future major; set `false` to test ahead of time. Flag: `--no-legacy-cookie`. |
| `accept_language` | printable ASCII, e.g. `en-US` | `en-US` | `Accept-Language` sent to the API. Invalid values exit `2` before any request. Flag: `--accept-language`. |
| `get_retries` | integer ≥ 0 | `0` | Extra attempts for a **GET** that failed with a transport error or a 5xx. Writes are never retried — by SDK design, not configurable. Flag: `--get-retries N` (negative → exit `2`). |

Precedence for the last three: **flag > environment variable > `config.json` > default**.

### Changing Settings

Edit `~/.config/eeroctl/config.json` directly, or use CLI commands:

```bash
# Set preferred network
eero network use <NETWORK_ID>

# Login with keyring (default)
eero auth login

# Login with cookie file storage
eero auth login --no-keyring
```

### Custom Config Location

```bash
# Use a custom config directory (config.json, cookies.json and the backup all move)
export EEROCTL_CONFIG_DIR="/path/to/config"
eero auth login
```

`~` is expanded. The directory is created if missing and its mode is tightened to
`0700` on every run (it holds a bearer token); a directory eeroctl cannot chmod is
used as is.

---

## Environment Variables

Every global flag has an `EEROCTL_`-prefixed variable. Flags win over variables;
variables win over `config.json`.

| Variable | Equivalent flag | Description |
|----------|-----------------|-------------|
| `EEROCTL_OUTPUT` | `--output` | Output format |
| `EEROCTL_NETWORK_ID` | `--network-id` | Network to operate on |
| `EEROCTL_FORCE` | `--force` | Skip confirmations at **every** tier, including HIGH typed-phrase writes (`REBOOT`/`DISCONNECT`/`DELETE`). eeroctl prints `note: confirmation prompts disabled by EEROCTL_FORCE` on stderr once per invocation, on every command (reads included), while the variable is set (`--quiet` suppresses it). Set it per command or per job, never globally in a shell profile. |
| `EEROCTL_NON_INTERACTIVE` | `--non-interactive` | Never prompt; exit `8` where confirmation would be needed |
| `EEROCTL_DEBUG` | `--debug` | Debug logging |
| `EEROCTL_QUIET` | `--quiet` | Suppress non-essential output |
| `EEROCTL_NO_COLOR` | `--no-color` | Disable colour |
| `EEROCTL_ACCEPT_LANGUAGE` | `--accept-language` | See `accept_language` above |
| `EEROCTL_GET_RETRIES` | `--get-retries` | See `get_retries` above |
| `EEROCTL_NO_LEGACY_COOKIE` | `--no-legacy-cookie` | See `send_legacy_cookie` above |
| `EEROCTL_CONFIG_DIR` | — | Config/credential directory |
| `EEROCTL_SESSION_TOKEN` | — | Ephemeral session token; see above |
| `NO_COLOR` | `--no-color` | Cross-tool standard; honoured as-is |

The `EERO_CONFIG_DIR`, `EERO_SESSION_TOKEN` and `EERO_NETWORK_ID` names documented for
2.x were never implemented. Use the `EEROCTL_*` names.

---

## Security Considerations

### Keyring Advantages

- Credentials encrypted at rest
- Protected by system authentication
- No plaintext files on disk (after the one-time promotion deletes `cookies.json`)

### File Storage Considerations

- Permissions set to `600` (owner read/write only)
- Located in the user config directory
- Suitable for containers/headless systems
- Remember the `.pre-v8.bak` copy is also plaintext

### What eeroctl never prints

- The session token, in any output mode. `--debug` enables debug logging on the
  `eero` (SDK) and `eeroctl` loggers only — never the root logger, so the HTTP
  library cannot dump the raw `X-User-Token` header — and the SDK redacts tokens,
  emails and phone numbers from what it logs.
- API response bodies on error. Errors render the SDK's message plus
  `(error code: …)`; the body is available only through the redacted `--debug` log.
- Sensitive keys in undocumented payloads. The generic key/value renderer used for
  `table`, `list` and `text` masks, at any nesting depth, values whose key matches the
  SDK's own zero-visibility patterns (`access_token`, `api_key`, `apikey`, `auth`,
  `authorization`, `bearer`, `cookie`, `credential`, `key`, `passwd`, `password`,
  `private`, `refresh_token`, `secret`, `session`, `session_id`, `token`, `user_token`)
  plus `email`, `phone`, `sms`, printing `<redacted>` instead. `serial`, `mac` and
  `url` are shown. `json`/`yaml` are the raw payload — never masked. Full list and
  caveats: [CLI Reference → Redaction](CLI-Reference#redaction-in-table-list-and-text).

### `EEROCTL_FORCE` in the environment

`EEROCTL_FORCE=1` is equivalent to `--force`: it disables confirmation at every tier,
including the typed phrases that protect mesh reboots and deletions. eeroctl prints
`note: confirmation prompts disabled by EEROCTL_FORCE` on stderr at the start of
every invocation while the variable is set — reads included, not only the writes it
disarms (suppressed by `--quiet`). The provenance is
tracked only internally (`force_source`) and is not exposed in any output, so the
notice is the only signal you get — keep the variable scoped to the job that needs it,
never in `~/.bashrc` or `~/.zshrc`.

### CI/CD Usage

For automated pipelines, supply the session token through the environment. Obtain it
once on a workstation by logging in with file storage and copying `session_id` from
`cookies.json`:

```bash
export EEROCTL_SESSION_TOKEN="<YOUR-SESSION-TOKEN>"
export EEROCTL_NETWORK_ID="<NETWORK-ID>"
eero network list
```

```yaml
# GitHub Actions example
- name: Check Eero connectivity
  env:
    EEROCTL_SESSION_TOKEN: ${{ secrets.EERO_TOKEN }}
    EEROCTL_NETWORK_ID: ${{ vars.EERO_NETWORK_ID }}
    EEROCTL_NON_INTERACTIVE: "1"
  run: eero troubleshoot connectivity --output json
```

Use `eero auth status --check` as a cheap pre-flight: it exits `3` when the token is
missing or rejected.

---

## 🔗 Related Pages

- [Migration](Migration) — what changed in 3.0.0 and how to roll back
- [CLI Reference](CLI-Reference) — Command structure
- [Usage Examples](Usage-Examples) — Practical examples
