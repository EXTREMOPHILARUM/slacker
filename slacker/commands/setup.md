---
argument-hint: "[token]"
description: "Install slacker dependencies, configure Slack token, and verify setup"
allowed-tools: "Bash, AskUserQuestion"
---

# Setup Slacker

One-command onboarding: installs dependencies, configures the Slack token, and verifies everything works.

## Usage

```bash
/slacker:setup                          # Interactive — installs deps, prompts for token if missing
/slacker:setup xoxp-your-token-here     # Direct — installs deps and sets the token
```

## Implementation

Execute these steps in order:

### Step 1: Check for uv

```bash
if ! command -v uv &> /dev/null; then
  echo "uv not found. Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  echo "uv installed. You may need to restart your shell."
fi
uv --version
```

### Step 2: Find the plugin directory and install dependencies

The plugin directory is wherever this command file lives — go up one level from `commands/`.

```bash
SLACKER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
echo "Slacker directory: $SLACKER_DIR"
cd "$SLACKER_DIR" && uv sync
```

### Step 3: Verify slack_sdk

```bash
cd "$SLACKER_DIR" && uv run python -c "from slack_sdk import WebClient; print('slack_sdk OK')"
```

### Step 4: Configure token

#### If a token is provided as argument

Write it directly to `.env`:

```bash
SLACKER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
TOKEN="$1"

if [[ "$TOKEN" == xoxb-* ]]; then
  echo "SLACK_BOT_TOKEN=$TOKEN" > "$SLACKER_DIR/.env"
elif [[ "$TOKEN" == xoxp-* ]]; then
  echo "SLACK_USER_TOKEN=$TOKEN" > "$SLACKER_DIR/.env"
else
  echo "Invalid token. Must start with xoxb- (bot) or xoxp- (user)."
  exit 1
fi
```

#### If no token provided and none exists

Check if a token already exists in `.env`. If not, ask the user:

> Please provide your Slack token. You can get this from https://api.slack.com/apps → your app → OAuth & Permissions.
>
> - **Bot token** (`xoxb-...`): For sending messages, reading channels, managing users
> - **User token** (`xoxp-...`): For all bot capabilities PLUS search
>
> Paste your token:

Then write as above.

If a token already exists, skip this step.

### Step 5: Verify connection

```bash
SLACKER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
cd "$SLACKER_DIR" && uv run python scripts/run_slack.py --code "$(cat <<'PYEOF'
me = slack.auth_test()
return f"Connected as {me['user']} to {me['team']}"
PYEOF
)"
```

## Token types

| Type | Prefix | Search | Send | Read | Recommended |
|------|--------|--------|------|------|-------------|
| Bot | `xoxb-` | No | Yes | Yes | For bots |
| User | `xoxp-` | Yes | Yes | Yes | For personal use |

## Creating a Slack App

If the user doesn't have a token:

1. Go to https://api.slack.com/apps → Create New App → From scratch
2. Name it (e.g., "slacker") and pick your workspace
3. Go to **OAuth & Permissions**
4. Add scopes:
   - Bot: `channels:read`, `chat:write`, `users:read`, `groups:read`, `im:read`, `mpim:read`, `reactions:read`, `reactions:write`, `files:read`, `files:write`, `pins:read`, `pins:write`, `bookmarks:read`, `bookmarks:write`, `usergroups:read`, `usergroups:write`, `reminders:read`, `reminders:write`
   - User (optional): `search:read`
5. Install to workspace
6. Copy the token

## Troubleshooting

### "uv: command not found"
Install manually: `curl -LsSf https://astral.sh/uv/install.sh | sh`

### "slack_sdk import failed"
Run `cd <plugin_dir> && uv sync` manually.

### Dependencies won't install
Check Python version — requires Python 3.11+: `python3 --version`

## Security

- Token is stored in `<plugin_dir>/.env` which is gitignored
- Never commit tokens to version control
- Rotate tokens at https://api.slack.com/apps if compromised
