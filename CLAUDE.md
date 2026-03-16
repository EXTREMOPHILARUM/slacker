# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Slacker?

A Slack code-mode plugin for Claude Code. Instead of predefined commands, Claude writes Python code on the fly using `slack_sdk` to perform any Slack operation. Distributed as a Claude Code plugin marketplace.

## Repository structure

This is a **marketplace repo** (not a monorepo). The root contains the marketplace manifest, and the actual plugin lives in `slacker/`.

- **Root `.claude-plugin/marketplace.json`** — marketplace index pointing to `./slacker`
- **`slacker/`** — the plugin itself:
  - `scripts/run_slack.py` — Python runner. Takes `--code` arg, wraps it in a function, exec's it with pre-configured `slack` (WebClient), `resolve_user()`, `resolve_channel()`, `paginate()`, `my_id()`, `send()`, `reply()`, `read_conversation()`, `read_thread()`, `get_unreads()`, `my_activity()` helpers, and a JSON file cache at `.cache/lookups.json`
  - `skills/slack.md` — the core skill prompt. Documents SDK methods, Block Kit reference, output formatting guidelines, and helper usage so Claude can write code dynamically. This file IS the product — changes here directly affect LLM behavior.
  - `commands/setup.md` — `/slacker:setup` command (install deps + configure token + verify)
  - `.claude-plugin/plugin.json` — plugin manifest

## Development

```bash
cd slacker/                          # All dev work happens here
uv sync                              # Install dependencies
uv run python scripts/run_slack.py --code "$(cat <<'PYEOF'
return slack.auth_test()['user']
PYEOF
)"                                   # Test auth
```

**Important:** Always use heredoc (`PYEOF`) for `--code` args that contain dict access (`['key']`) — single-quote shell escaping breaks on backslash-quote combos.

## Key design decisions

- **The runner is intentionally dumb** — it just exec's code with the SDK pre-loaded. The LLM is the router.
- **Output formatting is prompt-driven, not code-driven** — the skill prompt tells the LLM to return lean strings (TSV, plain text lines), not the runner. This preserves flexibility.
- **Helpers (`resolve_user`, `resolve_channel`, `paginate`) exist to reduce LLM-generated boilerplate** — the skill prompt tells Claude to prefer these over raw API scanning.
- **Cache is a flat JSON file** (`.cache/lookups.json`) — no expiry, no TTL. Delete the file to clear it.

## Token configuration

Requires `SLACK_USER_TOKEN` (xoxp-) or `SLACK_BOT_TOKEN` (xoxb-) in `slacker/.env`. User tokens enable search APIs. The `slack` global uses bot token if available, falls back to user token.

## Versioning

**Always bump the version when committing changes.** Update all three places:
1. `slacker/.claude-plugin/plugin.json`
2. `slacker/pyproject.toml`
3. Root `.claude-plugin/marketplace.json` (both the marketplace version and the plugin entry version)

Use semver strictly:
- **Patch** (x.y.Z) — bug fixes, doc tweaks, example changes, rule additions, prompt wording
- **Minor** (x.Y.0) — new features (new helpers, new commands, new block types, new skill capabilities)
- **Major** (X.0.0) — breaking changes (renamed globals, restructured plugin, removed APIs)

Default to patch. Only use minor when genuinely adding new functionality.

A **pre-commit hook** (`hooks/pre-commit`) enforces this — commits will be rejected if code files changed but version files weren't updated. CLAUDE.md and README.md changes are exempt.

## Git

- Author email for this repo: `git@saurabhn.com`
- Remote: `github.com/EXTREMOPHILARUM/slacker`
- Hooks path: `hooks/` (set via `git config core.hooksPath hooks`). After cloning, run: `git config core.hooksPath hooks`
