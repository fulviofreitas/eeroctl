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

