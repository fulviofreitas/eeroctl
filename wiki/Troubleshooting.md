# 🔧 Troubleshooting

Common issues and their solutions when using the Eero Client.

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

### Session Expired

If you see authentication errors, your session may have expired. Re-authenticate:

```bash
eero auth login --force
```

### Clear All Credentials

To completely reset authentication:

```bash
eero auth clear --force
```

---

## Network Connection Issues

### No Networks Found

If `eero network list` returns no networks:

1. Verify you're logged in: `eero auth status`
2. Check your Eero account has networks associated
3. Try re-authenticating: `eero auth login --force`

### API Timeouts

For slow or unreliable connections, the CLI will automatically retry. If issues persist:

1. Check your internet connection
2. Try again in a few minutes (Eero API may be temporarily unavailable)

---

## CLI Output Issues

### Disable Colors

If your terminal doesn't support colors or you're piping output:

```bash
eero --no-color network list
```

### JSON Output for Scripting

For machine-readable output:

```bash
eero --output json network list
```

---

## Debug Mode

For detailed logging when troubleshooting issues:

```bash
eero --debug network list
```

This will show HTTP requests, responses, and internal operations.

