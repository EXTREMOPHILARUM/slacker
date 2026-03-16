# Slacker

Slack code-mode plugin for Claude Code. Instead of predefined commands, Claude writes Python code on the fly using `slack_sdk` to perform any Slack operation.

## Install

### As a Claude Code plugin (recommended)

```bash
# Add the marketplace
/plugin marketplace add EXTREMOPHILARUM/slacker

# Install the plugin
/plugin install slacker

# Install dependencies and configure token
/slacker:setup xoxp-your-token
```

### Manual installation

```bash
git clone https://github.com/EXTREMOPHILARUM/slacker.git ~/.config/slacker
cd ~/.config/slacker/slacker
uv sync
cp .env.example .env   # Add your Slack tokens
```

## Setup

### Get a Slack token

1. Go to https://api.slack.com/apps → Create New App → From scratch
2. Go to **OAuth & Permissions** and add scopes:
   - Bot: `channels:read`, `chat:write`, `users:read`, `groups:read`, `im:read`, `mpim:read`, `reactions:read`, `reactions:write`, `files:read`, `files:write`, `pins:read`, `pins:write`, `bookmarks:read`, `bookmarks:write`, `usergroups:read`, `usergroups:write`, `reminders:read`, `reminders:write`
   - User (optional, enables search): `search:read`
3. Install to workspace and copy the token
4. Run `/slacker:setup <your-token>`

## Usage

Just mention Slack in conversation and Claude auto-triggers the skill. You can also use `/slack` directly.

### Examples

- "check my unreads"
- "what messages did I get in the last few hours"
- "send a deploy notification to the team channel with Block Kit"
- "read my DMs with jane"
- "search for messages about the outage last week"
- "reply to that thread saying I'll look into it"
- "post a standup summary"

## Commands

| Command | Description |
|---------|-------------|
| `/slacker:setup` | Install dependencies, configure Slack token, verify connection |
| `/slack` | Execute Slack operations via code-mode |

## Built-in helpers

The runner exposes these helpers so Claude generates less code and makes fewer API calls:

| Helper | Description |
|--------|-------------|
| `resolve_user(name_or_email)` | Resolve user by name, email, or ID. Cached. |
| `resolve_channel(name_or_id)` | Resolve channel by name, ID, or person (finds DM). Cached. |
| `paginate(method, key, **kwargs)` | Auto-paginate any Slack API method. |
| `my_id()` | Get authenticated user's ID. Cached. |
| `send(channel_or_name, text, **kwargs)` | Resolve channel + send message. Returns `ts`. |
| `reply(channel_or_name, thread_ts, text, **kwargs)` | Reply in a thread. Returns `ts`. |
| `read_conversation(channel_or_name, limit)` | Read messages with user names resolved. |
| `read_thread(channel_or_name, thread_ts, limit)` | Read thread replies with names resolved. |
| `get_unreads()` | All channels/DMs with unread counts. |
| `my_activity(since_hours)` | DMs + @mentions directed at you, deduped. |
| `cache.get_style(user)` / `cache.set_style(user, profile)` | Persist conversation style profiles for auto-replies. |

## How it works

1. You describe what you want in natural language
2. Claude writes Python code using `slack_sdk`
3. The code runs locally via `uv run`
4. Results come back formatted for minimal token usage

No MCP server, no middleware — just the SDK and Claude.

## License

MIT
