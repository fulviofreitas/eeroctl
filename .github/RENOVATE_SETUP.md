# 🔄 Renovate Setup Guide

This document describes how to set up Renovate for automated dependency updates in eero-cli.

## Overview

Renovate automatically creates PRs when dependencies are updated. For eero-cli, the most critical dependency is `eero-client`, which is tracked via a custom regex manager since it uses a git URL.

## Architecture

```
eero-client releases v1.x.x
    ↓ repository_dispatch
eero-cli Renovate workflow triggers
    ↓
PR created: "chore(deps-critical): update eero-client v1.x.x"
    ↓
CI runs on the PR
    ↓
Maintainer reviews and merges
```

## Prerequisites

### 1. Create a GitHub App

The Renovate workflow uses a GitHub App for authentication (better rate limits and security than PATs).

1. Go to **Settings** → **Developer settings** → **GitHub Apps** → **New GitHub App**
   - URL: `https://github.com/settings/apps/new`

2. Configure the app:
   - **GitHub App name**: `eero-cli-renovate` (must be unique)
   - **Homepage URL**: `https://github.com/fulviofreitas/eero-cli`
   - **Webhook**: Uncheck "Active" (not needed)

3. Set permissions (Repository permissions):
   | Permission | Access |
   |------------|--------|
   | Contents | Read & Write |
   | Issues | Read & Write |
   | Pull requests | Read & Write |
   | Metadata | Read-only |

4. Where can this GitHub App be installed?: **Only on this account**

5. Click **Create GitHub App**

### 2. Generate Private Key

1. After creating the app, scroll down to **Private keys**
2. Click **Generate a private key**
3. A `.pem` file will be downloaded - keep this secure!

### 3. Install the App

1. Go to your GitHub App's settings
2. Click **Install App** in the left sidebar
3. Select your account and choose **Only select repositories**
4. Select `eero-cli`
5. Click **Install**

### 4. Add Secrets to eero-cli Repository

Go to `eero-cli` repository **Settings** → **Secrets and variables** → **Actions**:

| Secret Name | Value |
|-------------|-------|
| `RENOVATE_APP_ID` | The App ID from your GitHub App settings (a number) |
| `RENOVATE_APP_PRIVATE_KEY` | Contents of the `.pem` file (entire file including headers) |

### 5. Add Secret to eero-client Repository

For the release notification to work, eero-client needs a token to dispatch to eero-cli:

1. Create a **Fine-grained Personal Access Token** (PAT):
   - Go to **Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens**
   - **Token name**: `eero-cli-dispatch`
   - **Expiration**: 1 year (or custom)
   - **Repository access**: Only select repositories → `eero-cli`
   - **Permissions**: 
     - Contents: Read-only
     - Metadata: Read-only (auto-selected)
   
   > Note: `repository_dispatch` only requires read access to contents

2. Add the token to `eero-client`:
   - Go to `eero-client` repository **Settings** → **Secrets and variables** → **Actions**
   - Add secret: `EERO_CLI_DISPATCH_TOKEN` with the PAT value

## Configuration Files

### `.github/renovate.json5`

The Renovate configuration with:
- Custom regex manager for `eero-client` git dependency
- Auto-merge for minor/patch updates (except eero-client)
- High priority labels for eero-client updates
- Dependency dashboard issue

### `.github/workflows/renovate.yml`

The workflow that:
- Runs weekly (Mondays at 3 AM UTC)
- Triggers on `repository_dispatch` from eero-client releases
- Supports manual dispatch with dry-run option
- Caches Renovate data for faster runs

## Triggers

| Trigger | When |
|---------|------|
| **Schedule** | Weekly on Mondays at 3 AM UTC |
| **Manual** | Workflow dispatch (Actions tab) |
| **eero-client release** | Immediate via `repository_dispatch` |

## Testing the Setup

### 1. Manual Dry Run

1. Go to **Actions** → **🔄 Renovate** → **Run workflow**
2. Set **Dry-run mode** to `true`
3. Set **Log level** to `debug`
4. Run the workflow
5. Check the logs for any configuration errors

### 2. Verify Configuration

Run Renovate manually without dry-run:
1. Go to **Actions** → **🔄 Renovate** → **Run workflow**
2. Keep defaults and run
3. Check if:
   - Dependency Dashboard issue is created
   - PRs are created for any outdated dependencies

### 3. Test eero-client Notification

After a new eero-client release:
1. Check eero-cli **Actions** tab for a Renovate run triggered by `repository_dispatch`
2. A PR should be created for the eero-client update

## Troubleshooting

### "Bad credentials" Error

- Verify `RENOVATE_APP_ID` is correct (it's a number, not the app name)
- Verify `RENOVATE_APP_PRIVATE_KEY` includes the full PEM file with headers

### No eero-client Updates Detected

- Ensure `pyproject.toml` has the version tag: `@v1.2.1`
- Check that the regex in `renovate.json5` matches your format
- Run with `debug` log level to see what Renovate detects

### repository_dispatch Not Triggering

- Verify `EERO_CLI_DISPATCH_TOKEN` is set in eero-client secrets
- Check eero-client release workflow logs for dispatch errors
- Ensure the token has access to the eero-cli repository

## Related Files

- `.github/renovate.json5` - Renovate configuration
- `.github/workflows/renovate.yml` - Renovate workflow
- `pyproject.toml` - Python dependencies (line 30)

## Links

- [Renovate Documentation](https://docs.renovatebot.com/)
- [GitHub Apps Guide](https://docs.github.com/en/apps/creating-github-apps)
- [Repository Dispatch](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#repository_dispatch)
