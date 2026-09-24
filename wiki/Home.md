# 🌐 eeroctl Wiki

Welcome to the Eero CLI documentation! This wiki provides comprehensive guides for using the command-line interface.

## 📚 Documentation

| Page | Description |
|------|-------------|
| **[CLI Reference](CLI-Reference)** | Complete command structure, global flags, and exit codes |
| **[Usage Examples](Usage-Examples)** | Practical examples for common tasks |
| **[Configuration](Configuration)** | Authentication storage and config files |
| **[Troubleshooting](Troubleshooting)** | Common issues and solutions |
| **[Migration](Migration)** | Upgrading to 3.0.0: removed/renamed commands, exit codes, credentials, rollback |
| **[Testing Checklist](Testing-Checklist)** | Manual verification scenarios |

> **Upgrading from 2.x?** 3.0.0 requires eero-api 8.0.3 and changes exit codes,
> `auth status` output, environment-variable names and where the session token is
> stored. Read [Migration](Migration) first.

---

## 🚀 Quick Links

### Getting Started

**Using uv (Recommended):**

```bash
# Clone and install
git clone https://github.com/fulviofreitas/eeroctl.git
cd eeroctl
uv sync

# Login
uv run eero auth login

# List networks
uv run eero network list
```

**Using pip:**

```bash
# Clone and install
git clone https://github.com/fulviofreitas/eeroctl.git
cd eeroctl
pip install .

# Login
eero auth login

# List networks
eero network list
```

### Common Tasks

- **List connected devices:** `eero device list`
- **Check connectivity:** `eero troubleshoot connectivity`
- **Run a speed test:** `eero network speedtest run` then `eero network speedtest show`
- **Enable the guest network:** `eero network guest set --name "Guest"` then `eero network guest password set`
- **Check the session from a script:** `eero auth status --check`

### Features

- Noun-first commands: `eero <noun> <verb>`; every `<id>` accepts a bare id, API path or URL
- Five output formats — `table`, `list`, `json`, `yaml`, `text` — with a schema envelope for scripting
- Safety rails: Y/N prompts for disruptive writes, a typed `REBOOT` phrase for anything that restarts the mesh, an explicit note on writes the SDK has not verified
- Read-first toggles: nothing is written when the setting already matches
- Fourteen fixed exit codes, one condition each
- Every global flag has an `EEROCTL_*` environment variable; `EEROCTL_SESSION_TOKEN` for CI
- Shell completion for bash, zsh and fish

---

## 📦 Dependencies

This CLI **requires [eero-api](https://github.com/fulviofreitas/eero-api) 8.0.3** (pinned exactly) for API communication with Eero networks. Python 3.12 or newer.

---

## 🔗 External Links

- [GitHub Repository](https://github.com/fulviofreitas/eeroctl)
- [eero-api Library](https://github.com/fulviofreitas/eero-api)
- [Issue Tracker](https://github.com/fulviofreitas/eeroctl/issues)

---

## 📖 Navigation Tips

- Use the sidebar on the right to navigate between pages
- Each page has a table of contents for quick section access
- Code blocks can be copied with one click
