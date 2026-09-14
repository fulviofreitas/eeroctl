# 🧪 Testing Checklist

Manual verification scenarios before releasing.

---

## Pre-Release Checklist

### Authentication

- [ ] `eero auth login` — Complete login flow
- [ ] `eero auth status` — Shows authentication status
- [ ] `eero auth logout` — Successfully logs out
- [ ] `eero auth clear` — Clears stored credentials

### Output Formats

- [ ] `eero network list --output table` — Table output format
- [ ] `eero network list --output json` — JSON output format
- [ ] `eero network list --output list` — List output format

### Core Commands

- [ ] `eero network show` — Shows network details
- [ ] `eero eero list` — Lists Eero nodes
- [ ] `eero client list` — Lists connected clients
- [ ] `eero profile list` — Lists profiles

### Safety Rails

- [ ] `eero eero reboot <id>` — Prompts for REBOOT confirmation
- [ ] `eero eero reboot <id> --force` — Skips confirmation
- [ ] `eero eero reboot <id> --non-interactive` — Exits with code 8
- [ ] `eero troubleshoot restart --all` — Prompts for RESTART ALL

### Help & Documentation

- [ ] `eero --help` — Clean help output
- [ ] `eero network --help` — Subcommand help
- [ ] `eero network dns --help` — Nested subcommand help
- [ ] `eero network dns mode set --help` — Names no fixed provider list; points at `dns providers`

### DNS (destructive — every write reboots the network)

- [ ] `eero network dns show` — Real mode/servers/caching, not defaults
- [ ] `eero network dns show --output json` — DNS subtree only; no password, wan_ip or eeros
- [ ] `eero network dns providers` — Lists the network's catalogue
- [ ] `eero network dns mode set <provider>` — Prompts for `REBOOT`
- [ ] `eero network dns mode set <provider>` twice — Second run exits 0, "already configured", no write
- [ ] `eero network dns mode set custom -s 1.1.1.1 -s 1.0.0.1 -s 8.8.8.8` — Exits 2 before prompting
- [ ] `eero --non-interactive network dns clear` — Exits 8, never hangs

### Legacy Compatibility

- [ ] `eero login` — Prints deprecation warning, works
- [ ] `eero networks` — Prints deprecation warning, works
- [ ] `eero devices` — Prints deprecation warning, works

### Error Handling

- [ ] Invalid network ID — Shows "not found" error
- [ ] No authentication — Shows "login required" message
- [ ] Network timeout — Shows timeout error

---

## Exit Code Verification

| Scenario | Expected Code |
|----------|---------------|
| Successful command | 0 |
| Invalid arguments | 2 |
| Not authenticated | 3 |
| Resource not found | 5 |
| Safety rail triggered | 8 |

```bash
# Test exit codes
eero auth status; echo "Exit: $?"
eero network show --network-id invalid; echo "Exit: $?"
eero eero reboot test --non-interactive; echo "Exit: $?"
```

---

## 🔗 Related Pages

- [CLI Reference](CLI-Reference) — Exit codes reference
- [Usage Examples](Usage-Examples) — Command examples

