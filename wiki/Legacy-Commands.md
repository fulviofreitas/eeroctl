# 🔄 Legacy Commands

Mapping from deprecated commands to the new noun-first structure.

---

## Command Mapping

The following legacy commands are deprecated but still supported. They print a deprecation warning and redirect to the new command.

| Legacy Command | New Command | Notes |
|----------------|-------------|-------|
| `eero login` | `eero auth login` | Prints deprecation warning |
| `eero logout` | `eero auth logout` | |
| `eero clear-auth` | `eero auth clear` | |
| `eero networks` | `eero network list` | |
| `eero set-network` | `eero network use` | |
| `eero eeros` | `eero eero list` | |
| `eero devices` | `eero client list` | |
| `eero profiles` | `eero profile list` | |
| `eero guest-network --enable` | `eero network guest enable` | |
| `eero guest-network --disable` | `eero network guest disable` | |

---

## Output Format Changes

| Legacy Flag | New Flag | Description |
|-------------|----------|-------------|
| `--output brief` | `--output table` | Tabular format |
| `--output extensive` | `--output table --detail full` | Full details |
| `--output json` | `--output json` | Unchanged |

---

## Migration Guide

### Update Scripts

If you have scripts using legacy commands, update them:

```bash
# Old
eero login
eero networks
eero devices

# New
eero auth login
eero network list
eero client list
```

### Suppress Deprecation Warnings

If you need to temporarily suppress warnings while migrating:

```bash
eero --quiet network list
```

---

## Timeline

- **Current:** Legacy commands work with deprecation warnings
- **Future:** Legacy commands will be removed in version 2.0

We recommend updating scripts to use the new command structure.

---

## 🔗 Related Pages

- [CLI Reference](CLI-Reference) — New command structure
- [Usage Examples](Usage-Examples) — Examples with new commands

