# 🌐 Eero CLI Wiki

Welcome to the Eero CLI documentation! This wiki provides comprehensive guides for using the command-line interface.

## 📚 Documentation

| Page | Description |
|------|-------------|
| **[CLI Reference](CLI-Reference)** | Complete command structure, global flags, and exit codes |
| **[Usage Examples](Usage-Examples)** | Practical examples for common tasks |
| **[Configuration](Configuration)** | Authentication storage and config files |
| **[Troubleshooting](Troubleshooting)** | Common issues and solutions |
| **[Legacy Commands](Legacy-Commands)** | Mapping from old commands to new structure |
| **[Testing Checklist](Testing-Checklist)** | Manual verification scenarios |

---

## 🚀 Quick Links

### Getting Started

**Using uv (Recommended):**

```bash
# Clone and install
git clone https://github.com/fulviofreitas/eero-cli.git
cd eero-cli
uv sync

# Login
uv run eero auth login

# List networks
uv run eero network list
```

**Using pip:**

```bash
# Clone and install
git clone https://github.com/fulviofreitas/eero-cli.git
cd eero-cli
pip install .

# Login
eero auth login

# List networks
eero network list
```

### Common Tasks

- **List connected devices:** `eero client list`
- **Check network status:** `eero troubleshoot status`
- **Run speed test:** `eero troubleshoot speedtest --force`
- **Enable guest network:** `eero network guest enable --name "Guest" --password "pass123"`

---

## 📦 Dependencies

This CLI uses [eero-client](https://github.com/fulviofreitas/eero-client) for API communication with Eero networks.

---

## 🔗 External Links

- [GitHub Repository](https://github.com/fulviofreitas/eero-cli)
- [eero-client Library](https://github.com/fulviofreitas/eero-client)
- [Issue Tracker](https://github.com/fulviofreitas/eero-cli/issues)

---

## 📖 Navigation Tips

- Use the sidebar on the right to navigate between pages
- Each page has a table of contents for quick section access
- Code blocks can be copied with one click
