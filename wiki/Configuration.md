# ⚙️ Configuration

Authentication storage and configuration options.

---

## Authentication Storage

### Keyring (Default)

By default, credentials are stored securely in your system keyring:

- **macOS:** Keychain
- **Linux:** Secret Service (GNOME Keyring, KWallet)
- **Windows:** Windows Credential Locker

```bash
# Login with keyring storage (default)
eero auth login
```

### File-based Storage

For systems without keyring support or headless environments:

```bash
# Store credentials in config file
eero auth login --no-keyring
```

Credentials are stored in `~/.config/eeroctl/cookies.json`.

---

## Config Files

| File | Location | Purpose |
|------|----------|---------|
| Credentials | `~/.config/eeroctl/cookies.json` | Session token storage |
| Settings | `~/.config/eeroctl/config.json` | User preferences |

### Custom Config Location

```bash
# Use custom config directory
export EERO_CONFIG_DIR="/path/to/config"
eero auth login
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `EERO_CONFIG_DIR` | Custom config directory path |
| `EERO_SESSION_TOKEN` | Pre-set session token (for CI/CD) |
| `EERO_NETWORK_ID` | Default network ID |
| `NO_COLOR` | Disable colored output (standard) |

---

## Security Considerations

### Keyring Advantages

- Credentials encrypted at rest
- Protected by system authentication
- No plaintext files on disk

### File Storage Considerations

- Permissions set to `600` (owner read/write only)
- Located in user config directory
- Suitable for containers/headless systems

### CI/CD Usage

For automated pipelines, set the session token directly:

```bash
export EERO_SESSION_TOKEN="<YOUR-SESSION-TOKEN>"
eero network list
```

Or pass via environment:

```yaml
# GitHub Actions example
- name: Check Eero Status
  env:
    EERO_SESSION_TOKEN: ${{ secrets.EERO_TOKEN }}
  run: eero troubleshoot status
```

---

## 🔗 Related Pages

- [CLI Reference](CLI-Reference) — Command structure
- [Usage Examples](Usage-Examples) — Practical examples

